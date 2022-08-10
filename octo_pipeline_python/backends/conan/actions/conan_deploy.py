import traceback
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.conan.models import ConanModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class ConanDeploy(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        """
        Does nothing
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        return True

    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        """
        Will attempt to upload the package to the deployment remote
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        from conans.client import conan_api
        from conans.client.cmd.uploader import UPLOAD_POLICY_FORCE
        from conans.errors import ConanException

        # Execute conan consumption
        conan_args: ConanModel = backend.backend_args(backends_context,
                                                      pipeline_context,
                                                      workspace_context,
                                                      self.action_type,
                                                      action_name)
        conan_client: conan_api.Conan = backends_context.attribute(backend.backend_name(), "conan_client")
        pattern = f"{pipeline_context.name}/{pipeline_context.full_version}@" \
                  f"{pipeline_context.user}/{pipeline_context.head.replace('/', '-')}"
        try:
            # Upload the packages
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Uploading conan pattern [{pattern}]")
            conan_client.upload(pattern,
                                remote_name=conan_args.deploy,
                                all_packages=True,
                                confirm=True,
                                parallel_upload=True,
                                retry=3,
                                policy=UPLOAD_POLICY_FORCE)
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
        Does nothing
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        return None

    @property
    def action_type(self) -> ActionType:
        return ActionType.Deploy
