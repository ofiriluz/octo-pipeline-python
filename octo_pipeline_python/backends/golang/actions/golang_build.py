import os
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.golang.models import GolangModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class GolangBuild(Action):
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
        golang_args: GolangModel = backend.backend_args(backends_context,
                                                        pipeline_context,
                                                        workspace_context,
                                                        self.action_type,
                                                        action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running build action")
        env = os.environ.copy()
        env.update(**golang_args.env)
        for entrypoint in golang_args.entrypoints:
            p = pipeline_context.run_contextual(
                f"{golang_args.go_path} build {entrypoint}", cwd=pipeline_context.source_dir, env=env)
            p.communicate()
            if p.returncode != 0:
                return ActionResult(action_type=self.action_type,
                                    result=[f"Failed to run go build on [{entrypoint}] [{p.returncode}]"],
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
        return ActionType.Build
