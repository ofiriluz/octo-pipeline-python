import os
import subprocess
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.cppcheck.models import CppCheckModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class CppCheckCodeCheck(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        return True

    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        cppcheck_args: CppCheckModel = backend.backend_args(backends_context,
                                                            pipeline_context,
                                                            workspace_context,
                                                            self.action_type,
                                                            action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running code checks action")
        cppcheck_dir = backends_context.attribute(backend.backend_name(),
                                                  "cppcheck_dir",
                                                  tag=pipeline_context.name)
        cppcheck_ignore_dirs = " ".join(f"-i{folder}"
                                        for folder
                                        in cppcheck_args.ignore_folders)
        preprocessor_symbols: Optional[str] = None
        if cppcheck_args.define_preprocessor_symbols:
            preprocessor_symbols = \
                " ".join(f"-D{symbol}" for symbol in
                         cppcheck_args.define_preprocessor_symbols)
        included_files: Optional[str] = None
        if cppcheck_args.include_files:
            included_files = " ".join(f"--include={file}" for file in
                                      cppcheck_args.include_files)
        cppcheck_switches = (
            "--quiet",
            "--force" if cppcheck_args.force else None,
            f"--output-file={cppcheck_dir}/cppcheck.txt",
            "--suppress=missingInclude",
            f"{cppcheck_ignore_dirs}" if cppcheck_ignore_dirs else None,
            f"{preprocessor_symbols}" if preprocessor_symbols else None,
            f"{included_files}" if included_files else None,
            f"{pipeline_context.source_dir}",
        )
        cppcheck_cmd = " ".join(v for v in ("cppcheck", *cppcheck_switches)
                                if v)
        logger.debug("Running cppcheck command: [%s]", cppcheck_cmd)
        p = pipeline_context.run_contextual(cppcheck_cmd, stdout=subprocess.PIPE)
        p.communicate()
        if p.returncode == 0 and os.path.exists(f"{cppcheck_dir}/cppcheck.txt"):
            with open(f"{cppcheck_dir}/cppcheck.txt", 'r') as f:
                data = f.read().strip().replace(pipeline_context.source_dir, "")
                if len(data) > cppcheck_args.fail_count:
                    return ActionResult(action_type=self.action_type,
                                        result=[data],
                                        result_code=ActionResultCode.FAILURE)
                return ActionResult(action_type=self.action_type,
                                    result=[],
                                    result_code=ActionResultCode.SUCCESS)
        return ActionResult(action_type=self.action_type,
                            result=[f"Failed to run cppcheck [{p.returncode}]"],
                            result_code=ActionResultCode.FAILURE)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        cppcheck_dir = backends_context.attribute(backend.backend_name(),
                                                  "cppcheck_dir",
                                                  tag=pipeline_context.name)
        if os.path.exists(f"{cppcheck_dir}/cppcheck.txt"):
            os.remove(f"{cppcheck_dir}/cppcheck.txt")

    @property
    def action_type(self) -> ActionType:
        return ActionType.CodeChecks
