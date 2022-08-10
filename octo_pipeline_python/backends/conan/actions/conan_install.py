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


class ConanInstall(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        """
        Does Nothing
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
        Executes conan build only with install
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        from conans.client import conan_api
        from conans.errors import ConanException

        # Execute conan build
        conan_client: conan_api.Conan = backends_context.attribute(backend.backend_name(), "conan_client")
        allowed_configurations = backends_context.attribute(backend.backend_name(),
                                                            "conan_dir.configurations",
                                                            tag=pipeline_context.name)
        try:
            for configuration in allowed_configurations:
                # Run configuration
                logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                            f"Installing [{configuration}] configuration")
                conan_conf_dir = backends_context.attribute(backend.backend_name(),
                                                            f"conan_dir.{configuration}",
                                                            tag=pipeline_context.name)
                conan_build_conf_dir = backends_context.attribute(backend.backend_name(),
                                                                  f"conan_dir.{configuration}.build",
                                                                  tag=pipeline_context.name)
                conan_package_conf_dir = backends_context.attribute(backend.backend_name(),
                                                                    f"conan_dir.{configuration}.package",
                                                                    tag=pipeline_context.name)
                conan_client.build(pipeline_context.source_dir,
                                   source_folder=backends_context.source_dir(backend,
                                                                             pipeline_context,
                                                                             workspace_context),
                                   install_folder=conan_conf_dir,
                                   build_folder=conan_build_conf_dir,
                                   package_folder=conan_package_conf_dir,
                                   should_configure=False,
                                   should_build=True,
                                   should_test=False,
                                   should_install=True,
                                   cwd=pipeline_context.source_dir)
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
        Cleans up the packaging folder installed
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        allowed_configurations = backends_context.attribute(backend.backend_name(),
                                                            "conan_dir.configurations",
                                                            tag=pipeline_context.name)
        for configuration in allowed_configurations:
            # Cleanup configuration build
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Cleanup Install of [{configuration}] configuration")
            conan_package_conf_dir = backends_context.attribute(backend.backend_name(),
                                                                f"conan_dir.{configuration}.package",
                                                                tag=pipeline_context.name)
            shutil.rmtree(conan_package_conf_dir)

    @property
    def action_type(self) -> ActionType:
        return ActionType.Install
