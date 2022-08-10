import os
import subprocess
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.pipenv.models import PIPEnvModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class PIPEnvConsume(Action):
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
        pipenv_args: PIPEnvModel = backend.backend_args(backends_context,
                                                        pipeline_context,
                                                        workspace_context,
                                                        self.action_type,
                                                        action_name)
        pipenv_path = os.path.join(pipeline_context.source_dir, pipenv_args.pipenv_path) if pipenv_args.pipenv_path \
            else pipeline_context.source_dir
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running consume action with pipenv path [{pipenv_path}]")
        if not pipenv_args.force and os.path.exists(os.path.join(pipenv_path, "Pipfile.lock")):
            p = subprocess.Popen(f"pipenv sync --dev", shell=True,
                                 cwd=pipenv_path)
        else:
            p = subprocess.Popen(f"pipenv install", shell=True,
                                 cwd=pipenv_path)
        p.communicate()
        if p.returncode != 0:
            return ActionResult(action_type=self.action_type,
                                result=["Failed to consume pipenv"],
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
        return ActionType.Consume
