import json
import os
from io import TextIOWrapper
from typing import Dict, List, Optional, cast

from overrides import overrides

from octo_pipeline_python.actions.action_result import ActionResultCode
from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backend_auth_details import \
    BackendAuthDetails
from octo_pipeline_python.backends.backend_description import \
    BackendDescription
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.cdk.actions import (CDKBuild, CDKBuildLayer,
                                                       CDKDeploy, CDKDestroy)
from octo_pipeline_python.backends.cdk.models import CDKModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

TAG = "cdk"


class CDKBackend(Backend):
    def __init__(self) -> None:
        self.__actions = {
            ActionType.Build: CDKBuild(),
            ActionType.Deploy: CDKDeploy(),
            ActionType.Destroy: CDKDestroy(),
            ActionType.Layer: CDKBuildLayer()
        }

    def initialize_backend(self,
                           backends_context: BackendsContext,
                           workspace_context: WorkspaceContext) -> bool:
        return True

    def cleanup_backend(self,
                        backends_context: BackendsContext,
                        workspace_context: WorkspaceContext) -> None:
        return None

    def authenticate_backend(self,
                             auth_details: BackendAuthDetails,
                             backends_context: BackendsContext,
                             workspace_context: WorkspaceContext,
                             pipeline_context: Optional[PipelineContext]) -> ActionResultCode:
        return ActionResultCode.SUCCESS

    def describe_backend(self,
                         backends_context: BackendsContext,
                         workspace_context: WorkspaceContext) -> BackendDescription:
        return BackendDescription(name=TAG,
                                  working_dir=os.path.join(workspace_context.working_dir, TAG),
                                  actions=self.__actions,
                                  backend_model=CDKModel)

    @staticmethod
    def backend_name() -> str:
        return TAG

    @staticmethod
    def __write_dependencies(f: TextIOWrapper, data: Dict, dependency_type: str,
                             subset_dependencies: Optional[List[str]]):
        if subset_dependencies:
            diff = list(set(subset_dependencies) - set(data[dependency_type]))
            if len(diff):
                logger.warning(f'Dependencies {diff} were not found in Pipfile.lock in \'{dependency_type}\' section')
        for dependency in data[dependency_type]:
            if subset_dependencies and dependency not in subset_dependencies:
                continue
            dependency_section = data[dependency_type][dependency]
            if "git" in dependency_section:
                git_string = f"git+{dependency_section['git']}@{dependency_section['ref']}#egg={dependency}"
                f.write(f"-e {git_string}\n") if "editable" in dependency_section else f.write(git_string + "\n")
            elif 'version' in dependency_section:
                if "markers" in dependency_section and dependency_section['markers'] is not None:
                    f.write(f"{dependency}{dependency_section['version']} ; {dependency_section['markers']}\n")
                else:
                    f.write(f"{dependency}{dependency_section['version']}\n")

    @overrides
    def initialize_backend_pipeline_action(self,
                                           action_type: ActionType,
                                           backends_context: BackendsContext,
                                           pipeline_context: PipelineContext,
                                           workspace_context: WorkspaceContext,
                                           action_name: Optional[str]) -> bool:
        cdk_args: CDKModel = self.backend_args(backends_context,
                                               pipeline_context,
                                               workspace_context,
                                               action_type,
                                               action_name)
        # Create the cdk working dir
        cdk_working_dir = os.path.join(pipeline_context.working_dir, TAG)
        if cdk_args.working_dir:
            cdk_working_dir = cdk_args.working_dir
        if not os.path.exists(cdk_working_dir):
            os.makedirs(cdk_working_dir)
        backends_context.add_attribute(TAG, "cdk_working_dir", cdk_working_dir, tag=pipeline_context.name)
        backends_context.add_attribute(TAG, "cdk_requirements", os.path.join(cdk_working_dir, "cdk_requirements.txt"),
                                       tag=pipeline_context.name)

        # Create a requirements.txt for cdk if Pipfile.lock exists
        base_pip_path = pipeline_context.source_dir
        if cdk_args.pipenv_path:
            base_pip_path = os.path.join(base_pip_path, cdk_args.pipenv_path)
        if os.path.exists(os.path.join(base_pip_path, "Pipfile.lock")):
            with open(os.path.join(base_pip_path, "Pipfile.lock")) as json_file:
                data = json.load(json_file)
            with open(os.path.join(cdk_working_dir, "cdk_requirements.txt"), "w") as f:
                index = 0
                for source in data['_meta']['sources']:  # sets the pypi server path
                    if index == 0:
                        f.write(f"-i {source['url']}\n")
                    else:
                        f.write(f"--extra-index-url {source['url']}\n")
                    index += 1
                if cdk_args.external_dependencies:
                    for dep in cdk_args.external_dependencies:
                        f.write(f"{dep}\n")

                CDKBackend.__write_dependencies(cast(TextIOWrapper, f), data, "default", cdk_args.runtime_dependencies)
                if cdk_args.development:
                    CDKBackend.__write_dependencies(cast(TextIOWrapper, f), data, "develop", cdk_args.dev_dependencies)

        return super().initialize_backend_pipeline_action(action_type,
                                                          backends_context,
                                                          pipeline_context,
                                                          workspace_context,
                                                          action_name)
