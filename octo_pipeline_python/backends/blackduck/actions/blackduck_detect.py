import os
from http import HTTPStatus
from typing import Optional

import requests

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.blackduck.models import BlackduckModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

DEFAULT_EXCLUDED_DIRS = ["build"]


class BlackduckDetect(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        blackduck_args: BlackduckModel = backend.backend_args(backends_context,
                                                              pipeline_context,
                                                              workspace_context,
                                                              self.action_type,
                                                              action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Preparing detect action")
        blackduck_dir = backends_context.attribute(backend.backend_name(),
                                                   "blackduck_dir",
                                                   tag=pipeline_context.name)
        blackduck_script_resp = requests.get(blackduck_args.detect_script_url, allow_redirects=True)
        if blackduck_script_resp.status_code != HTTPStatus.OK:
            return False
        blackduck_filepath = os.path.join(blackduck_dir, "detect.sh")
        with open(blackduck_filepath, "w") as f:
            f.write(blackduck_script_resp.content.decode("utf-8"))
        return True

    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        blackduck_args: BlackduckModel = backend.backend_args(backends_context,
                                                              pipeline_context,
                                                              workspace_context,
                                                              self.action_type,
                                                              action_name)
        blackduck_dir = backends_context.attribute(backend.backend_name(),
                                                   "blackduck_dir",
                                                   tag=pipeline_context.name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running detect action")
        blackduck_secret = backend.load_backend_secret(pipeline_context,
                                                       workspace_context,
                                                       pipeline_context.name)
        if not blackduck_secret:
            return ActionResult(action_type=self.action_type,
                                result=[f"Failed to find blackduck api token"],
                                result_code=ActionResultCode.FAILURE)
        blackduck_filepath = os.path.join(blackduck_dir, "detect.sh")
        if not os.path.exists(blackduck_filepath):
            return ActionResult(action_type=self.action_type,
                                result=[f"Failed to find blackduck detect"],
                                result_code=ActionResultCode.FAILURE)
        excluded_dirs = DEFAULT_EXCLUDED_DIRS + blackduck_args.excluded_directories
        source_path = pipeline_context.source_dir
        if blackduck_args.source_path:
            source_path = os.path.join(source_path, blackduck_args.source_path)
        conan_build_dir = os.path.join(workspace_context.working_dir, 'conan', pipeline_context.name)
        conan_lock = None
        if "conan" in blackduck_args.detectors and os.path.exists(conan_build_dir):
            for config in ["relwithdebinfo", "release", "debug"]:
                config_conan_lock = os.path.join(conan_build_dir, config, "conan.lock")
                if os.path.exists(config_conan_lock):
                    conan_lock = config_conan_lock
                    logger.info(f"Detecting with conan lock file [{conan_lock}]")
                    break
        blackduck_cmd = f"{blackduck_args.detect_script_shell} {blackduck_filepath} " \
                        f"--blackduck.api.token={blackduck_secret['token']} " \
                        f"--blackduck.url={blackduck_args.blackduck_url} " \
                        f"--blackduck.trust.cert={'true' if blackduck_args.blackduck_certificate_validation else 'false'} " \
                        f"--detect.source.path={source_path} " \
                        f"--detect.project.version.name={pipeline_context.version} " \
                        f"--detect.project.name={pipeline_context.name if not blackduck_args.project_group else f'{blackduck_args.project_group}-{pipeline_context.name}'} " \
                        f"--detect.parallel.processors={blackduck_args.parallel_processors} " \
                        f"--detect.wait.for.results={'true' if blackduck_args.wait_for_results else 'false'} " \
                        f"--detect.tools={','.join(map(lambda t: t.upper(), blackduck_args.tools))} " \
                        f"--detect.excluded.directories={','.join(excluded_dirs)} " \
                        f"--detect.clone.project.version.latest={'true' if blackduck_args.clone_from_latest else 'false'}" \
                        + (f" --detect.required.detector.types={','.join(map(lambda d: d.upper(), blackduck_args.detectors))}" if blackduck_args.detectors else "") \
                        + (f" --detect.conan.lockfile.path={conan_lock}" if conan_lock else "") \
                        + (f" --detect.code.location.name={blackduck_args.code_location_name}" if blackduck_args.code_location_name else "")
        p = pipeline_context.run_contextual(blackduck_cmd, False)
        return_code = p.wait()
        if return_code != 0:
            return ActionResult(action_type=self.action_type,
                                result=[f"Failed to run blackduck detect"],
                                result_code=ActionResultCode.FAILURE)
        return ActionResult(action_type=self.action_type,
                            result=[],
                            result_code=ActionResultCode.SUCCESS)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        blackduck_dir = backends_context.attribute(backend.backend_name(),
                                                   "blackduck_dir",
                                                   tag=pipeline_context.name)
        blackduck_filepath = os.path.join(blackduck_dir, "detect.sh")
        if os.path.exists(blackduck_filepath):
            os.remove(blackduck_filepath)

    @property
    def action_type(self) -> ActionType:
        return ActionType.Detect
