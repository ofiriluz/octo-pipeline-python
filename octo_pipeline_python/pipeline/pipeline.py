import os
import shutil
from datetime import datetime
from typing import List, Optional, Tuple, Union

from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.common.surrounding import Surrounding
from octo_pipeline_python.pipeline.pipeline_action import PipelineAction
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.pipeline.pipeline_database import PipelineDatabase
from octo_pipeline_python.pipeline.pipeline_description import \
    PipelineDescription
from octo_pipeline_python.utils.git import GitUtils
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class Pipeline:
    """
    Class responsible for describing the pipeline
    The pipeline may be described with yml files with a set of actions to run
    """
    def __init__(self, context: PipelineContext, actions: List[PipelineAction]):
        self.__context = context
        self.__actions = actions
        self.__partial_success_results: List[ActionResult] = []
        self.__db = PipelineDatabase(self.__context, self.describe_pipeline())
        self.__is_initialized = False
        if self.__db.contains("stats"):
            self.__context.stats = self.__db.get("stats")

    @staticmethod
    def init_pipeline_to(organizations: List[str],
                         name: str,
                         scm: str,
                         to_path: str,
                         head: str = "master",
                         ignore_workspace: bool = False,
                         external: bool = False) -> Optional["Pipeline"]:
        """
        Tries to initialize a pipeline to a given path
        :param organizations:
        :param name:
        :param scm:
        :param to_path:
        :param head:
        :param ignore_workspace:
        :param external:
        :return:
        """
        from pipeline.pipeline_builder import PipelineBuilder
        if not os.path.exists(to_path):
            os.makedirs(to_path)
        if len(os.listdir(to_path)) > 0:
            if GitUtils.checkout_to_branch(to_path, head):
                if external:
                    return None
                return PipelineBuilder.create(to_path, ignore_workspace=ignore_workspace)
        for org in organizations:
            repo_scm = GitUtils.clone_and_checkout(scm, org, name, to_path, head)
            if repo_scm:
                if external:
                    return None
                pipeline: Pipeline = PipelineBuilder.create(to_path, ignore_workspace=ignore_workspace)
                if pipeline:
                    logger.info(f"[{pipeline.context.name}] Using [{repo_scm}] on [{to_path}] as the repo for [{name}]")
                    return pipeline
                else:
                    shutil.rmtree(to_path)
                    os.makedirs(to_path)
        return None

    @property
    def context(self) -> PipelineContext:
        """
        Getter for the pipeline context
        :return: PipelineContext
        """
        return self.__context

    @property
    def actions(self) -> List[PipelineAction]:
        """
        Getter for the pipeline actions
        :return: List[PipelineAction]
        """
        return self.__actions

    @property
    def completed(self) -> bool:
        """
        Checks if the pipeline completed all its actions
        :return:
        """
        return not self.__db.has_steps

    @property
    def failed(self) -> bool:
        """
        Checks if the pipeline failed already
        :return:
        """
        return self.__db.dirty

    def initialize_pipeline(self,
                            backends_context: BackendsContext,
                            workspace_context: WorkspaceContext) -> bool:
        """
        Initializes the pipeline with all the backends
        :param backends_context:
        :param workspace_context:
        :return:
        """
        if self.__is_initialized:
            logger.info(f"[{self.context.name}] Pipeline is already initialized")
            return True
        # Initialize the actions backends
        for action in self.__actions:
            if self.__context.surrounding not in action.surroundings:
                continue
            for backend in action.backends:
                if not backends_context.initialize_backend(backend, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend [{backend}]")
                    return False
        self.__is_initialized = True
        return True

    def execute_pipeline_action(self, action_type_name: Union[ActionType, str],
                                backends_context: BackendsContext,
                                workspace_context: WorkspaceContext) -> ActionResultCode:
        """
        Executes a given action on the pipeline
        If there are multiple actions of this type, they will all run in order
        If a backend was not initialized yet, will also try and initialize the backend
        :param action_type_name:
        :param backends_context:
        :param workspace_context:
        :return: bool
        """
        # Create the working dir
        if not os.path.exists(self.context.working_dir):
            os.makedirs(self.context.working_dir)
        if not os.path.exists(os.path.join(self.context.working_dir, ".cache")):
            os.makedirs(os.path.join(self.context.working_dir, ".cache"))
        result = ActionResultCode.SUCCESS
        for action in self.__actions:
            if self.__context.surrounding not in action.surroundings and \
               Surrounding.OnDemand not in action.surroundings:
                logger.info(f"[{self.context.name}] Action [{action.action_type}] Does not fit surrounding "
                            f"[{self.__context.surrounding}], Ignoring")
                continue
            if action.action_type != action_type_name and action.action_name != action_type_name:
                continue
            for backend in action.backends:
                if self.__db.is_step_disabled(action.action_type.value,
                                              backend,
                                              "execute-action") or \
                        action.action_name and self.__db.is_step_disabled(action.action_name,
                                                                          backend,
                                                                          "execute-action"):
                    logger.info(f"[{self.context.name}] Action [{action.action_type}] "
                                f"from backend [{backend}] is disabled in execute action" +
                                (f" for action name [{action.action_name}]" if action.action_name else ""))
                    continue
                if not backends_context.initialize_backend(backend, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend [{backend}]")
                    return ActionResultCode.FAILURE
                if not backends_context.initialize_pipeline_backend_action(backend, action,
                                                                           self.__context, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend "
                                 f"[{backend}] for action [{action.action_type}]")
                    return ActionResultCode.FAILURE
                action_result = backends_context.execute_pipeline_backend_action(backend, action,
                                                                                 self.__context, workspace_context)
                if not action_result or action_result.result_code == ActionResultCode.FAILURE:
                    logger.error(f"[{self.context.name}] Failed to run pipeline action"
                                 f" [{action.action_type}] on backend [{backend}]" + 
                                 (f" for action name [{action.action_name}]" if action.action_name else ""))
                    self.__db.mark_dirty()
                    self.__db.flush()
                    return ActionResultCode.FAILURE
                if action_result.result_code != ActionResultCode.SUCCESS:
                    result = action_result.result_code
        self.__db.commit("stats", self.__context.stats)
        return result

    def execute_pipeline(self,
                         backends_context: BackendsContext,
                         workspace_context: WorkspaceContext,
                         clear_database: bool = False) -> ActionResultCode:
        """
        Executes the entire pipeline
        Each action will be executed in order
        If a backend was not initialized yet, will also try and initialize the backend
        :param backends_context:
        :param workspace_context:
        :param clear_database:
        :return: bool
        """
        # Create the working dir
        if not os.path.exists(self.context.working_dir):
            os.makedirs(self.context.working_dir)
        if not os.path.exists(os.path.join(self.context.working_dir, ".cache")):
            os.makedirs(os.path.join(self.context.working_dir, ".cache"))
        if not self.initialize_pipeline(backends_context, workspace_context):
            logger.error(f"[{self.context.name}] Failed to initialize pipeline")
            return ActionResultCode.FAILURE
        if clear_database:
            self.__db.reset()
            self.__context.stats.start_time = datetime.now()
            self.__partial_success_results = []
        # Start the pipeline
        result = ActionResultCode.SUCCESS
        for action in self.__actions[self.__db.current_step_idx:]:
            if self.__context.surrounding not in action.surroundings:
                logger.info(f"[{self.context.name}] Action [{action.action_type}] Does not fit surrounding "
                            f"[{self.__context.surrounding}], Ignoring")
                self.step_next_pipeline_action()
                continue
            for backend in action.backends:
                if self.__db.is_step_disabled(action.action_type.value,
                                              backend,
                                              "execute") or \
                        action.action_name and self.__db.is_step_disabled(action.action_name,
                                                                          backend,
                                                                          "execute"):
                    logger.info(f"[{self.context.name}] Action [{action.action_type}] "
                                f"from backend [{backend}] is disabled in execute" +
                                (f" for action name [{action.action_name}]" if action.action_name else ""))
                    continue
                if not backends_context.initialize_pipeline_backend_action(backend, action,
                                                                           self.__context, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend "
                                 f"[{backend}] for action [{action.action_type}]")
                    return ActionResultCode.FAILURE
                action_result = backends_context.execute_pipeline_backend_action(backend, action,
                                                                                 self.__context, workspace_context)
                if not action_result or action_result.result_code == ActionResultCode.FAILURE:
                    logger.error(f"[{self.context.name}] Failed to run pipeline action "
                                 f"[{action.action_type}] on backend [{backend}]" +
                                 (f" for action name [{action.action_name}]" if action.action_name else ""))
                    self.__db.mark_dirty()
                    self.__db.flush()
                    return ActionResultCode.FAILURE
                if action_result.result_code == ActionResultCode.PARTIAL_SUCCESS:
                    self.__partial_success_results.append(action_result)
                if action_result.result_code != ActionResultCode.SUCCESS:
                    result = action_result.result_code
            self.step_next_pipeline_action()

        # Check finalized result
        if len(self.__partial_success_results) > 0:
            logger.warning(f"[{self.context.name}] Partially succeeded running pipeline")
            for result in self.__partial_success_results:
                BackendsContext.print_result(result, self.context)
        else:
            logger.info(f"[{self.context.name}] Successfully Finished Executing Pipeline")
        self.__context.stats.end_time = datetime.now()
        return result

    def cleanup_pipeline(self,
                         backends_context: BackendsContext,
                         workspace_context: WorkspaceContext,
                         clear_database: bool = True,
                         rm_working_dir: bool = True) -> None:
        """
        Cleans up the entire pipeline
        Each action will be cleaned up reversed in order
        :param backends_context:
        :param workspace_context:
        :param clear_database:
        :param rm_working_dir:
        :return:
        """
        # Stop if there is not build directory to clean
        if not os.path.exists(self.__context.working_dir):
            return None
        # Make sure we initialize the pipeline if haven't already
        if not self.initialize_pipeline(backends_context, workspace_context):
            logger.error(f"[{self.context.name}] Failed to initialize pipeline")
            return None
        # Run the actions reversed for cleanup
        for action in reversed(self.__actions[:self.__db.current_step_idx+1]):
            if self.__context.surrounding not in action.surroundings:
                logger.info(f"[{self.context.name}] Action [{action.action_type}] Does not fit surrounding "
                            f"[{self.__context.surrounding}], Ignoring")
                continue
            for backend in action.backends:
                if self.__db.is_step_disabled(action.action_type.value,
                                              backend,
                                              "clean") or \
                        action.action_name and self.__db.is_step_disabled(action.action_name,
                                                                          backend,
                                                                          "clean"):
                    logger.info(f"[{self.context.name}] Action [{action.action_type}] "
                                f"from backend [{backend}] is disabled in cleanup" +
                                (f" for action name [{action.action_name}]" if action.action_name else ""))
                    continue
                if not backends_context.initialize_pipeline_backend_action(backend, action,
                                                                           self.__context, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend "
                                 f"[{backend}] for action [{action.action_type}]" +
                                 (f" for action name [{action.action_name}]" if action.action_name else ""))
                    return None
                backends_context.cleanup_pipeline_backend_action(backend, action, self.__context, workspace_context)
        if rm_working_dir and os.path.exists(self.__context.working_dir):
            shutil.rmtree(self.__context.working_dir)
        if clear_database:
            self.__db.reset()

    def cleanup_pipeline_action(self, action_type_name: Union[ActionType, str],
                                backends_context: BackendsContext,
                                workspace_context: WorkspaceContext) -> None:
        """
        Cleans up a specific pipeline action type
        All of the actions of this type will be cleaned up if fit the surrounding
        :param action_type_name:
        :param backends_context:
        :param workspace_context:
        :return:
        """
        # Create the working dir
        if not os.path.exists(self.__context.working_dir):
            return None
        for action in reversed(self.__actions[:self.__db.current_step_idx+1]):
            if self.__context.surrounding not in action.surroundings and \
               Surrounding.OnDemand not in action.surroundings:
                logger.info(f"[{self.context.name}] Action [{action.action_type}] Does not fit surrounding "
                            f"[{self.__context.surrounding}], Ignoring")
                continue
            if action.action_type != action_type_name and action.action_name != action_type_name:
                continue
            for backend in action.backends:
                if self.__db.is_step_disabled(action.action_type.value,
                                              backend,
                                              "clean-action") or \
                        action.action_name and self.__db.is_step_disabled(action.action_name,
                                                                          backend,
                                                                          "clean-action"):
                    logger.info(f"[{self.context.name}] Action [{action.action_type}] "
                                f"from backend [{backend}] is disabled in clean action" +
                                (f" for action name [{action.action_name}]" if action.action_name else ""))
                    continue
                if not backends_context.initialize_backend(backend, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend [{backend}]")
                    return None
                if not backends_context.initialize_pipeline_backend_action(backend, action,
                                                                           self.__context, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend "
                                 f"[{backend}] for action [{action.action_type}]" +
                                 (f" for action name [{action.action_name}]" if action.action_name else ""))
                    return None
                backends_context.cleanup_pipeline_backend_action(backend, action, self.__context, workspace_context)
        self.__db.commit("stats", self.__context.stats)

    def step_next_pipeline_action(self) -> None:
        """
        Moves the step pointer to the next pipeline action
        Also commits to the pipeline DB
        :return:
        """
        self.__db.step_next()
        self.__db.commit("stats", self.__context.stats)

    def step_previous_pipeline_action(self) -> None:
        """
        Moves the step pointer to the previous pipeline action
        Also commits to the pipeline DB
        :return:
        """
        self.__db.step_previous()
        self.__db.commit("stats", self.__context.stats)

    def current_pipeline_step(self) -> Tuple[PipelineAction, int]:
        """
        Getter for the current step info
        :return: Tuple[PipelineAction, int]
        """
        return self.__db.current_step, self.__db.current_step_idx

    def reset_pipeline_steps(self) -> None:
        """
        Resets the entire step pipeline DB
        :return:
        """
        self.__db.reset()

    def step_execute_pipeline_action(self,
                                     backends_context: BackendsContext,
                                     workspace_context: WorkspaceContext) -> ActionResultCode:
        """
        Executes the current step pointer action
        Will only execute and update the DB, but not move the step forward
        :param backends_context:
        :param workspace_context:
        :return:
        """
        if not os.path.exists(self.context.working_dir):
            os.makedirs(self.context.working_dir)
        if not os.path.exists(os.path.join(self.context.working_dir, ".cache")):
            os.makedirs(os.path.join(self.context.working_dir, ".cache"))
        action: PipelineAction = self.__db.current_step
        result = ActionResultCode.SUCCESS
        if action:
            if self.__context.surrounding not in action.surroundings:
                logger.info(f"[{self.context.name}] Action [{action.action_type}] Does not fit surrounding "
                            f"[{self.__context.surrounding}], Ignoring")
                return ActionResultCode.SUCCESS
            for backend in action.backends:
                if self.__db.is_step_disabled(action.action_type.value,
                                              backend,
                                              "execute-step") or \
                        action.action_name and self.__db.is_step_disabled(action.action_name,
                                                                          backend,
                                                                          "execute-step"):
                    logger.info(f"[{self.context.name}] Action [{action.action_type}] "
                                f"from backend [{backend}] is disabled in execute" +
                                (f" for action name [{action.action_name}]" if action.action_name else ""))
                    continue
                if not backends_context.initialize_backend(backend, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend [{backend}]")
                    return ActionResultCode.FAILURE
                if not backends_context.initialize_pipeline_backend_action(backend, action,
                                                                           self.__context, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend "
                                 f"[{backend}] for action [{action.action_type}]")
                    return ActionResultCode.FAILURE
                action_result = backends_context.execute_pipeline_backend_action(backend, action,
                                                                                 self.__context, workspace_context)
                if not action_result or action_result.result_code == ActionResultCode.FAILURE:
                    logger.error(f"[{self.context.name}] Failed to run pipeline action "
                                 f"[{action.action_type}] on backend [{backend}]" +
                                 (f" for action name [{action.action_name}]" if action.action_name else ""))
                    self.__db.mark_dirty()
                    self.__db.flush()
                    return ActionResultCode.FAILURE
                self.__db.commit("stats", self.__context.stats)
                if action_result.result_code != ActionResultCode.SUCCESS:
                    result = action_result.result_code
        else:
            logger.info(f"[{self.context.name}] No more actions to run")
        return result

    def step_clean_pipeline_action(self,
                                   backends_context: BackendsContext,
                                   workspace_context: WorkspaceContext) -> None:
        """
        Cleans up the current step pointer action
        Will only clean up and update the DB, but not move the step backwards
        :param backends_context:
        :param workspace_context:
        :return:
        """
        action: PipelineAction = self.__db.current_step
        if action:
            if self.__context.surrounding not in action.surroundings:
                logger.info(f"[{self.context.name}] Action [{action.action_type}] Does not fit surrounding "
                            f"[{self.__context.surrounding}], Ignoring")
                return None
            for backend in action.backends:
                if self.__db.is_step_disabled(action.action_type.value,
                                              backend,
                                              "clean-step") or \
                        action.action_name and self.__db.is_step_disabled(action.action_name,
                                                                          backend,
                                                                          "clean-step"):
                    logger.info(f"[{self.context.name}] Action [{action.action_type}] "
                                f"from backend [{backend}] is disabled in execute" +
                                (f" for action name [{action.action_name}]" if action.action_name else ""))
                    continue
                if not backends_context.initialize_backend(backend, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend [{backend}]")
                    return None
                if not backends_context.initialize_pipeline_backend_action(backend, action,
                                                                           self.__context, workspace_context):
                    logger.error(f"[{self.context.name}] Could not initialize backend"
                                 f" [{backend}] for action [{action.action_type}]" +
                                 (f" for action name [{action.action_name}]" if action.action_name else ""))
                    return None
                backends_context.cleanup_pipeline_backend_action(backend, action, self.__context, workspace_context)
                self.__db.commit("stats", self.__context.stats)
        else:
            logger.info(f"[{self.context.name}] No more actions to clean")

    def describe_pipeline(self) -> PipelineDescription:
        """
        Getter for the pipeline description
        :return: PipelineDescription
        """
        return PipelineDescription(actions=self.__actions,
                                   context=self.__context)

    def disable_pipeline_step(self, action: str,
                              backend: Optional[str] = None,
                              command: Optional[str] = None) -> None:
        """
        Disables a specific action from running when the pipeline is executed / cleaned
        :param action:
        :param backend:
        :param command:
        :return:
        """
        self.__db.disable_step(action, backend, command)

    def enable_pipeline_step(self, action: str,
                             backend: Optional[str] = None,
                             command: Optional[str] = None) -> None:
        """
        Enables a specific action to be able to run when the pipeline is executed / cleaned if it was disabled
        :param action:
        :param backend:
        :param command:
        :return:
        """
        self.__db.enable_step(action, backend, command)
