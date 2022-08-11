import os
import shutil
import traceback
from datetime import datetime
from threading import RLock
from typing import Any, Dict, Optional, Set

from overrides import overrides

from octo_pipeline_python.actions.action_result import ActionResultCode
from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backend_auth_details import \
    BackendAuthDetails
from octo_pipeline_python.backends.backend_description import \
    BackendDescription
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.conan.actions import (ConanBuild,
                                                         ConanConsume,
                                                         ConanDeploy,
                                                         ConanInstall,
                                                         ConanPackage,
                                                         ConanSource,
                                                         ConanUnitTests)
from octo_pipeline_python.backends.conan.models import (ConanConfiguration,
                                                        ConanModel)
from octo_pipeline_python.common.surrounding import Surrounding
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

TAG = "conan"

ConanConfigurationDict = Dict[ConanConfiguration, Dict[str, Any]]


class ConanBackend(Backend):
    def __init__(self) -> None:
        self.__actions = {
            ActionType.Source: ConanSource(),
            ActionType.Consume: ConanConsume(),
            ActionType.Build: ConanBuild(),
            ActionType.UnitTests: ConanUnitTests(),
            ActionType.Install: ConanInstall(),
            ActionType.Package: ConanPackage(),
            ActionType.Deploy: ConanDeploy()
        }
        self.__conan_lock = RLock()

    @staticmethod
    def __configure_conan_env_vars(backends_context: BackendsContext) -> None:
        conan_dir = backends_context.attribute(TAG, "conan_dir")

        # Set the home directory
        os.environ["CONAN_USER_HOME"] = conan_dir

        # Set conan to use v2 mode for newer compiler support
        os.environ["CONAN_V2_MODE"] = "1"

        # Conan trace path
        os.environ["CONAN_TRACE_FILE"] = os.path.join(conan_dir, "conan_log.log")

        # Set color display for jenkins builds
        os.environ['CONAN_COLOR_DISPLAY'] = "1"

        # Add scm to conan data
        os.environ['CONAN_SCM_TO_CONANDATA'] = "1"

        # Coloring
        os.environ['CONAN_COLOR_DISPLAY'] = "1"

    @staticmethod
    def __configure_conan_conf(backends_context: BackendsContext) -> None:
        from conans.client import conan_api
        from conans.client.tools.oss import CpuProperties
        conan_client: conan_api.Conan = backends_context.attribute(TAG, "conan_client")

        # Set parallel download
        conan_client.config_set("general.parallel_download", str(CpuProperties().get_cpus()))

        # Disable conan lock
        conan_client.config_set("general.cache_no_locks", "True")

    @staticmethod
    def __configure_profile(conan_args: ConanModel,
                            backends_context: BackendsContext,
                            pipeline_context: PipelineContext) -> None:
        from conans.client import conan_api
        conan_client: conan_api.Conan = backends_context.attribute(TAG, "conan_client")
        # Create the profile if it doesnt exist
        if pipeline_context.name not in conan_client.profile_list():
            logger.info(f"[{pipeline_context.name}][{TAG}] Creating new profile [{pipeline_context.name}]")
            conan_client.create_profile(pipeline_context.name, detect=True)
        if conan_args.settings:
            # Add settings if set on the arguments
            detected_os = conan_client.get_profile_key(pipeline_context.name, "settings.os")
            for possible_os in conan_args.settings.keys():
                if possible_os.lower() == detected_os.lower():
                    for key, val in conan_args.settings[possible_os].items():
                        if not key.startswith("settings"):
                            key = f"settings.{key}"
                        try:
                            existing_value = str(conan_client.get_profile_key(pipeline_context.name, key))
                            if existing_value == val:
                                continue
                        except Exception as e:
                            pass
                        logger.info(f"[{pipeline_context.name}][{TAG}] Configuring conan setting [{key}={val}]")
                        conan_client.update_profile(pipeline_context.name, key, val)
        backends_context.add_attribute(TAG, "profile", pipeline_context.name, tag=pipeline_context.name)

    @staticmethod
    def __get_artifactory_url(conan_pipeline_args: ConanModel,
                              conan_workspace_args: ConanModel) -> Optional[str]:
        artifactory: Optional[str] = None
        if conan_pipeline_args:
            artifactory = conan_pipeline_args.artifactory
        elif conan_workspace_args:
            artifactory = conan_workspace_args.artifactory
        return artifactory

    @staticmethod
    def __get_remotes(conan_pipeline_args: ConanModel,
                      conan_workspace_args: ConanModel) -> Set[str]:
        remotes = set()
        if conan_pipeline_args and conan_pipeline_args.remotes:
            remotes.update(set(conan_pipeline_args.remotes))
            if conan_pipeline_args.deploy:
                remotes.add(conan_pipeline_args.deploy)
        if conan_workspace_args and conan_workspace_args.remotes:
            remotes.update(set(conan_workspace_args.remotes))
            if conan_workspace_args.deploy:
                remotes.add(conan_workspace_args.deploy)
        return remotes

    @staticmethod
    def __configure_remotes(conan_pipeline_args: ConanModel,
                            conan_workspace_args: ConanModel,
                            backends_context: BackendsContext) -> None:
        from conans.client import conan_api
        conan_client: conan_api.Conan = backends_context.attribute(TAG, "conan_client")
        remote_list = [remote.name for remote in conan_client.remote_list()]
        artifactory = ConanBackend.__get_artifactory_url(conan_pipeline_args, conan_workspace_args)
        # Remove conan center if it doesnt exist
        if conan_pipeline_args.no_default_remotes or conan_workspace_args.no_default_remotes:
            for denied_remote in ["conancenter", "conan-center"]:
                if denied_remote in remote_list:
                    conan_client.remote_remove(denied_remote)
        # Add the remotes
        for remote in ConanBackend.__get_remotes(conan_pipeline_args, conan_workspace_args):
            if remote not in remote_list:
                remote_url = f"{artifactory}/artifactory/api/conan/{remote}"
                logger.info(f"[{TAG}] Adding remote [{remote}] with url [{remote_url}]")
                conan_client.remote_add(remote, remote_url)

    @staticmethod
    def __configure_build_types(conan_pipeline_args: ConanModel,
                                conan_workspace_args: ConanModel,
                                backends_context: BackendsContext,
                                pipeline_context: PipelineContext):
        # Create configuration dirs
        # Default is build only debug
        allowed_configurations = [ConanConfiguration.Debug]
        # Workspace overrides pipeline configuration in this case
        if conan_pipeline_args and conan_pipeline_args.configurations:
            allowed_configurations = conan_pipeline_args.configurations
        if conan_workspace_args and conan_workspace_args.configurations:
            allowed_configurations = conan_workspace_args.configurations
        for configuration in ConanConfiguration:
            if configuration in allowed_configurations:
                conf_conan_dir = os.path.join(pipeline_context.working_dir, "conan",
                                              pipeline_context.name, configuration)
                if not os.path.exists(conf_conan_dir):
                    logger.info(f"[{pipeline_context.name}][{TAG}] Preparing [{configuration}] configuration")
                    os.makedirs(conf_conan_dir)
                backends_context.add_attribute(TAG, f"conan_dir.{configuration}",
                                               conf_conan_dir,
                                               tag=pipeline_context.name)
                backends_context.add_attribute(TAG,
                                               f"conan_dir.{configuration}.build",
                                               os.path.join(conf_conan_dir, "build"),
                                               tag=pipeline_context.name)
                backends_context.add_attribute(TAG,
                                               f"conan_dir.{configuration}.package",
                                               os.path.join(pipeline_context.working_dir,
                                                            "package", pipeline_context.name, configuration),
                                               tag=pipeline_context.name)
        backends_context.add_attribute(TAG,
                                       f"conan_dir.configurations",
                                       allowed_configurations,
                                       tag=pipeline_context.name,
                                       exclude_from_db=True)

    @staticmethod
    def __configure_props_file(backends_context: BackendsContext,
                               pipeline_context: PipelineContext):
        conan_dir = backends_context.attribute(TAG, "conan_dir")
        props = f"artifact_property_build.name={pipeline_context.name}\n" \
                f"artifact_property_build.number={pipeline_context.build_number or 0}\n" \
                f"artifact_property_build.timestamp={datetime.now().timestamp()}"
        with open(os.path.join(conan_dir, '.conan', 'artifacts.properties'), 'w') as f:
            f.write(props)

    @staticmethod
    def __authenticate_to_remote(backends_context: BackendsContext,
                                 auth_details: BackendAuthDetails, remote: str) -> bool:
        from conans.client import conan_api
        from conans.errors import ConanException
        try:
            # Try and authenticate to the remote
            conan_client: conan_api.Conan = backends_context.attribute(TAG, "conan_client")
            remote_name, _, user = conan_client.authenticate(auth_details.username,
                                                             auth_details.secret.get_secret_value(),
                                                             remote)
            if remote_name and user:
                return True
        except ConanException as e:
            logger.exception(f"[{TAG}] Failed to authenticate to remote [{remote}] - [{str(e)}]")
        return False

    @staticmethod
    def __configure_certificate(backends_context: BackendsContext,
                                auth_details: BackendAuthDetails):
        if auth_details.certificate:
            if os.path.exists(auth_details.certificate):
                certificate_data = open(auth_details.certificate, 'r').read()
                conan_dir = backends_context.attribute(TAG, "conan_dir")
                cacert_path = os.path.join(conan_dir, ".conan", "cacert.pem")
                if os.path.exists(cacert_path):
                    cacert_data = open(cacert_path, 'r').read()
                    if certificate_data not in cacert_data:
                        logger.info(f"Editing certificate file [{cacert_path}] and adding "
                                    f"[{auth_details.certificate}] to it")
                        with open(cacert_path, 'a') as cacert_file:
                            cacert_file.write(f"\n{certificate_data}\n")
            else:
                logger.warning(f"Certificate path [{auth_details.certificate} does not exist]")

    def initialize_backend(self,
                           backends_context: BackendsContext,
                           workspace_context: WorkspaceContext) -> bool:
        from conans.client import conan_api
        from conans.errors import ConanException

        # Make sure the working build dir exists
        conan_dir = os.path.join(workspace_context.working_dir, TAG)
        if "OCTO_CONAN_USER_HOME" in os.environ:
            conan_dir = os.environ["OCTO_CONAN_USER_HOME"]
        if not os.path.exists(conan_dir):
            os.makedirs(conan_dir)
        backends_context.add_attribute(TAG, "conan_dir", conan_dir)

        # Set the conan env vars
        self.__configure_conan_env_vars(backends_context)

        try:
            # Create the conan client
            conan_client = \
                conan_api.Conan(cache_folder=os.path.join(conan_dir, '.conan'))
            conan_client.config_init()

            # Add the client to the context
            backends_context.add_attribute(TAG, "conan_client", conan_client,
                                           exclude_from_db=True)

            # Set configurations
            self.__configure_conan_conf(backends_context)
        except ConanException as e:
            logger.exception(f"[{TAG}] Could not initialize conan backend - [{str(e)}]")
            return False

        if backends_context.has_attribute(TAG, "consumed_packages"):
            # Get and set to update any new `ConanConfiguration` values.
            self.set_consumed_packages(
                    self.get_consumed_packages(backends_context),
                    backends_context)
        else:
            self.set_consumed_packages({}, backends_context)

        return True

    def authenticate_backend(self, auth_details: BackendAuthDetails,
                             backends_context: BackendsContext,
                             workspace_context: WorkspaceContext,
                             pipeline_context: Optional[PipelineContext]) -> ActionResultCode:
        from conans.client import conan_api
        conan_pipeline_args: ConanModel = self.backend_args(backends_context,
                                                            pipeline_context,
                                                            workspace_context)
        conan_workspace_args: ConanModel = self.backend_args(backends_context,
                                                             None,
                                                             workspace_context)
        artifactory: Optional[str] = ConanBackend.__get_artifactory_url(conan_pipeline_args, conan_workspace_args)
        pipeline_tag = ''
        if pipeline_context:
            pipeline_tag = f"[{pipeline_context.name}]"
        if not artifactory:
            logger.warning(f"{pipeline_tag}[{TAG}] Cannot retrieve arguments for authentication")
            return ActionResultCode.FAILURE
        conan_client: conan_api.Conan = backends_context.attribute(TAG, "conan_client")
        # Add certificate if present
        self.__configure_certificate(backends_context, auth_details)
        # Authenticate to remotes
        remotes = set()
        if auth_details.target:
            remotes.add(auth_details.target)
        else:
            remotes = ConanBackend.__get_remotes(conan_pipeline_args, conan_workspace_args)
        existing_remotes = conan_client.remote_list()
        for remote in remotes:
            if all(existing_remote.name != remote for existing_remote in existing_remotes):
                logger.info(f"{pipeline_tag}[{TAG}] Remote [{remote}] does not exist in remote list, adding it")
                remote_url = f"{artifactory}/artifactory/api/conan/{remote}"
                conan_client.remote_add(remote, remote_url)
            if not self.__authenticate_to_remote(backends_context, auth_details, remote):
                logger.error(f"{pipeline_tag}[{TAG}] Failed to authenticate to remote [{remote}]")
                return ActionResultCode.FAILURE
            else:
                logger.info(f"{pipeline_tag}[{TAG}] Authenticated Successfully to remote [{remote}]")
        return ActionResultCode.SUCCESS

    def cleanup_backend(self,
                        backends_context: BackendsContext,
                        workspace_context: WorkspaceContext) -> None:
        conan_dir = backends_context.attribute(TAG, "conan_dir")
        if os.path.exists(os.path.join(conan_dir, ".conan")):
            shutil.rmtree(os.path.join(conan_dir, ".conan"))
        if len(os.listdir(conan_dir)) == 0:
            os.rmdir(conan_dir)

    def describe_backend(self,
                         backends_context: BackendsContext,
                         workspace_context: WorkspaceContext) -> BackendDescription:
        return BackendDescription(name=TAG,
                                  working_dir=os.path.join(workspace_context.working_dir, TAG),
                                  actions=self.__actions,
                                  backend_model=ConanModel)

    @staticmethod
    def backend_name() -> str:
        return TAG

    @overrides
    def initialize_backend_pipeline_action(self,
                                           action_type: ActionType,
                                           backends_context: BackendsContext,
                                           pipeline_context: PipelineContext,
                                           workspace_context: WorkspaceContext,
                                           action_name: Optional[str]) -> bool:
        self.__conan_lock.acquire()
        try:
            conan_args: ConanModel = self.backend_args(backends_context,
                                                       pipeline_context,
                                                       workspace_context)
            conan_pipeline_args: ConanModel = self.backend_args(backends_context,
                                                                pipeline_context,
                                                                workspace_context)
            conan_workspace_args: ConanModel = self.backend_args(backends_context,
                                                                 None,
                                                                 workspace_context)

            # Configure conan profile
            self.__configure_profile(conan_args, backends_context, pipeline_context)

            # Configure conan env vars
            self.__configure_conan_env_vars(backends_context)

            # Configure build types for the action
            self.__configure_build_types(conan_pipeline_args, conan_workspace_args,
                                         backends_context, pipeline_context)

            # Configure the remotes for this action
            self.__configure_remotes(conan_pipeline_args, conan_workspace_args, backends_context)

            # Add artifacts props
            if workspace_context.surrounding == Surrounding.Jenkins:
                self.__configure_props_file(backends_context, pipeline_context)

            return super().initialize_backend_pipeline_action(action_type,
                                                              backends_context,
                                                              pipeline_context,
                                                              workspace_context,
                                                              action_name)
        finally:
            self.__conan_lock.release()

    @staticmethod
    def __populate_consumed_packages(consumed_packages: ConanConfigurationDict) \
            -> ConanConfigurationDict:
        for configuration in ConanConfiguration.__members__.values():
            if configuration not in consumed_packages:
                consumed_packages[configuration] = {}
        return consumed_packages

    @staticmethod
    def get_consumed_packages(backends_context: Optional[BackendsContext]) \
            -> ConanConfigurationDict:
        if backends_context.has_attribute(TAG, "consumed_packages"):
            res = backends_context.attribute(TAG, "consumed_packages")
        else:
            res = ConanBackend.__populate_consumed_packages({})
            ConanBackend.set_consumed_packages(res, backends_context)

        return res.copy()

    @staticmethod
    def set_consumed_packages(consumed_packages: ConanConfigurationDict,
                              backends_context: BackendsContext) -> None:
        backends_context.add_attribute(
                TAG,
                "consumed_packages",
                ConanBackend.__populate_consumed_packages(consumed_packages))
