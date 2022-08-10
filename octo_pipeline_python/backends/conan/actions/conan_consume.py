import os
import shutil
import traceback
from collections import defaultdict
from typing import Optional, cast

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


class ConanConsume(Action):
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
        Will execute conan install for each configuration defined for the pipeline
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        from backends.conan import ConanBackend
        from conans.client import conan_api
        from conans.errors import ConanException

        # Execute conan consumption
        conan_client: conan_api.Conan = backends_context.attribute(backend.backend_name(), "conan_client")
        allowed_configurations = backends_context.attribute(backend.backend_name(),
                                                            "conan_dir.configurations",
                                                            tag=pipeline_context.name) or [ConanConfiguration.Debug]
        profile = backends_context.attribute(backend.backend_name(), "profile", tag=pipeline_context.name)
        try:
            results = []
            consumed_packages = defaultdict(dict)
            for configuration in allowed_configurations:
                # Run configuration
                conan_configuration: ConanConfiguration = \
                    ConanConfiguration(configuration)
                logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                            f"Consuming [{configuration}] configuration")
                conan_conf_dir = backends_context.attribute(backend.backend_name(),
                                                            f"conan_dir.{configuration}",
                                                            tag=pipeline_context.name)
                result = conan_client.install(pipeline_context.source_dir,
                                              settings=[f"build_type={conan_configuration.name}"],
                                              profile_names=[profile],
                                              install_folder=conan_conf_dir,
                                              cwd=pipeline_context.source_dir)
                results.append(result)

                if not result["error"]:
                    for package in result["installed"]:
                        consumed_packages[conan_configuration][package["recipe"]["name"]] = {
                            "error": package["recipe"]["error"],
                            "id": package["recipe"]["id"],
                            "name": package["recipe"]["name"],
                            "time": package["recipe"]["time"],
                            "version": package["recipe"]["version"],
                            "package": {
                                "error": package["packages"][0]["error"],
                                "id": package["packages"][0]["id"],
                                "time": package["packages"][0]["time"],
                                **{
                                    p: package["packages"][0]["cpp_info"].get(p, None)
                                    for p in ("bindirs", "includedirs",
                                              "libdirs", "libs", "resdirs",
                                              "rootpath", "version")
                                }
                            },
                        }

            cast(ConanBackend, backend).set_consumed_packages(consumed_packages,
                                                              backends_context)

            return ActionResult(action_type=self.action_type,
                                result=results,
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
        Cleans up the build directory, along with removing conan imports if existed
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        from conans.client import conan_api
        from conans.client.importer import IMPORTS_MANIFESTS
        conan_client: conan_api.Conan = backends_context.attribute(backend.backend_name(), "conan_client")
        allowed_configurations = backends_context.attribute(backend.backend_name(),
                                                            "conan_dir.configurations",
                                                            tag=pipeline_context.name)
        for configuration in allowed_configurations:
            # Cleanup configuration
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Cleanup Consumption of [{configuration}] configuration")
            conan_conf_dir = backends_context.attribute(backend.backend_name(),
                                                        f"conan_dir.{configuration}",
                                                        tag=pipeline_context.name)
            if os.path.exists(os.path.join(conan_conf_dir, IMPORTS_MANIFESTS)):
                conan_client.imports_undo(conan_conf_dir)
            if os.path.exists(conan_conf_dir):
                shutil.rmtree(conan_conf_dir)

    @property
    def action_type(self) -> ActionType:
        return ActionType.Consume
