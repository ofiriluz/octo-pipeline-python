import os
import traceback
from typing import Optional

import git

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.git.models import GitModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class GitMirror(Action):
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
            git_args: GitModel = backend.backend_args(backends_context,
                                                      pipeline_context,
                                                      workspace_context,
                                                      self.action_type,
                                                      action_name)
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Running mirror action")
            source_dir = backends_context.source_dir(backend, pipeline_context, workspace_context)
            if len(os.listdir(source_dir)) > 0 and git_args.mirror:
                repo = git.Repo(source_dir)
                if all(remote.name != "mirror" for remote in repo.remotes):
                    logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                                f"Adding mirror remote [{git_args.mirror}] into [{source_dir}]")
                    mirror = repo.create_remote("mirror", git_args.mirror)
                    mirror.fetch()
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
        return ActionType.Mirror
