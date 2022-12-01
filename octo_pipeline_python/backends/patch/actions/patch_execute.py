import os
import platform
import subprocess
from pathlib import Path
from typing import Final, List, Optional, Union

from overrides import overrides

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.patch.models import PatchModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

_PATCH_OK_RC: Final[int] = 0


class PatchExecute(Action):
    @overrides
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        action_args: PatchModel = backend.backend_args(backends_context, pipeline_context, workspace_context,
                                                       self.action_type, action_name)

        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] Preparing to patch files")

        p = self.__subprocess("--version", action_args)
        if p.returncode != _PATCH_OK_RC:
            logger.error("Failed to locate patch executable")
            return False

        missing_files: List[str] = []
        for file_patch in action_args.files:
            src_path = Path(os.path.join(pipeline_context.source_dir, "patches", file_patch.patch_src))
            dst_path = Path(os.path.join(pipeline_context.source_dir, action_args.working_dir, file_patch.patch_dst))

            for path in (src_path, dst_path):
                if not path.exists():
                    missing_files.append(f"({path}, No such file)")
                elif not path.is_file():
                    missing_files.append(f"({path}, Not a file)")

        if len(missing_files) > 0:
            logger.error(f"Failed to validate all patch files [{','.join(missing_files)}]")
            return False
        return True

    @overrides
    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        action_args: PatchModel = backend.backend_args(backends_context, pipeline_context, workspace_context,
                                                       self.action_type, action_name)
        working_dir = os.path.join(pipeline_context.source_dir, action_args.working_dir)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running execute {backend.backend_name()} action")

        results: List[str] = []
        rc: ActionResultCode = ActionResultCode.SUCCESS
        for file_patch in action_args.files:
            if file_patch.platform_list is not None:
                if platform.system().lower() not in (platform_.lower() for platform_ in file_patch.platform_list):
                    logger.info(f"Skipping patching [{file_patch.patch_src}] due to platform")
                    continue

            src_file = os.path.join(pipeline_context.source_dir, "patches", file_patch.patch_src)
            dst_file = os.path.join(pipeline_context.source_dir, action_args.working_dir, file_patch.patch_dst)
            logger.info(f"Patching [{dst_file}] with [{src_file}]")

            p = self.__subprocess([dst_file, src_file], action_args, cwd=working_dir)
            patch_stdout, patch_stderr = p.communicate()
            if p.returncode != _PATCH_OK_RC:
                patch_err = " - ".join((pipe.decode().replace("\n", "\\n")
                                        for pipe in (patch_stderr, patch_stdout) if pipe)) or "-"
                if not self.__check_already_patched(dst_file, src_file, action_args, cwd=working_dir):
                    results.append(f"Patching [{dst_file}] with [{src_file}] failed [{p.returncode}][{patch_err}]")
                    rc = ActionResultCode.FAILURE
                else:
                    logger.info(f"File [{dst_file}] was already patched")

        return ActionResult(action_type=self.action_type,
                            result=results,
                            result_code=rc)

    @staticmethod
    def __subprocess(cmd_args: Union[List[str], str], action_args: PatchModel, **kwargs) -> subprocess.Popen:
        if isinstance(cmd_args, list):
            cmd_args = " ".join(cmd_args)

        if "shell" not in kwargs:
            kwargs["shell"] = True
        for std_kwarg in ("stdout", "stderr"):
            if std_kwarg not in kwargs:
                kwargs[std_kwarg] = subprocess.PIPE if not action_args.verbose else None

        full_cmd: Final[str] = f"{action_args.patch_binary_path} {cmd_args}"
        p = subprocess.Popen(full_cmd, **kwargs)
        p.communicate()
        return p

    @staticmethod
    def __check_already_patched(dst_file: str, src_file: str, action_args: PatchModel, **kwargs) -> bool:
        """Check if this is being run again and the file was already patched before."""
        p = PatchExecute.__subprocess([dst_file, src_file, "--dry-run", "-R"], action_args, **kwargs)
        p.communicate()

        return p.returncode == _PATCH_OK_RC

    @overrides
    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        return None

    @property
    @overrides
    def action_type(self) -> ActionType:
        return ActionType.Patch
