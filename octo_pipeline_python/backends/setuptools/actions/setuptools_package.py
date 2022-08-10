import os
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.setuptools.models import SetupToolsModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.exec import ExecUtils
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class SetupToolsPackage(Action):
    def __init__(self):
        self._root_dirs = {}

    def prepare(self,
                backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        try:
            from octo_pipeline_python.backends.conan import ConanBackend
            from octo_pipeline_python.backends.conan.models import \
                ConanConfiguration

            def package_to_root(p: str) -> str:
                return f"{p.upper().replace('-', '_')}_ROOT"

            conan_consumed_packages = \
                ConanBackend.get_consumed_packages(backends_context)
            self._root_dirs = {}
            for conan_configuration in reversed(ConanConfiguration):
                for k, v in conan_consumed_packages[conan_configuration].items():
                    if package_to_root(k) not in self._root_dirs.keys() \
                            and v["package"]["rootpath"]:
                        self._root_dirs[package_to_root(k)] = v["package"]["rootpath"]
        except (ImportError, ModuleNotFoundError):
            pass
        return True

    def execute(self,
                backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        setuptools_args: SetupToolsModel = backend.backend_args(
            backends_context,
            pipeline_context,
            workspace_context,
            self.action_type,
            action_name
        )
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running package action")
        setup_env_args = os.environ.copy()
        setup_env_args.update(**self._root_dirs)
        setup_env_args["PIPELINE_WORKING_DIR"] = pipeline_context.working_dir

        for package in setuptools_args.packages:
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Packaging [{package}]")
            full_path = os.path.join(pipeline_context.source_dir, package)
            if not os.path.exists(os.path.join(full_path, "setup.py")):
                return ActionResult(
                        action_type=self.action_type,
                        result=[f"Failed to find setup.py in [{package}]"],
                        result_code=ActionResultCode.FAILURE)
            p = pipeline_context.run_contextual(f"{ExecUtils.detect_python()} -m setup bdist_wheel",
                                                cwd=full_path,
                                                env=setup_env_args)
            p.communicate()
            if p.returncode != 0:
                return ActionResult(
                        action_type=self.action_type,
                        result=[f"Failed to run setup.py in [{package}]"],
                        result_code=ActionResultCode.FAILURE)
        return ActionResult(action_type=self.action_type,
                            result=[],
                            result_code=ActionResultCode.SUCCESS)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        return None

    @property
    def action_type(self) -> ActionType:
        return ActionType.Package
