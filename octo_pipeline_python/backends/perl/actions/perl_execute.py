import os
import subprocess
import traceback
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.perl.models import PerlModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class PerlExecute(Action):
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
        try:
            perl_args: PerlModel = backend.backend_args(backends_context,
                                                        pipeline_context,
                                                        workspace_context,
                                                        self.action_type,
                                                        action_name)
            working_dir = os.path.join(pipeline_context.source_dir, perl_args.working_dir) or pipeline_context.source_dir
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Running execute action")
            for perl_command in perl_args.perl_commands:
                p = pipeline_context.run_contextual(
                    f"{perl_args.perl_binary_path} {perl_command}",
                    stdout=subprocess.PIPE if not perl_args.verbose else None,
                    stderr=subprocess.PIPE if not perl_args.verbose else None,
                    cwd=working_dir)
                p.communicate()
                if p.returncode != 0 and not perl_args.ignore_failures:
                    return ActionResult(action_type=self.action_type,
                                        result=[f"Command [{perl_command}] failed to finish with rc [{p.returncode}]"],
                                        result_code=ActionResultCode.FAILURE)
            return ActionResult(action_type=self.action_type,
                                result=[],
                                result_code=ActionResultCode.SUCCESS)
        except (FileNotFoundError, PermissionError) as e:
            return ActionResult(action_type=self.action_type,
                                result=[traceback.format_exc(), str(e)],
                                result_code=ActionResultCode.FAILURE)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        return None

    @property
    def action_type(self) -> ActionType:
        return ActionType.Execute
