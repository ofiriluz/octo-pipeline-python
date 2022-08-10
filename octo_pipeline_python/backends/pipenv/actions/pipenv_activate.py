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


class PIPEnvActivate(Action):
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
        if "VIRTUAL_ENV" in os.environ and os.path.exists(os.path.join(os.environ["VIRTUAL_ENV"], "bin", "activate")):
            logger.info(f"Venv already activated, not creating a new one")
            return ActionResult(action_type=self.action_type,
                                result=["Venv already exists, not creating a new one"],
                                result_code=ActionResultCode.SUCCESS)
        if pipenv_args.venv_path:
            venv_path = pipenv_args.venv_path
        elif "VIRTUAL_ENV" in os.environ:
            venv_path = os.environ["VIRTUAL_ENV"]
        else:
            venv_path = os.path.join(pipeline_context.source_dir, ".venv")

        venv_arguments = " ".join(
                arg for arg in
                (
                    "--system-site-packages"
                    if pipenv_args.system_site_packages else None,
                    "--copies"
                    if pipenv_args.copy_system_site_packages else None,
                    venv_path,
                ) if arg is not None
        )
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running activate action")
        logger.debug("Venv arguments: [%s]", venv_arguments)
        p = subprocess.Popen(f"python3 -m venv {venv_arguments}", shell=True,
                             cwd=pipeline_context.source_dir)
        p.communicate()
        if p.returncode != 0:
            return ActionResult(action_type=self.action_type,
                                result=["Failed to activate pipenv"],
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
        return ActionType.Activate
