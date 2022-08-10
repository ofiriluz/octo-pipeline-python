import os
import shutil
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


class GitSource(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        source_dir = os.path.join(pipeline_context.source_dir, "source")
        if not os.path.exists(source_dir):
            os.makedirs(source_dir)
        backends_context.add_attribute(backend.backend_name(),
                                       "source_dir", source_dir,
                                       tag=pipeline_context.name)
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
                        f"Running source action")
            source_dir = backends_context.attribute(backend.backend_name(), "source_dir", tag=pipeline_context.name)
            if len(os.listdir(source_dir)) == 0:
                logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                            f"Cloning repo [{pipeline_context.scm}] into [{source_dir}]")
                kwargs = {}
                if git_args.shallow:
                    kwargs['depth'] = 1
                if git_args.recursive:
                    kwargs['recursive'] = True
                repo = git.Repo.clone_from(pipeline_context.scm, source_dir, **kwargs)
            else:
                logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                            f"Path [{source_dir}] already exists, will use the existing folder")
                repo = git.Repo(source_dir)
            repo.git.checkout(git_args.head)
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
        source_dir = backends_context.attribute(backend.backend_name(),
                                                "source_dir",
                                                tag=pipeline_context.name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Cleaning source action")
        if os.path.exists(source_dir):
            shutil.rmtree(source_dir)
        return None

    @property
    def action_type(self) -> ActionType:
        return ActionType.Source
