import os
import shutil
import traceback
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class ConanSource(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        """
        Creates the source directory for conan to work with
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        src_path = os.path.join(pipeline_context.working_dir, "source")
        if not os.path.exists(src_path):
            os.makedirs(src_path)
        backends_context.add_attribute(backend.backend_name(),
                                       "source_dir", src_path, tag=pipeline_context.name)
        return True

    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        """
        Runs the conan source action
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        from conans.client import conan_api
        from conans.errors import ConanException

        # Execute conan source
        conan_client: conan_api.Conan = backends_context.attribute(backend.backend_name(), "conan_client")
        try:
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Running Source action")
            conan_client.source(pipeline_context.source_dir,
                                source_folder=backends_context.source_dir(backend,
                                                                          pipeline_context,
                                                                          workspace_context))
            return ActionResult(action_type=self.action_type,
                                result=[],
                                result_code=ActionResultCode.SUCCESS)
        except ConanException as e:
            return ActionResult(action_type=self.action_type,
                                result=[traceback.format_exc(), str(e)],
                                result_code=ActionResultCode.FAILURE)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        """
        Removes the source directory created
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Cleaning Source action")
        shutil.rmtree(backends_context.source_dir(backend,
                                                  pipeline_context,
                                                  workspace_context))

    @property
    def action_type(self) -> ActionType:
        return ActionType.Source
