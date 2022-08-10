import os
import traceback
from collections import defaultdict
from threading import RLock
from typing import Any, Dict, List, Optional

from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend_auth_details import \
    BackendAuthDetails
from octo_pipeline_python.backends.backend_description import \
    BackendDescription
from octo_pipeline_python.backends.backends_database import BackendsDatabase
from octo_pipeline_python.pipeline.pipeline_action import PipelineAction
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class BackendsContext:
    def __init__(self, workspace_context: WorkspaceContext):
        from backends.backend import Backend
        self.__backends: Dict[str, Backend] = {}
        self.__backends_attributes: Dict[str, Any] = {}
        self.__backends_attributes_exclude: Dict[str, bool] = defaultdict(bool)
        self.__backends_attrs_lock = RLock()
        self.__db = BackendsDatabase(workspace_context)
        if self.__db.contains("backends_attributes"):
            self.__backends_attributes = self.__db.get("backends_attributes")

    @staticmethod
    def print_result(result: ActionResult, pipeline_context: PipelineContext) -> None:
        """
        Helper functions to print results for a pipeline action
        :param result:
        :param pipeline_context:
        :return:
        """
        logger.warning(f"[{pipeline_context.name}] Action Type [{result.action_type}]")
        logger.warning(f"[{pipeline_context.name}] Result Code [{result.result_code}]")
        logger.warning(f"[{pipeline_context.name}] ----------- Results -----------")
        for error in result.result:
            logger.warning(f"[{pipeline_context.name}] {error}")

    def __commit_to_database(self):
        self.__db.commit("backends_attributes", {
            x: y for x, y in self.__backends_attributes.items()
            if not self.__backends_attributes_exclude[x]
        })

    def initialize_backend(self, backend: str, workspace_context: WorkspaceContext) -> bool:
        """
        Initializes the backend itself and stores it on the local map
        :param backend:
        :param workspace_context:
        :return: bool
        """
        import octo_pipeline_python.backends.backends
        from octo_pipeline_python.backends.backend import Backend
        self.__backends_attrs_lock.acquire()
        try:
            if backend in self.__backends:
                return True
            # Initialize the backend only if it exists as part of one of the actions
            logger.info(f"Initializing backend [{backend}]")
            backend_class = [b for b in Backend.__subclasses__() if b.backend_name() == backend]
            if len(backend_class) != 1:
                return False
            self.__backends[backend] = backend_class[0]()
            self.__backends[backend].initialize_backend(self, workspace_context)
            return True
        finally:
            self.__backends_attrs_lock.release()

    def initialize_pipeline_backend_action(self, backend: str,
                                           action: PipelineAction,
                                           pipeline_context: PipelineContext,
                                           workspace_context: WorkspaceContext) -> bool:
        """
        Initializes the backend action based on the given backend name and action
        Depending on the backend, the action may run or not
        :param backend:
        :param action:
        :param pipeline_context:
        :param workspace_context:
        :return: bool
        """
        try:
            # Execute the action for the backend
            if not self.__backends[backend]. \
                initialize_backend_pipeline_action(action.action_type,
                                                   self,
                                                   pipeline_context,
                                                   workspace_context,
                                                   action.action_name):
                logger.error(f"[{pipeline_context.name}] "
                             f"Failed initializing action [{action.action_type}] on backend [{backend}]")
                return False
        except Exception as e:
            logger.error(f"[{pipeline_context.name}] Error occurred while running action "
                         f"[{action.action_type}] from backend [{backend}] - [{str(e)}]")
            logger.error(traceback.format_exc())
        return True

    def execute_pipeline_backend_action(self, backend: str,
                                        action: PipelineAction,
                                        pipeline_context: PipelineContext,
                                        workspace_context: WorkspaceContext) -> Optional[ActionResult]:
        """
        Executes the backend action based on the given backend name and action
        Depending on the backend, the action may run or not
        :param backend:
        :param action:
        :param pipeline_context:
        :param workspace_context:
        :return: bool
        """
        if not os.path.exists(workspace_context.working_dir):
            os.makedirs(workspace_context.working_dir)
        if not os.path.exists(pipeline_context.working_dir):
            os.makedirs(pipeline_context.working_dir)
        result: Optional[ActionResult] = None
        try:
            # Execute the action for the backend
            result = self.__backends[backend]. \
                execute_backend_pipeline_action(action.action_type,
                                                self,
                                                pipeline_context,
                                                workspace_context,
                                                action.action_name)
            if result.result_code == ActionResultCode.FAILURE:
                logger.error(f"[{pipeline_context.name}] Failed running action "
                             f"[{action.action_type}] on backend [{backend}]")
                BackendsContext.print_result(result, pipeline_context)
            return result
        except Exception as e:
            logger.error(f"[{pipeline_context.name}] Error occurred while running action "
                         f"[{action.action_type}] from backend [{backend}] - [{str(e)}]")
            logger.error(traceback.format_exc())
        return result

    def cleanup_pipeline_backend_action(self, backend: str,
                                        action: PipelineAction,
                                        pipeline_context: PipelineContext,
                                        workspace_context: WorkspaceContext) -> None:
        """
        Cleans up an action via the given backend
        :param backend:
        :param action:
        :param pipeline_context:
        :param workspace_context:
        :return:
        """
        try:
            # Cleanup action
            self.__backends[backend].\
                cleanup_backend_pipeline_action(action.action_type,
                                                self,
                                                pipeline_context,
                                                workspace_context,
                                                action.action_name)
        except Exception as e:
            logger.warning(f"[{pipeline_context.name}] Error occurred while cleaning up action "
                           f"{action.action_type} from backend {backend} - [{str(e)}]")
            logger.warning(traceback.format_exc())

    def authenticate_backend(self, backend: str, auth_details: BackendAuthDetails,
                             workspace_context: WorkspaceContext,
                             pipeline_context: Optional[PipelineContext]) -> ActionResultCode:
        """
        Tries to authenticate to a given backend
        Will also try and initialize the backend beforehand if not initialized yet
        :param backend:
        :param auth_details:
        :param workspace_context:
        :param pipeline_context:
        :return: bool
        """
        if not os.path.exists(workspace_context.working_dir):
            os.makedirs(workspace_context.working_dir)
        if not os.path.exists(os.path.join(workspace_context.working_dir, ".cache")):
            os.makedirs(os.path.join(workspace_context.working_dir, ".cache"))
        # Initialize the backend before trying to authenticate
        if backend not in self.__backends:
            if not self.initialize_backend(backend, workspace_context):
                logger.error(f"Could not initialize backend [{backend}]")
                return ActionResultCode.FAILURE
        return self.__backends[backend].authenticate_backend(auth_details,
                                                             self,
                                                             workspace_context,
                                                             pipeline_context)

    def describe_backend(self, backend: str,
                         workspace_context: WorkspaceContext) -> Optional[BackendDescription]:
        """
        Getter for a backend description
        Will also try and initialize the backend beforehand if not initialized yet
        :param backend:
        :param workspace_context:
        :return: Optional[BackendDescription]
        """
        # Initialize the backend before getting its description
        if backend not in self.__backends:
            if not self.initialize_backend(backend, workspace_context):
                logger.error(f"Could not initialize backend [{backend}]")
                return None
        return self.__backends[backend].describe_backend(self, workspace_context)

    def backend_context_attribute(self, backend: str,
                                  key: str,
                                  workspace_context: WorkspaceContext) -> Any:
        """
        Getter for a backed context attribute
        Will also try and initialize the backend beforehand if not initialized yet
        :param backend:
        :param key:
        :param workspace_context:
        :return: Any
        """
        # Initialize the backend before trying to get the attribute
        if backend not in self.__backends:
            if not self.initialize_backend(backend, workspace_context):
                logger.error(f"Could not initialize backend [{backend}]")
                return None
        if not self.has_attribute(backend, key):
            raise Exception(f"Could not find attribute [{key}]")
        return self.attribute(backend, key)

    def initialize_backends_for_pipeline(self,
                                         actions: List[PipelineAction],
                                         workspace_context: WorkspaceContext) -> bool:
        """
        Will try and initialize a backend if it fits the surrounding
        :return: bool
        """
        # Initialize the actions backends
        for action in actions:
            if workspace_context.surrounding not in action.surroundings:
                continue
            for backend in action.backends:
                if not self.initialize_backend(backend, workspace_context):
                    logger.error(f"Could not initialize backend [{backend}]")
                    return False
        return True

    @property
    def backends_attributes(self) -> Dict[str, Any]:
        """
        Getter for the attributes
        :return:
        """
        return self.__backends_attributes

    def add_attribute(self,
                      backend: str,
                      key: str,
                      val: Any,
                      tag: str = None,
                      exclude_from_db: bool = False) -> None:
        """
        Add a new attribute to the context, with possible tagging
        :param backend:
        :param key:
        :param val:
        :param tag:
        :param exclude_from_db:
        :return:
        """
        self.__backends_attrs_lock.acquire()
        path = f"{backend}.{key}"
        if tag:
            path = f"{tag}.{path}"
        self.__backends_attributes[path] = val
        self.__backends_attributes_exclude[path] = exclude_from_db
        if not exclude_from_db:
            self.__commit_to_database()
        self.__backends_attrs_lock.release()

    def attribute(self, backend: str, key: str, tag: str = None) -> Any:
        """
        Getter for a specific attribute
        :param backend:
        :param key:
        :param tag:
        :return:
        """
        self.__backends_attrs_lock.acquire()
        path = f"{backend}.{key}"
        if tag:
            path = f"{tag}.{path}"
        try:
            if path in self.__backends_attributes:
                return self.__backends_attributes[path]
            return None
        finally:
            self.__backends_attrs_lock.release()

    def has_attribute(self, backend: str, key: str, tag: str = None) -> bool:
        """
        Checks if an attribute exists
        :param backend:
        :param key:
        :param tag:
        :return:
        """
        self.__backends_attrs_lock.acquire()
        path = f"{backend}.{key}"
        if tag:
            path = f"{tag}.{path}"
        try:
            return path in self.__backends_attributes
        finally:
            self.__backends_attrs_lock.release()

    def source_dir(self,
                   backend: "Backend",
                   pipeline_context: PipelineContext,
                   workspace_context: WorkspaceContext) -> str:
        """
        Tries to get the source directory to work on based on a few backends
        :param backend:
        :param pipeline_context:
        :param workspace_context:
        :return:
        """
        from octo_pipeline_python.actions.action_type import ActionType

        # Assume the source dir for conan operations is the pipeline source dir
        conan_source_dir = pipeline_context.source_dir

        # If exists, meaning it was set via conan source
        if self.has_attribute(backend.backend_name(), "source_dir", tag=pipeline_context.name):
            conan_source_dir = self.attribute(backend.backend_name(),
                                              "source_dir",
                                              tag=pipeline_context.name)

        # If exists, meaning it was set via git source
        elif self.has_attribute("git", "source_dir", tag=pipeline_context.name):
            conan_source_dir = self.attribute("git", "source_dir", tag=pipeline_context.name)

        # Check if it context of source in working dir
        elif os.path.exists(os.path.join(pipeline_context.working_dir, 'source')) and \
                ActionType.Source.value in backend.describe_backend(self, workspace_context).actions:
            conan_source_dir = os.path.join(pipeline_context.working_dir, 'source')
        return conan_source_dir
