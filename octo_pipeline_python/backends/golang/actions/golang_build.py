import os
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.golang.models import (GolangEntrypointInfo,
                                                         GolangModel)
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
        build_dir = os.path.join(pipeline_context.working_dir, "golang")
        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running build action")
        env = os.environ.copy()
        env.update(**golang_args.env)
        extra_args = ''
        if golang_args.mod_path:
            extra_args = f'-modfile {golang_args.mod_path}'
        for entrypoint in golang_args.entrypoints:
            entrypoint_path = entrypoint
            output_path = build_dir
            if isinstance(entrypoint, GolangEntrypointInfo):
                entrypoint_path = entrypoint.path
                if entrypoint.output_name:
                    output_path = os.path.join(output_path, entrypoint.output_name)
            logger.info(f'Running go build on entrypoint [{entrypoint_path}] outputted to [{output_path}]')
            p = pipeline_context.run_contextual(
                f"{golang_args.go_path} build -o {output_path} {extra_args} {entrypoint_path}", cwd=pipeline_context.source_dir, env=env)
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
