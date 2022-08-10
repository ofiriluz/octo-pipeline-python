import concurrent.futures
import functools
import multiprocessing
import os
import shutil
import traceback
from random import uniform
from threading import RLock
from time import sleep
from typing import Callable, Dict, Final, List, Optional, Set, Tuple, Union

import networkx

from octo_pipeline_python.actions.action_result import ActionResultCode
from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.pipeline.pipeline import Pipeline
from octo_pipeline_python.pipeline.pipeline_builder import PipelineBuilder
from octo_pipeline_python.utils.git import GitUtils
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.utils.search import Search
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext
from octo_pipeline_python.workspace.workspace_database import WorkspaceDatabase
from octo_pipeline_python.workspace.workspace_description import \
    WorkspaceDescription
from octo_pipeline_python.workspace.workspace_pipeline import WorkspacePipeline
from octo_pipeline_python.workspace.workspace_state import WorkspaceState

COND_VAR_TIMEOUT = 3.0
DEFAULT_RETRY_COUNT = 1


class Workspace:
    def __init__(self, workspace: Dict[str, List[WorkspacePipeline]],
                 context: WorkspaceContext,
                 singular_pipeline: Optional[Pipeline] = None):
        self.__workspace = workspace
        self.__context = context
        self.__singular_pipeline = singular_pipeline
        self.__workspace_pipelines: Dict[str, List[Pipeline]] = {}
        if self.__singular_pipeline:
            self.__workspace_pipelines[self.__singular_pipeline.context.name] = [self.__singular_pipeline]
        self.__db = WorkspaceDatabase(context)
        if self.__db.contains("stats"):
            self.__context.stats = self.__db.get("stats")
        self.__workspace_state: Optional[WorkspaceState] = None
        self.__sync_lock = RLock()
        self.__resolve_lock = RLock()
        self.__ws_pipelines_lock = RLock()
        self.__failed_pipelines: List[str] = []

    @staticmethod
    def init_workspace_to(organization: str,
                          name: str,
                          scm: str,
                          to_path: str,
                          head: str = "master") -> Optional["Workspace"]:
        """
        Tries to initialize a workspace to the given directory
        :param organization:
        :param name:
        :param scm:
        :param to_path:
        :param head:
        :return:
        """
        from workspace.workspace_builder import WorkspaceBuilder
        if not os.path.exists(to_path):
            os.makedirs(to_path)
        if len(os.listdir(to_path)) > 0:
            if GitUtils.checkout_to_branch(to_path, head):
                return WorkspaceBuilder.create(source_dir=to_path)
        scm = GitUtils.clone_and_checkout(scm, organization, name, to_path, head)
        if scm:
            workspace: Workspace = WorkspaceBuilder.create(source_dir=to_path)
            if workspace:
                logger.info(f"Using [{scm}] on [{to_path}] as the repo for [{name}]")
                return workspace
            else:
                shutil.rmtree(to_path)
                os.makedirs(to_path)
        return None

    @property
    def context(self) -> WorkspaceContext:
        """
        Getter for the workspace context
        :return: PipelineContext
        """
        return self.__context

    @property
    def workspace(self) -> Dict[str, List[WorkspacePipeline]]:
        """
        Getter for the workspace information
        :return:
        """
        return self.__workspace

    @property
    def workspace_pipelines(self) -> Dict[str, List[Pipeline]]:
        """
        Getter for the workspace pipelines
        :return:
        """
        return self.__workspace_pipelines

    @property
    def singular_pipeline(self) -> Optional[Pipeline]:
        """
        Getter for the singular pipeline
        :return:
        """
        if self.__singular_pipeline:
            return self.__singular_pipeline
        pipeline_name: Optional[str] = Search. \
            search_pipeline_name(hints=[],
                                 possible_pipelines=self.describe_pipelines(
                                     with_groups=False))
        if pipeline_name:
            pipeline: Pipeline = self.pipeline(pipeline_name)
            if not pipeline:
                return PipelineBuilder.create(source_dir=self.pipeline_path(pipeline_name))
        return None

    def workspace_state(self, quick: bool = False) -> WorkspaceState:
        self.__resolve_state(quick)
        return self.__workspace_state

    def __update_resolved_state(self, state_list: Union[Dict[str, List[WorkspacePipeline]], Dict[str, List[Pipeline]]],
                                pipeline: Optional[Union[WorkspacePipeline, List[WorkspacePipeline], Pipeline]],
                                base_path: str):
        try:
            self.__resolve_lock.acquire()
            if pipeline and isinstance(pipeline, list):
                state_list[base_path] = pipeline
            else:
                if base_path not in state_list:
                    state_list[base_path] = []
                if pipeline:
                    state_list[base_path].append(pipeline)
        finally:
            self.__resolve_lock.release()

    def __resolve_pipeline_state_thread(self, pipeline: WorkspacePipeline, pipeline_path: str,
                                        base_path: str, quick: bool) -> None:
        if not os.path.exists(pipeline_path):
            self.__update_resolved_state(self.__workspace_state.unresolved_pipelines, pipeline, base_path)
            return

        ws_pipeline: Optional[Union[Pipeline, List[Pipeline]]] = \
            [p for p in self.__workspace_pipelines[base_path] if p.context.name == pipeline.name]
        if len(ws_pipeline) > 0:
            ws_pipeline = ws_pipeline[0]
        else:
            ws_pipeline: Pipeline = PipelineBuilder.create(pipeline_path, self.context.working_dir,
                                                           ignore_workspace=True)
            if ws_pipeline:
                self.__update_resolved_state(self.__workspace_pipelines, ws_pipeline, base_path)
            else:
                self.__update_resolved_state(self.__workspace_state.unresolved_pipelines, pipeline, base_path)
                return

        if ws_pipeline.context.head != pipeline.head or \
                (not quick and (GitUtils.is_behind_on_commits(ws_pipeline.context.source_dir) or
                                GitUtils.is_ahead_on_commits(ws_pipeline.context.source_dir))):
            if ws_pipeline.completed:
                self.__update_resolved_state(self.__workspace_state.completed_pipelines, pipeline, base_path)
            elif not pipeline.executable:
                self.__update_resolved_state(self.__workspace_state.read_only_pipelines, pipeline, base_path)
            else:
                self.__update_resolved_state(self.__workspace_state.unsynced_pipelines, pipeline, base_path)
        elif ws_pipeline.completed:
            self.__update_resolved_state(self.__workspace_state.completed_pipelines, pipeline, base_path)
        elif ws_pipeline.failed:
            self.__update_resolved_state(self.__workspace_state.failed_pipelines, pipeline, base_path)
        else:
            self.__update_resolved_state(self.__workspace_state.synced_pipelines, pipeline, base_path)

    def __resolve_state(self, quick: bool = False,
                        parallel_jobs: Optional[int] = None) -> None:
        """
        Tries and resolves the workspace state
        :return:
        """
        if not parallel_jobs:
            parallel_jobs = min(multiprocessing.cpu_count() / 2, 8)
        self.__resolve_lock.acquire()
        self.__workspace_state = WorkspaceState(unresolved_pipelines={},
                                                unsynced_pipelines={},
                                                synced_pipelines={},
                                                completed_pipelines={},
                                                read_only_pipelines={},
                                                failed_pipelines={})
        self.__resolve_lock.release()
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            active_futures = set()
            for path, pipelines in self.__workspace.items():
                if not os.path.exists(path):
                    # All of the pipelines do not exist
                    self.__update_resolved_state(self.__workspace_state.unresolved_pipelines, pipelines, path)
                    continue
                if path not in self.__workspace_pipelines:
                    self.__update_resolved_state(self.__workspace_pipelines, None, path)
                for pipeline in pipelines:
                    pipeline_path = os.path.join(self.context.source_dir, path, pipeline.name)
                    active_futures.add(
                        executor.submit(self.__resolve_pipeline_state_thread,
                                        pipeline=pipeline, pipeline_path=pipeline_path, base_path=path, quick=quick)
                    )
            concurrent.futures.wait(active_futures, return_when=concurrent.futures.ALL_COMPLETED)

    def describe_workspace(self) -> WorkspaceDescription:
        """
        Getter for the workspace description
        :return: WorkspaceDescription
        """
        ws_description = WorkspaceDescription(workspace=self.__workspace,
                                              context=self.__context,
                                              pipelines=None)
        if len(self.__workspace_pipelines) > 0:
            ws_description.pipelines = {path: [pipeline.describe_pipeline() for pipeline in path_pipelines]
                                        for path, path_pipelines in self.__workspace_pipelines.items()}
        elif self.__singular_pipeline:
            ws_description.pipelines = \
                {self.__singular_pipeline.context.name: [self.__singular_pipeline.describe_pipeline()]}
        return ws_description

    def describe_pipelines(self, with_groups=True) -> Set[str]:
        """
        Getter for the pipelines existing in the workspace
        :return:
        """
        # Add all of the pipelines possible, both the keys to list and the pipelines themselves
        pipeline_names: Set[str] = set()
        if with_groups:
            pipeline_names.update(self.__workspace.keys())
        for pipelines in self.__workspace.values():
            pipeline_names.update({p.name for p in pipelines})
        return pipeline_names

    def pipeline_path(self, name: str) -> Optional[str]:
        """
        Gets the pipeline path for a given name
        :param name:
        :return:
        """
        for path, pipelines in self.__workspace.items():
            for pipeline in pipelines:
                if pipeline.name == name:
                    return os.path.join(self.context.source_dir, path, name)
        return None

    def pipeline(self, name: str) -> Optional[Pipeline]:
        """
        Gets a pipeline for a given name
        :param name:
        :return:
        """
        for path, pipelines in self.__workspace_pipelines.items():
            for pipeline in pipelines:
                if pipeline.context.name == name:
                    return pipeline
        return None

    def __sync_unresolved_pipeline_thread(self, path: str, workspace_pipeline: WorkspacePipeline) -> None:
        """
        Tries to create the actual pipeline, clone and checkout to branch
        :param path:
        :param workspace_pipeline:
        :return:
        """
        pipeline_path = os.path.join(path, workspace_pipeline.name)
        logger.info(f"Resolving {workspace_pipeline.name}")
        pipeline: Pipeline = Pipeline.init_pipeline_to(self.context.organizations,
                                                       workspace_pipeline.name,
                                                       self.context.scm,
                                                       pipeline_path,
                                                       workspace_pipeline.head,
                                                       True,
                                                       workspace_pipeline.external)
        if not pipeline and not workspace_pipeline.external:
            logger.warning(f"Failed to resolve pipeline {workspace_pipeline.name} [Pipeline files were not found]")
            self.__ws_pipelines_lock.acquire()
            self.__failed_pipelines.append(workspace_pipeline.name)
            self.__ws_pipelines_lock.release()
            return
        if workspace_pipeline.external:
            self.__ws_pipelines_lock.acquire()
            if path not in self.__workspace_pipelines:
                self.__workspace_pipelines[path] = []
            self.__workspace_pipelines[path].append(pipeline)
            self.__ws_pipelines_lock.release()

    def __sync_unsynced_pipeline_thread(self, path: str,
                                        workspace_pipeline: WorkspacePipeline,
                                        no_code_sync: bool,
                                        sync_retry: int = 3,
                                        backoff_factor: float = 1.3,
                                        max_retry_sleep: float = 60) -> None:
        """
        Runs a sync to the pipeline head branch if possible
        :param path:
        :param workspace_pipeline:
        :return:
        """
        pipeline_path = os.path.join(path, workspace_pipeline.name)
        logger.info(f"Syncing {workspace_pipeline.name}")
        if not GitUtils.checkout_to_branch(pipeline_path, workspace_pipeline.head):
            logger.warning(f"Failed to sync pipeline {workspace_pipeline.name} branch")
            self.__ws_pipelines_lock.acquire()
            self.__failed_pipelines.append(workspace_pipeline.name)
            self.__ws_pipelines_lock.release()
        if not no_code_sync:
            success_code_sync = GitUtils.pull_latest_code(pipeline_path)
            if not success_code_sync and sync_retry > 0:
                for _ in range(0, sync_retry):
                    retry_sleep = min(round(uniform(1 * backoff_factor, 5 * backoff_factor), 3), max_retry_sleep)
                    backoff_factor *= backoff_factor
                    logger.info(f"Retrying pipeline {workspace_pipeline.name}"
                                f" pull code in [{retry_sleep}] seconds")
                    sleep(retry_sleep)
                    success_code_sync = GitUtils.pull_latest_code(pipeline_path)
                    if success_code_sync:
                        break

            if not success_code_sync:
                logger.warning(f"Failed to sync pipeline"
                               f" {workspace_pipeline.name} code")
                self.__ws_pipelines_lock.acquire()
                self.__failed_pipelines.append(workspace_pipeline.name)
                self.__ws_pipelines_lock.release()

    def sync_workspace(self,
                       no_code_sync: bool = False,
                       parallel_jobs: Optional[int] = None,
                       sync_retry: int = 3,
                       backoff_factor: float = 1.3) -> Optional[List[str]]:
        """
        Syncs the workspace, clones the repos if needed
        And checks out to branches if needed accordingly
        :return: List of pipelines that failed to sync
        """
        self.__sync_lock.acquire()
        if not parallel_jobs:
            parallel_jobs = min(multiprocessing.cpu_count() / 2, 8)

        try:
            self.__resolve_state(parallel_jobs=parallel_jobs)
            self.__failed_pipelines = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
                active_futures = set()

                for path, unresolved_pipelines in self.__workspace_state.unresolved_pipelines.items():
                    if not os.path.exists(path):
                        os.makedirs(path)
                    for unresolved_pipeline in unresolved_pipelines:
                        active_futures.add(
                            executor.submit(self.__sync_unresolved_pipeline_thread,
                                            path=path, workspace_pipeline=unresolved_pipeline)
                        )

                for path, unsynced_pipelines in self.__workspace_state.unsynced_pipelines.items():
                    for unsynced_pipeline in unsynced_pipelines:
                        active_futures.add(
                            executor.submit(self.__sync_unsynced_pipeline_thread,
                                            path=path, workspace_pipeline=unsynced_pipeline, no_code_sync=no_code_sync,
                                            sync_retry=sync_retry, backoff_factor=backoff_factor)
                        )

                concurrent.futures.wait(active_futures, return_when=concurrent.futures.ALL_COMPLETED)
            return self.__failed_pipelines
        finally:
            self.__sync_lock.release()

    def __get_filtered_pipelines(self,
                                 filters: Optional[Tuple[str, ...]],
                                 recursive: Optional[bool]) -> Set[WorkspacePipeline]:
        # Collect all of the pipelines filtered
        pipelines: Set[WorkspacePipeline] = set()
        for path, ws_pipelines in self.__workspace.items():
            if not filters or len(filters) == 0:
                pipelines.update(ws_pipelines)
            elif path in filters:
                pipelines.update(ws_pipelines)
                if recursive:
                    for p in ws_pipelines:
                        if len(p.needs) > 0:
                            pipelines.update(self.__get_filtered_pipelines(p.needs, recursive))
            else:
                for p in ws_pipelines:
                    if p.name in filters:
                        pipelines.add(p)
                        if recursive:
                            if recursive and len(p.needs) > 0:
                                pipelines.update(self.__get_filtered_pipelines(p.needs, recursive))
        return {pipeline for pipeline in pipelines if pipeline.executable and not pipeline.external}

    def __execute_pipeline_thread(self, reset_cache: bool,
                                  backends_context: BackendsContext,
                                  pipeline: Pipeline,
                                  retries: int = DEFAULT_RETRY_COUNT) -> Tuple[ActionResultCode, Pipeline]:
        for _ in range(retries):
            try:
                result = pipeline.execute_pipeline(backends_context,
                                                   self.context,
                                                   reset_cache)
                return result, pipeline
            except:
                continue
        return ActionResultCode.FAILURE, pipeline

    def __execute_pipeline_action_thread(self, action_type: ActionType,
                                         backends_context: BackendsContext,
                                         pipeline: Pipeline,
                                         retries: int = DEFAULT_RETRY_COUNT) -> Tuple[ActionResultCode, Pipeline]:
        for _ in range(retries):
            try:
                result = pipeline.execute_pipeline_action(action_type,
                                                          backends_context,
                                                          self.context)
                return result, pipeline
            except:
                continue
        return ActionResultCode.FAILURE, pipeline

    def __clean_pipeline_thread(self,
                                reset_cache: bool,
                                rm_working_dir: bool,
                                backends_context: BackendsContext,
                                pipeline: Pipeline,
                                retries: int = DEFAULT_RETRY_COUNT) -> Tuple[ActionResultCode, Pipeline]:
        for _ in range(retries):
            try:
                pipeline.cleanup_pipeline(backends_context, self.context, reset_cache, rm_working_dir)
                return ActionResultCode.SUCCESS, pipeline
            except:
                continue
        return ActionResultCode.FAILURE, pipeline

    def __clean_pipeline_action_thread(self, action_type: ActionType,
                                       backends_context: BackendsContext,
                                       pipeline: Pipeline,
                                       retries: int = DEFAULT_RETRY_COUNT) -> Tuple[ActionResultCode, Pipeline]:
        for _ in range(retries):
            try:
                pipeline.cleanup_pipeline_action(action_type,
                                                 backends_context,
                                                 self.context)
                break
            except:
                continue
        return ActionResultCode.SUCCESS, pipeline

    def __execute_pipelines_action(self,
                                   backends_context: BackendsContext,
                                   action: Callable,
                                   filters: Optional[List[str]],
                                   parallel_jobs: Optional[int],
                                   retries: Optional[int],
                                   recursive: Optional[bool]) -> ActionResultCode:
        # Get a simple list of pipelines filtered
        # Start executing them
        if not parallel_jobs:
            parallel_jobs = min(multiprocessing.cpu_count() / 2, 8)
        logger.info("Running workspace pipelines with [%d] parallel size",
                    parallel_jobs)
        self.__ws_pipelines_lock.acquire()
        self.__resolve_state(quick=True, parallel_jobs=parallel_jobs)
        for p in (self.context.working_dir,
                  os.path.join(self.context.working_dir, ".cache")):
            os.makedirs(p, exist_ok=True)

        try:
            workspace_pipelines: Set[WorkspacePipeline] = \
                self.__get_filtered_pipelines(filters, recursive)
            for workspace_pipeline in workspace_pipelines:
                if unresolved_pipelines := \
                        self.__workspace_state.unresolved_pipelines.get(workspace_pipeline.path, None):
                    if workspace_pipeline in unresolved_pipelines:
                        logger.error(f"Pipeline [{workspace_pipeline.name}]"
                                     f" is unresolved")
                        return ActionResultCode.FAILURE

            workspace_pipelines_name: Final[Tuple[str, ...]] = \
                tuple(wp.name for wp in workspace_pipelines)
            completed_pipelines = [
                p.name
                for completed_pipeline in
                self.__workspace_state.completed_pipelines.values()
                for p in completed_pipeline
                if p.name not in workspace_pipelines_name
            ]
            failed_pipelines = []

            # Build a DAG of all dependencies
            pipeline_graph = networkx.DiGraph()
            for ws_pipeline in workspace_pipelines:
                pipeline_graph.add_node(ws_pipeline.name)
                pipeline_graph.add_edges_from([(need, ws_pipeline.name)
                                               for need in ws_pipeline.needs])

            if not networkx.algorithms.dag.is_directed_acyclic_graph(pipeline_graph):
                logger.error("Workspace contains a circular dependency:")
                cycle = networkx.algorithms.cycles.find_cycle(pipeline_graph)
                cycle = [u for (u, v) in cycle]
                cycle.append(cycle[0])
                cycle = ' -> '.join(cycle)
                logger.error(f"  {cycle}")
                return ActionResultCode.FAILURE

            available_pipelines = \
                {p.name for p in workspace_pipelines} | set(completed_pipelines)
            for need, pipeline in pipeline_graph.edges:
                if need not in available_pipelines:
                    logger.error(f"Unmet dependency: [{pipeline}] needs"
                                 f" [{need}]")
                    return ActionResultCode.FAILURE

            with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
                active_futures = set()
                while len(workspace_pipelines) > 0:
                    for workspace_pipeline in workspace_pipelines.copy():
                        if all(n in completed_pipelines for n in
                               workspace_pipeline.needs):
                            pipeline: Pipeline = \
                                next(p for p in
                                     self.__workspace_pipelines[workspace_pipeline.path]
                                     if
                                     p.context.name == workspace_pipeline.name)
                            f = executor.submit(action, backends_context,
                                                pipeline, retries)
                            active_futures.add(f)
                            workspace_pipelines.remove(workspace_pipeline)

                    done, not_done = concurrent.futures.wait(active_futures,
                                                             return_when=concurrent.futures.FIRST_COMPLETED)
                    if any((success == ActionResultCode.FAILURE for success, _
                            in tuple(f.result() for f in done))):
                        # a pipeline failed, wait for results from all
                        # pipelines already submitted before stopping
                        done, not_done = concurrent.futures.wait(active_futures,
                                                                 return_when=concurrent.futures.ALL_COMPLETED)

                    active_futures = active_futures.difference(done)
                    for f in done:
                        success, pipeline = f.result()
                        if success == ActionResultCode.SUCCESS or success == ActionResultCode.PARTIAL_SUCCESS:
                            completed_pipelines.append(pipeline.context.name)
                        else:
                            failed_pipelines.append(pipeline.context.name)
                    if len(failed_pipelines) > 0:
                        break

            if len(failed_pipelines) > 0:
                logger.error(f"Some pipelines failed to finish:")
                for p in failed_pipelines:
                    logger.error(f"  {p}")
                if len(workspace_pipelines) > 0:
                    logger.warning(f"Pipelines that did not run due to"
                                   f" previous failures:")
                    for p in workspace_pipelines:
                        logger.warning(f"  {p.name}")
                return ActionResultCode.FAILURE
            return ActionResultCode.SUCCESS
        except:
            logger.error(f"Error occurred while trying to run pipelines")
            logger.error(traceback.format_exc())
            return ActionResultCode.FAILURE
        finally:
            self.__ws_pipelines_lock.release()

    def execute_pipelines(self, backends_context: BackendsContext,
                          filters: Optional[List[str]] = None,
                          reset_cache: Optional[bool] = False,
                          parallel_jobs: Optional[int] = None,
                          retries: Optional[int] = DEFAULT_RETRY_COUNT,
                          recursive: Optional[bool] = False) -> ActionResultCode:
        return self.__execute_pipelines_action(backends_context,
                                               functools.partial(self.__execute_pipeline_thread, reset_cache),
                                               filters, parallel_jobs, retries, recursive)

    def clean_pipelines(self, backends_context: BackendsContext,
                        filters: Optional[List[str]] = None,
                        reset_cache: Optional[bool] = True,
                        parallel_jobs: Optional[int] = None,
                        retries: Optional[int] = DEFAULT_RETRY_COUNT,
                        recursive: Optional[bool] = False,
                        rm_working_dir: Optional[bool] = False) -> ActionResultCode:
        return self.__execute_pipelines_action(backends_context,
                                               functools.partial(self.__clean_pipeline_thread,
                                                                 reset_cache, rm_working_dir),
                                               filters, parallel_jobs, retries, recursive)

    def execute_pipelines_action(self, backends_context: BackendsContext,
                                 action_type: ActionType,
                                 filters: Optional[List[str]] = None,
                                 parallel_jobs: Optional[int] = None,
                                 retries: Optional[int] = DEFAULT_RETRY_COUNT,
                                 recursive: Optional[bool] = False) -> ActionResultCode:
        return self.__execute_pipelines_action(backends_context,
                                               functools.partial(self.__execute_pipeline_action_thread, action_type),
                                               filters, parallel_jobs, retries, recursive)

    def clean_pipelines_action(self, backends_context: BackendsContext,
                               action_type: ActionType,
                               filters: Optional[List[str]] = None,
                               parallel_jobs: Optional[int] = None,
                               retries: Optional[int] = DEFAULT_RETRY_COUNT,
                               recursive: Optional[bool] = False) -> ActionResultCode:
        return self.__execute_pipelines_action(backends_context,
                                               functools.partial(self.__clean_pipeline_action_thread, action_type),
                                               filters, parallel_jobs, retries, recursive)
