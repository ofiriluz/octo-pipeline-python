import os
from typing import Dict, List, Optional, Tuple, Union

import yaml

from octo_pipeline_python.backends.backend_settings import BackendSettings
from octo_pipeline_python.common.surrounding import Surrounding
from octo_pipeline_python.pipeline.pipeline import Pipeline
from octo_pipeline_python.pipeline.pipeline_builder import PipelineBuilder
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.utils.search import PIPELINE_FOLDER, Search
from octo_pipeline_python.workspace.workspace import Workspace
from octo_pipeline_python.workspace.workspace_context import (WorkspaceContext,
                                                              WorkspaceStats)
from octo_pipeline_python.workspace.workspace_pipeline import WorkspacePipeline

WORKSPACE_FILE_NAME = "workspace.yml"
REQUIRED_KEYS = ["name", "scm", "organizations", "workspace"]


class WorkspaceBuilder:
    @staticmethod
    def __get_organizations(workspace_yaml: Dict) -> List[str]:
        """
        Getter for the organizations per yaml
        :param workspace_yaml:
        :return:
        """
        organizations = []
        if 'organizations' in workspace_yaml:
            organizations.extend(workspace_yaml['organizations'])
        elif 'organization' in workspace_yaml:
            organizations.append(workspace_yaml['organization'])
        return organizations

    @staticmethod
    def __get_needs(value: Union[Dict, str]) -> Tuple[str, ...]:
        """
        Getter for the pipeline needs per value
        :param value:
        :return:
        """
        needs = []
        if isinstance(value, Dict) and 'needs' in value:
            needs.extend(value['needs'])
        return tuple(needs)

    @staticmethod
    def __get_branch(value: Union[Dict, str]) -> str:
        """
        Getter for the pipeline head branch per value
        :param value:
        :return:
        """
        head = 'master'
        if isinstance(value, Dict) and 'head' in value and value['head']:
            head = value['head']
        return head

    @staticmethod
    def __get_workspace_executable(value: Union[Dict, str], workspace_executable: bool) -> bool:
        """
        Getter for if the pipeline is workspace buildable
        :param value:
        :return:
        """
        if isinstance(value, Dict) and 'executable' in value and isinstance(value['executable'], bool):
            workspace_executable = value['executable']
        return workspace_executable

    @staticmethod
    def __get_workspace_external(value: Union[Dict, str], workspace_external: bool) -> bool:
        """
        Getter for if the pipeline is workspace external
        :param value:
        :return:
        """
        if isinstance(value, Dict) and 'external' in value and isinstance(value['external'], bool):
            workspace_external = value['external']
        return workspace_external

    @staticmethod
    def __get_workspace(workspace_yaml: Union[str, List, Dict], context: WorkspaceContext, path_prefix: str = "",
                        workspace_executable: bool = True, workspace_external: bool = False) -> \
            Dict[str, List[WorkspacePipeline]]:
        """
        Getter for the workspace per yaml
        Will parse the workspace recursively per directories
        :param workspace_yaml:
        :param context:
        :param path_prefix:
        :param workspace_executable:
        :param workspace_external:
        :return:
        """
        workspace: Dict[str, List[WorkspacePipeline]] = {path_prefix: []}
        for workspace_item in workspace_yaml:
            if isinstance(workspace_item, Dict) and "executable" in workspace_item.keys() and len(workspace_item) == 1:
                workspace_executable = workspace_item["executable"]
            elif isinstance(workspace_item, Dict) and "external" in workspace_item.keys() and len(workspace_item) == 1:
                workspace_external = workspace_item["external"]
            elif isinstance(workspace_item, List):
                workspace.update(WorkspaceBuilder.__get_workspace(workspace_item, context,
                                                                  path_prefix, workspace_executable))
            elif isinstance(workspace_item, Dict):
                for key, value in workspace_item.items():
                    if (isinstance(value, Dict) and "needs" in value or "head" in value) or isinstance(value, str):
                        # New item
                        workspace[path_prefix].append(
                            WorkspacePipeline(name=key,
                                              needs=WorkspaceBuilder.__get_needs(value),
                                              head=WorkspaceBuilder.__get_branch(value),
                                              path=path_prefix,
                                              executable=WorkspaceBuilder.__get_workspace_executable(value,
                                                                                                     workspace_executable),
                                              external=WorkspaceBuilder.__get_workspace_external(value,
                                                                                                 workspace_external)))
                    elif isinstance(value, List):
                        workspace.update(WorkspaceBuilder.__get_workspace(value, context,
                                                                          os.path.join(path_prefix, key)))
            elif isinstance(workspace_item, str):
                workspace[path_prefix].append(
                    WorkspacePipeline(name=workspace_item,
                                      needs=WorkspaceBuilder.__get_needs(workspace_item),
                                      head=WorkspaceBuilder.__get_branch(workspace_item),
                                      path=path_prefix,
                                      executable=WorkspaceBuilder.__get_workspace_executable(workspace_item,
                                                                                             workspace_executable),
                                      external=WorkspaceBuilder.__get_workspace_external(workspace_item,
                                                                                         workspace_external)))
        return {key: value for key, value in workspace.items() if len(value) > 0}

    @staticmethod
    def __get_surrounding(is_singular: bool) -> Surrounding:
        """
        Getter for the surrounding per workspace
        :param is_singular:
        :return:
        """
        if "JENKINS_HOME" in os.environ and "JENKINS_URL" in os.environ:
            return Surrounding.Jenkins
        if is_singular:
            return Surrounding.Local
        return Surrounding.Workspace

    @staticmethod
    def create_singular_workspace(source_dir: str = None,
                                  working_dir: str = None,
                                  pipeline: Pipeline = None) -> Optional[Workspace]:
        """
        Creates a workspace with a singular pipeline
        This is used for when we are in the context of a pipeline and not a multi pipeline workspace
        :param source_dir:
        :param working_dir:
        :param pipeline:
        :return:
        """
        if not pipeline:
            pipeline = PipelineBuilder.create(source_dir=source_dir, working_dir=working_dir, ignore_workspace=True)
            if not pipeline:
                logger.warning(f"Cannot create pipeline / workspace")
                return None

        # Create the singular workspace context
        context: WorkspaceContext = WorkspaceContext(name=pipeline.context.name,
                                                     scm=pipeline.context.scm,
                                                     source_dir=pipeline.context.source_dir,
                                                     working_dir=pipeline.context.working_dir,
                                                     surrounding=WorkspaceBuilder.__get_surrounding(True),
                                                     organizations=[],
                                                     settings=None,
                                                     stats=WorkspaceStats(),
                                                     is_singular=True)
        pipeline_workspace_action: WorkspacePipeline = WorkspacePipeline(name=pipeline.context.name,
                                                                         needs=(),
                                                                         head=pipeline.context.head,
                                                                         path=pipeline.context.name,
                                                                         executable=True,
                                                                         external=False)
        workspace: Workspace = Workspace({pipeline.context.name: [pipeline_workspace_action]},
                                         context,
                                         pipeline)
        return workspace

    @staticmethod
    def create(workspace_file_path: str = None,
               settings_file_path: str = None,
               source_dir: str = None) -> Optional[Workspace]:
        """
        Tries to create the workspace object to work on for all the pipelines
        :param workspace_file_path:
        :param settings_file_path:
        :param source_dir:
        :return:
        """
        # Try to find workspace file if not given
        if not workspace_file_path:
            workspace_file_path = Search.search_by_name(WORKSPACE_FILE_NAME, extra_search_paths=[source_dir])
        if not workspace_file_path or not os.path.exists(workspace_file_path):
            # Try and create a singular pipeline
            return WorkspaceBuilder.create_singular_workspace(source_dir=source_dir)
        # Create the source directory
        if not source_dir:
            source_dir = os.path.dirname(workspace_file_path)
            # If inside pipeline folder, act as source directory above
            if os.path.basename(source_dir) == PIPELINE_FOLDER:
                source_dir = os.path.dirname(source_dir)
        # Read the workspace definition
        with open(workspace_file_path, 'r') as workspace_file:
            workspace_yaml = yaml.load(workspace_file, Loader=yaml.FullLoader)
            if any(x not in workspace_yaml for x in REQUIRED_KEYS):
                logger.warning(f"Could not assert workspace, missing keys from {REQUIRED_KEYS}")
                return None

            # Create the context
            working_dir = os.path.join(source_dir, workspace_yaml.get("working-dir", "build"))
            backends_settings, settings_file_path = BackendSettings.create(source_dir,
                                                                           settings_file_path,
                                                                           workspace_yaml)
            context: WorkspaceContext = WorkspaceContext(name=workspace_yaml['name'],
                                                         scm=workspace_yaml['scm'],
                                                         source_dir=source_dir,
                                                         working_dir=working_dir,
                                                         surrounding=WorkspaceBuilder.__get_surrounding(False),
                                                         organizations=WorkspaceBuilder.__get_organizations(
                                                             workspace_yaml),
                                                         backends_settings=backends_settings,
                                                         settings_path=settings_file_path,
                                                         stats=WorkspaceStats(),
                                                         is_singular=False)
            # Create the workspace
            # Path => List of pipelines in that path
            workspace: Dict[str, List[WorkspacePipeline]] = \
                WorkspaceBuilder.__get_workspace(workspace_yaml['workspace'], context, path_prefix=source_dir)
            return Workspace(workspace, context)
