from typing import Optional

from utils.logger import logger

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.cdk.common.cdk_env import CDKEnv
from octo_pipeline_python.backends.cdk.models import CDKModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class CDKDestroy(Action):
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
        cdk_args: CDKModel = backend.backend_args(backends_context,
                                                  pipeline_context,
                                                  workspace_context,
                                                  self.action_type,
                                                  action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running destroy action")
        CDKEnv.load_dotenv(pipeline_context, cdk_args.deploy_env, cdk_args.deployment_env_vars)
        p = pipeline_context.run_contextual(f"cdk destroy -f",
                                            cwd=pipeline_context.source_dir)
        p.communicate()
        if p.returncode != 0:
            return ActionResult(action_type=self.action_type,
                                result=["Failed to destroy environment"],
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
        return ActionType.Destroy
