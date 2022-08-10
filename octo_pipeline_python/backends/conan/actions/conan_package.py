import shutil
import traceback
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.conan.models.conan_configuration import \
    ConanConfiguration
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class ConanPackage(Action):
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
        Runs conan export package for packing in conan cache dir
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        from conans.client import conan_api
        from conans.errors import ConanException

        # Execute conan export pkg
        conan_client: conan_api.Conan = backends_context.attribute(backend.backend_name(), "conan_client")
        profile = backends_context.attribute(backend.backend_name(), "profile", tag=pipeline_context.name)
        allowed_configurations = backends_context.attribute(backend.backend_name(),
                                                            "conan_dir.configurations",
                                                            tag=pipeline_context.name)
        try:
            for configuration in allowed_configurations:
                # Run configuration
                logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                            f"Running Package for [{configuration}] configuration")
                conan_conf_dir = backends_context.attribute(backend.backend_name(),
                                                            f"conan_dir.{configuration}",
                                                            tag=pipeline_context.name)
                conan_build_conf_dir = backends_context.attribute(backend.backend_name(),
                                                                  f"conan_dir.{configuration}.build",
                                                                  tag=pipeline_context.name)
                conan_package_conf_dir = backends_context.attribute(backend.backend_name(),
                                                                    f"conan_dir.{configuration}.package",
                                                                    tag=pipeline_context.name)
                source_dir = backends_context.source_dir(backend,
                                                         pipeline_context,
                                                         workspace_context)
                conan_client.package(pipeline_context.source_dir,
                                     build_folder=conan_build_conf_dir,
                                     package_folder=conan_package_conf_dir,
                                     source_folder=source_dir,
                                     install_folder=conan_conf_dir,
                                     cwd=pipeline_context.source_dir)
                conan_client.export_pkg(pipeline_context.source_dir,
                                        name=pipeline_context.name,
                                        channel=pipeline_context.head.replace("/", "."),
                                        user=pipeline_context.user,
                                        settings=[f"build_type={ConanConfiguration._value2member_map_[configuration].name}"],
                                        profile_names=[profile],
                                        package_folder=conan_package_conf_dir,
                                        install_folder=conan_conf_dir,
                                        force=True,
                                        version=pipeline_context.full_version,
                                        cwd=source_dir)
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
        Cleans up the exported packages
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name
        :return:
        """
        from conans.client import conan_api
        conan_client: conan_api.Conan = backends_context.attribute(backend.backend_name(), "conan_client")
        allowed_configurations = backends_context.attribute(backend.backend_name(),
                                                            "conan_dir.configurations",
                                                            tag=pipeline_context.name)
        for configuration in allowed_configurations:
            # Cleanup configuration build
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Cleanup Package of [{configuration}] configuration")
            try:
                conan_client.remove(f"{pipeline_context.name}/{pipeline_context.full_version}@"
                                    f"{pipeline_context.user}/{pipeline_context.head.replace('/', '.')}",
                                    query=f"build_type={configuration}")
            except Exception as e:
                logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                            f"Failed to clean [{pipeline_context.name}] "
                            f"for configuration [{configuration}] - [{str(e)}]")
            conan_package_conf_dir = backends_context.attribute(backend.backend_name(),
                                                                f"conan_dir.{configuration}.package",
                                                                tag=pipeline_context.name)
            shutil.rmtree(conan_package_conf_dir)

    @property
    def action_type(self) -> ActionType:
        return ActionType.Package
