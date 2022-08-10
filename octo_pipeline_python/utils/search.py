import inspect
import operator
import os
from typing import List, Optional, Set

from octo_pipeline_python.utils.logger import logger

MAX_DISTANCE = 2
PIPELINE_FOLDER = "pipeline"


class Search:
    @staticmethod
    def __find_pipeline_definition(starting_dir: str, filename: str, distance: int = 0) -> Optional[str]:
        if distance == MAX_DISTANCE:
            return None
        if os.path.exists(os.path.join(starting_dir, filename)):
            return os.path.join(starting_dir, filename)
        if os.path.exists(os.path.join(starting_dir, PIPELINE_FOLDER, filename)):
            return os.path.join(starting_dir, PIPELINE_FOLDER, filename)
        parent_dir = os.path.dirname(starting_dir)
        return Search.__find_pipeline_definition(parent_dir, filename, distance + 1)

    @staticmethod
    def search(starting_dir: str, filename: str) -> str:
        return Search.__find_pipeline_definition(starting_dir, filename)

    @staticmethod
    def search_by_name(filename: str, extra_search_paths: Optional[List[str]] = None) -> Optional[str]:
        if not extra_search_paths:
            extra_search_paths = []
        frames = inspect.getouterframes(inspect.currentframe())
        idx = 1
        while idx < len(frames) and "octo-pipeline-python" in frames[idx].filename:
            idx += 1
        if idx < len(frames):
            extra_search_paths.append(os.path.dirname(frames[idx].filename))
        file_path = None
        # Try to find by extra paths first
        for extra_path in extra_search_paths:
            if extra_path:
                # Try to find based on extra paths
                logger.debug(f"Trying to find file [{filename}] based on extra path [{extra_path}]")
                file_path = Search.search(extra_path, filename)
                if file_path:
                    logger.debug(f"Using extra path [{extra_path}] for [{filename}]")
                    break
        if not file_path:
            # Try and find by env vars
            for env in ["PWD", "WORKSPACE"]:
                if env in os.environ:
                    # Try to find based on PWD env var
                    logger.debug(f"Trying to find file [{filename}] based on env var [{env}={os.environ[env]}]")
                    file_path = Search.search(os.environ[env], filename)
                    if file_path:
                        logger.debug(f"Using env var [{env}] for [{filename}]")
                        break
        # Fallback to current dir
        if not file_path:
            file_path = Search.search(os.getcwd(), filename)
        return file_path

    @staticmethod
    def search_pipeline_name(hints: List[str], possible_pipelines: Set[str]) -> Optional[str]:
        paths = [os.getcwd()]
        paths.extend(hints)
        frames = inspect.getouterframes(inspect.currentframe())
        idx = 1
        while idx < len(frames) and "octo-pipeline-python" in frames[idx].filename:
            idx += 1
        if idx < len(frames):
            paths.append(os.path.dirname(frames[idx].filename))
        for env in ["PWD", "WORKSPACE"]:
            if env in os.environ:
                paths.append(os.environ[env])
        possible_pipelines_counters = {}
        for path in [p for p in paths if p]:
            for possibility in possible_pipelines:
                if possibility in path:
                    if possibility not in possible_pipelines_counters:
                        possible_pipelines_counters[possibility] = 0
                    possible_pipelines_counters[possibility] += 1
        if len(possible_pipelines_counters) == 0:
            return None
        return max(possible_pipelines_counters.items(), key=operator.itemgetter(1))[0]
