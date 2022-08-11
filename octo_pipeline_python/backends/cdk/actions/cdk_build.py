import fnmatch
import glob
import hashlib
import os
import platform
import shutil
import socket
from pathlib import Path
from shutil import ignore_patterns
from typing import List, Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.cdk.models import CDKIncludePath, CDKModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.exec import ExecUtils
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class CDKBuild(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        cdk_working_dir = backends_context.attribute(backend.backend_name(),
                                                     "cdk_working_dir", tag=pipeline_context.name)
        cdk_build_dir = os.path.join(cdk_working_dir, ".build")
        cdk_cache_dir = os.path.join(cdk_working_dir, ".cache")
        backends_context.add_attribute(backend.backend_name(),
                                       "cdk_build_dir", cdk_build_dir, tag=pipeline_context.name)
        backends_context.add_attribute(backend.backend_name(),
                                       "cdk_cache_dir", cdk_cache_dir, tag=pipeline_context.name)
        return True

    @staticmethod
    def __clean_build_target(backend: Backend,
                             backends_context: BackendsContext,
                             pipeline_context: PipelineContext,
                             cdk_args: CDKModel) -> None:
        cdk_build_dir = Path(backends_context.attribute(backend.backend_name(),
                                                        "cdk_build_dir", tag=pipeline_context.name))
        cdk_cache_dir = Path(backends_context.attribute(backend.backend_name(),
                                                        "cdk_cache_dir", tag=pipeline_context.name))
        cdk_requirements = backends_context.attribute(backend.backend_name(),
                                                      "cdk_requirements", tag=pipeline_context.name)
        if not cdk_args.skip_deps:
            cdk_hash_file = Path(str(cdk_requirements) + ".md5")
            if cdk_hash_file.is_file():
                cdk_hash_file.unlink()
            shutil.rmtree(cdk_build_dir, ignore_errors=True)
            cdk_build_dir.mkdir(parents=True, exist_ok=True)
            cdk_cache_dir.mkdir(parents=True, exist_ok=True)
        else:
            for include_path in cdk_args.include_paths:
                path = include_path
                if isinstance(include_path, CDKIncludePath):
                    if include_path.envs and cdk_args.deploy_env not in include_path.envs:
                        continue
                    path = include_path.path
                shutil.rmtree(cdk_build_dir / os.path.basename(os.path.normpath(path)),
                              ignore_errors=True)

    @staticmethod
    def __ignore_patterns(*patterns):
        def _ignore_patterns(path, names):
            ignored_names = []
            for pattern in patterns:
                ignored_names.extend(fnmatch.filter(names, pattern))
                for name in names:
                    if os.path.commonpath([os.path.join(path, name), pattern]) == pattern:
                        ignored_names.append(name)
            return set(ignored_names)

        return _ignore_patterns

    @staticmethod
    def __copy_resources(backend: Backend,
                         backends_context: BackendsContext,
                         pipeline_context: PipelineContext,
                         cdk_args: CDKModel) -> None:
        cdk_build_dir = Path(backends_context.attribute(backend.backend_name(),
                                                        "cdk_build_dir", tag=pipeline_context.name))
        logger.info('Copying \'include\' resources:')
        for include_path in cdk_args.include_paths:
            path = include_path
            if isinstance(include_path, CDKIncludePath):
                if include_path.envs and cdk_args.deploy_env not in include_path.envs:
                    continue
                path = include_path.path
            ignore_pattern_func = None
            if cdk_args.exclude_paths:
                ignore_pattern_func = CDKBuild.__ignore_patterns(*cdk_args.exclude_paths)
            logger.info(f'    -  {(Path.cwd() / path).resolve()}')
            logger.info(f'        ->  {(cdk_build_dir / os.path.basename(os.path.normpath(path))).as_posix()}')
            shutil.copytree(path, (cdk_build_dir / os.path.basename(os.path.normpath(path))).as_posix(),
                            ignore=ignore_pattern_func)

    @staticmethod
    def __consume_deps(backend: Backend,
                       backends_context: BackendsContext,
                       pipeline_context: PipelineContext,
                       cdk_args: CDKModel) -> None:
        if platform.system().lower() == 'linux':
            CDKBuild.__consume_natively(backend, backends_context, pipeline_context, cdk_args)
        else:
            CDKBuild.__consume_using_docker(backend, backends_context, pipeline_context, cdk_args)

    @staticmethod
    def __consume_natively(backend: Backend,
                           backends_context: BackendsContext,
                           pipeline_context: PipelineContext,
                           cdk_args: CDKModel) -> None:
        cdk_build_dir = Path(backends_context.attribute(backend.backend_name(),
                                                        "cdk_build_dir", tag=pipeline_context.name))
        cdk_requirements = backends_context.attribute(backend.backend_name(),
                                                      "cdk_requirements", tag=pipeline_context.name)
        logger.info('Installing lambda runtime dependencies on Linux')
        strip_exclude: str = CDKBuild.__get_strip_exclude(cdk_args.strip_exclude_list)
        if os.system(f"{ExecUtils.detect_python()} -m pip install --target {cdk_build_dir} --requirement {cdk_requirements} &&"
                     f"find {cdk_build_dir} -name "
                     "\\*.so "
                     f"{strip_exclude} "
                     "-exec strip \\{\\} \\;") != 0:
            raise Exception('Cloud not resolve lambda runtime dependencies')
        logger.info('Finish to install lambda runtime dependencies')

    @staticmethod
    def __consume_using_docker(backend: Backend,
                               backends_context: BackendsContext,
                               pipeline_context: PipelineContext,
                               cdk_args: CDKModel) -> None:
        import docker
        from docker.errors import APIError, NotFound
        from docker.types import Mount
        cdk_requirements = Path(backends_context.attribute(backend.backend_name(),
                                                           "cdk_requirements", tag=pipeline_context.name))
        cdk_build_dir = Path(backends_context.attribute(backend.backend_name(),
                                                        "cdk_build_dir", tag=pipeline_context.name))
        cdk_cache_dir = Path(backends_context.attribute(backend.backend_name(),
                                                        "cdk_cache_dir", tag=pipeline_context.name))
        art_ip = socket.gethostbyname("artifactory")
        logger.info('Installing dependencies [running in Docker]...')
        client = docker.from_env()
        try:
            client.images.get('amazon/aws-sam-cli-build-image-python3.8:latest')
        except docker.errors.ImageNotFound:
            client.images.pull(repository='amazon/aws-sam-cli-build-image-python3.8', tag='latest')
        # pylint: disable=bad-option-value
        strip_exclude: str = CDKBuild.__get_strip_exclude(cdk_args.strip_exclude_list)
        command: str = f"/bin/sh -c 'echo \"{art_ip} artifactory\" >> /etc/hosts && " \
                       "python3.8 -m pip install --trusted-host artifactory " \
                       "--trusted-host=artifactory.com --target /var/task/" \
                       " --requirement /root/cdk_requirements.txt && " \
                       f"find /var/task -name \\*.so {strip_exclude} " \
                       "-exec strip \\{\\} \\;'"
        container = client.containers.run(
            image='amazon/aws-sam-cli-build-image-python3.8:latest',
            command=command,
            auto_remove=True,
            mounts=[
                Mount(target="/var/task", source=cdk_build_dir.as_posix(), type="bind", consistency="delegated"),
                Mount(target="/root/cdk_requirements.txt", source=cdk_requirements.as_posix(), type="bind",
                      consistency="delegated", read_only=True),
                Mount(target="/root/.cache", source=cdk_cache_dir.as_posix(), type="bind", consistency="delegated"),
                Mount(target="/root/.netrc", source=f"{str(Path.home())}/.netrc", type="bind",
                      consistency="delegated", read_only=True)
            ],
            user=0,
            detach=True,
        )
        try:
            if cdk_args.verbose:
                for log in container.logs(stream=True, follow=True):
                    logger.info(log.decode('utf-8'))
            else:
                container.wait()
        finally:  # handle Ctrl-C or other interruptions: kill the container
            try:
                container.kill()
            except (NotFound, APIError):
                pass  # container has already exited, was already deleted, etc.

    @staticmethod
    def __get_strip_exclude(exclude_list: Optional[List[str]]) -> str:
        exclude_string = ""
        if exclude_list:
            for index in range(0, len(exclude_list)):
                exclude_string += f"-not -name {exclude_list[index]}"
                if index != len(exclude_list) - 1:
                    exclude_string += f" -and "
        return exclude_string

    @staticmethod
    def __truncate_deps(backend: Backend,
                        backends_context: BackendsContext,
                        pipeline_context: PipelineContext,
                        cdk_args: CDKModel) -> None:
        logger.info("Truncating dependencies...")
        cdk_build_dir = Path(backends_context.attribute(backend.backend_name(),
                                                        "cdk_build_dir", tag=pipeline_context.name))
        # Truncate paths
        if cdk_args.truncate_deps:
            for path in cdk_args.truncate_deps:
                full_path = os.path.join(cdk_build_dir, path)
                for resolved_path in glob.glob(full_path):
                    if os.path.exists(resolved_path):
                        logger.info(f"Truncating dependency [{resolved_path}]")
                        if os.path.isdir(resolved_path):
                            shutil.rmtree(resolved_path, ignore_errors=True)
                        else:
                            os.remove(resolved_path)

    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        cdk_args: CDKModel = backend.backend_args(backends_context,
                                                  pipeline_context,
                                                  workspace_context,
                                                  self.action_type,
                                                  action_name)
        cdk_requirements = backends_context.attribute(backend.backend_name(),
                                                      "cdk_requirements", tag=pipeline_context.name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running build action")
        # Check if consumption is needed
        current_md5: Optional[str] = None
        md5_hash_file = Path(cdk_requirements + ".md5")
        if cdk_args.skip_deps:
            prev_md5 = md5_hash_file.read_text() if md5_hash_file.is_file() else ''
            current_md5 = hashlib.md5(Path(cdk_requirements).read_bytes()).hexdigest()
            cdk_args.skip_deps = prev_md5 == current_md5
        # Clean old build target
        CDKBuild.__clean_build_target(backend, backends_context, pipeline_context, cdk_args)
        # Copy resources needed
        CDKBuild.__copy_resources(backend, backends_context, pipeline_context, cdk_args)
        # Consume deps if needed
        if not cdk_args.skip_deps:
            CDKBuild.__consume_deps(backend, backends_context, pipeline_context, cdk_args)
        if not current_md5:
            current_md5 = hashlib.md5(Path(cdk_requirements).read_bytes()).hexdigest()
        md5_hash_file.write_text(current_md5)
        CDKBuild.__truncate_deps(backend, backends_context, pipeline_context, cdk_args)
        return ActionResult(action_type=self.action_type,
                            result=[],
                            result_code=ActionResultCode.SUCCESS)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        cdk_build_dir = Path(backends_context.attribute(backend.backend_name(),
                                                        "cdk_build_dir", tag=pipeline_context.name))
        cdk_cache_dir = Path(backends_context.attribute(backend.backend_name(),
                                                        "cdk_cache_dir", tag=pipeline_context.name))
        cdk_requirements = backends_context.attribute(backend.backend_name(),
                                                      "cdk_requirements", tag=pipeline_context.name)
        shutil.rmtree(cdk_build_dir, ignore_errors=True)
        shutil.rmtree(cdk_cache_dir, ignore_errors=True)
        if os.path.exists(cdk_requirements):
            os.unlink(cdk_requirements)
        return None

    @property
    def action_type(self) -> ActionType:
        return ActionType.Build
