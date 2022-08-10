import getpass
import os
from typing import Dict, List, Optional

import yaml

from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backend_settings import BackendSettings
from octo_pipeline_python.common.surrounding import Surrounding
from octo_pipeline_python.pipeline.pipeline import Pipeline
from octo_pipeline_python.pipeline.pipeline_action import PipelineAction
from octo_pipeline_python.pipeline.pipeline_context import (PipelineContext,
                                                            PipelineStats)
from octo_pipeline_python.utils.git import GitUtils
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.utils.search import PIPELINE_FOLDER, Search

PIPELINE_FILE_NAME = "pipeline.yml"
REQUIRED_KEYS = ["name", "pipeline"]


class PipelineBuilder:
    @staticmethod
    def __get_working_branch(pipeline_yaml: Dict, source_dir: str) -> Optional[str]:
        """
        Tries to get the branch of the pipeline
        Either from the yaml or from repo investigation
        :param pipeline_yaml:
        :param source_dir:
        :return:
        """
        if 'head' in pipeline_yaml:
            return pipeline_yaml['head']
        if 'BRANCH_NAME' in os.environ:
            return os.environ["BRANCH_NAME"]
        return GitUtils.get_head_branch(source_dir)

    @staticmethod
    def __get_maintainers(pipeline_yaml: Dict):
        """
        Tries to get the maintainers of the pipeline
        :param pipeline_yaml:
        :return:
        """
        maintainers = []
        if 'maintainers' in pipeline_yaml:
            if isinstance(pipeline_yaml['maintainers'], str):
                maintainers.append(pipeline_yaml['maintainers'])
            elif isinstance(pipeline_yaml['maintainers'], list):
                maintainers.extend(pipeline_yaml['maintainers'])
        return maintainers

    @staticmethod
    def __get_surrounding():
        """
        Tries to get the surrounding per env var or local
        :return:
        """
        if "JENKINS_HOME" in os.environ and "JENKINS_URL" in os.environ:
            return Surrounding.Jenkins
        return Surrounding.Local

    @staticmethod
    def __get_version(pipeline_yaml: Dict, source_dir: str):
        """
        Tries to get the version per yaml, or per VERSION file
        :param pipeline_yaml:
        :param source_dir:
        :return:
        """
        if "version" in pipeline_yaml:
            return pipeline_yaml["version"]
        if os.path.exists(os.path.join(source_dir, "VERSION")):
            return open(os.path.join(source_dir, "VERSION"), 'r').read().strip()
        if pipeline_yaml['name'].upper() + "_VERSION" in os.environ:
            return os.environ[pipeline_yaml['name'].upper() + "_VERSION"]
        return None

    @staticmethod
    def __get_build_number(pipeline_yaml: Dict):
        """
        Tries to get the build number per yaml or per env var
        :param pipeline_yaml:
        :return:
        """
        if "build_number" in pipeline_yaml:
            return pipeline_yaml["build_number"]
        if "BUILD_NUMBER" in os.environ:
            return os.environ["BUILD_NUMBER"]
        return "local"

    @staticmethod
    def __get_scm(pipeline_yaml: Dict, source_dir: str):
        """
        Tries to get the scm per the yaml
        if it does not exist, will try and investigate the repo
        :param pipeline_yaml:
        :param source_dir:
        :return:
        """
        if 'scm' in pipeline_yaml:
            return pipeline_yaml['scm']
        return GitUtils.get_scm_for(source_dir)

    @staticmethod
    def __get_user():
        """
        Tries to get the user per the surroundings
        :return:
        """
        surrounding: Surrounding = PipelineBuilder.__get_surrounding()
        if surrounding == Surrounding.Jenkins:
            return "prod"
        return getpass.getuser()

    @staticmethod
    def create(source_dir: str = None,
               working_dir: str = None,
               pipeline_file_path: str = None,
               settings_file_path: str = None,
               pipeline_name: str = None,
               ignore_workspace: bool = False) -> Optional[Pipeline]:
        """
        Tries and create a pipeline
        If pipeline_file_path was not given, will try and look for it with different schemes
        Same for the settings_file_path
        :param source_dir:
        :param working_dir:
        :param pipeline_file_path:
        :param settings_file_path:
        :param pipeline_name:
        :param ignore_workspace:
        :return:
        """
        import octo_pipeline_python.backends.backends

        # Try to find pipeline file if not given
        if not pipeline_file_path:
            pipeline_file_path = Search.search_by_name(PIPELINE_FILE_NAME, extra_search_paths=[source_dir])
            if not pipeline_file_path:
                if ignore_workspace:
                    return None
                from workspace.workspace import Workspace
                from workspace.workspace_builder import WorkspaceBuilder

                # Try to resolve a workspace instead and from that find the current pipeline
                workspace: Workspace = WorkspaceBuilder.create(source_dir=source_dir)
                if not workspace:
                    return None
                elif pipeline_name and pipeline_name in workspace.describe_pipelines(with_groups=False):
                    return PipelineBuilder.create(source_dir=workspace.pipeline_path(pipeline_name))
                else:
                    pipeline_name: Optional[str] = Search.\
                        search_pipeline_name(hints=[source_dir],
                                             possible_pipelines=workspace.describe_pipelines(
                                                 with_groups=False))
                    if pipeline_name:
                        return PipelineBuilder.create(source_dir=workspace.pipeline_path(pipeline_name))
                    return None
        # Make sure it exists
        if not os.path.exists(pipeline_file_path):
            logger.warning(f"Path [{pipeline_file_path}] does not exist")
            return None
        if not source_dir:
            # Set the source dir based on the pipeline file path
            source_dir = os.path.dirname(pipeline_file_path)
            # If inside pipeline folder, act as source directory above
            if os.path.basename(source_dir) == PIPELINE_FOLDER:
                source_dir = os.path.dirname(source_dir)
        # Read the pipeline
        with open(pipeline_file_path, 'r') as pipeline_file:
            pipeline_yaml = yaml.load(pipeline_file, Loader=yaml.FullLoader)
            if any(x not in pipeline_yaml for x in REQUIRED_KEYS):
                logger.warning(f"Could not assert pipeline, missing keys from {REQUIRED_KEYS}")
                return None

            # Create the context
            if not working_dir:
                working_dir = os.path.join(source_dir, pipeline_yaml.get("working-dir", "build"))
            backends_settings, settings_file_path = BackendSettings.create(source_dir,
                                                                           settings_file_path,
                                                                           pipeline_yaml)
            context: PipelineContext = PipelineContext(name=pipeline_yaml['name'],
                                                       scm=PipelineBuilder.__get_scm(pipeline_yaml,
                                                                                     source_dir),
                                                       version=PipelineBuilder.__get_version(pipeline_yaml,
                                                                                             source_dir),
                                                       build_number=PipelineBuilder.__get_build_number(pipeline_yaml),
                                                       maintainers=PipelineBuilder.__get_maintainers(pipeline_yaml),
                                                       head=PipelineBuilder.__get_working_branch(pipeline_yaml,
                                                                                                   source_dir),
                                                       source_dir=source_dir,
                                                       working_dir=working_dir,
                                                       surrounding=PipelineBuilder.__get_surrounding(),
                                                       user=PipelineBuilder.__get_user(),
                                                       stats=PipelineStats(),
                                                       backends_settings=backends_settings,
                                                       settings_path=settings_file_path)

            # Create the pipeline
            pipeline: List[PipelineAction] = []
            for action_group in pipeline_yaml["pipeline"]:
                for action_type_name in action_group.keys():
                    if action_type_name not in ActionType._value2member_map_.keys():
                        logger.warning(f"Action with name [{action_type_name}] is invalid")
                        return None
                    action = action_group[action_type_name]
                    action_type: ActionType = ActionType._value2member_map_[action_type_name]
                    action_name = action.get("name", None)
                    backends: List[str] = []
                    if 'backend' in action:
                        backends.append(action['backend'])
                    if 'backends' in action:
                        backends.extend(action['backends'])
                    if len(backends) == 0:
                        logger.warning(f"Action [{action_type_name}] must have at least one backend")
                        return None
                    if any(backend not in [s.backend_name() for s in Backend.__subclasses__()] for backend in backends):
                        logger.warning(f"Some of the backends are invalid [{backends}]")
                        return None
                    if 'surroundings' not in action:
                        logger.warning(f"At least one surrounding must exist for action [{action_type_name}]")
                        return None
                    surroundings_str: List[str] = action['surroundings']
                    if any(s not in Surrounding._value2member_map_ for s in surroundings_str):
                        logger.warning(f"Some of surroundings are invalid [{surroundings}]")
                        return None
                    surroundings: List[Surrounding] = [Surrounding._value2member_map_[s] for s in surroundings_str]
                    pipeline.append(PipelineAction(action_type=action_type,
                                                   backends=backends,
                                                   surroundings=surroundings,
                                                   action_name=action_name))
            return Pipeline(context, pipeline)
