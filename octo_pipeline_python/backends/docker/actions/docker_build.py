import traceback
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.docker.models.docker_model import \
    DockerModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class DockerBuild(Action):
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
        from docker.client import DockerClient
        docker_args: DockerModel = backend.backend_args(backends_context,
                                                        pipeline_context,
                                                        workspace_context,
                                                        self.action_type,
                                                        action_name)
        args = {}
        tag = pipeline_context.name
        if docker_args.args:
            args = docker_args.args
        if docker_args.tag:
            tag = docker_args.tag
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running build action")
        try:
            client: DockerClient = backends_context.attribute(backend.backend_name(), "docker_client")
            image, logs = client.images.build(
                path=pipeline_context.source_dir,
                tag=tag,
                buildargs=args
            )
            if docker_args.verbose:
                for log in logs:
                    logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                                f"${log}")
            return ActionResult(action_type=self.action_type,
                                result=[],
                                result_code=ActionResultCode.SUCCESS)
        except Exception as e:
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
        return ActionType.Build
