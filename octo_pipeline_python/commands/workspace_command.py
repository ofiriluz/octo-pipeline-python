import argparse
import multiprocessing
import os
import sys
from typing import Any, Dict, Final, List, NamedTuple, Set, Tuple

import git
from colorama import Back, Fore, Style

from octo_pipeline_python.actions.action_result import ActionResultCode
from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.commands.command import Command
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace import (DEFAULT_RETRY_COUNT,
                                                      Workspace)
from octo_pipeline_python.workspace.workspace_pipeline import WorkspacePipeline


class WorkspaceCommand(Command):
    @staticmethod
    def __print_pipelines(pipelines: Dict[str, List[WorkspacePipeline]], title: str, title_color: str, color: str):
        sys.stdout.write(f"{Fore.WHITE}{title_color}{Style.BRIGHT}"
                         f"============ {title} ============"
                         f"{Style.RESET_ALL}{Fore.RESET}\n")
        for path, path_pipelines in pipelines.items():
            sys.stdout.write(f"{color}{Style.BRIGHT}"
                             f"\t{path}:"
                             f"{Style.RESET_ALL}{Fore.RESET}\n")
            for pipeline in path_pipelines:
                sys.stdout.write(f"{color}"
                                 f"\t\t{pipeline.name}"
                                 f"{Fore.RESET}\n")
        sys.stdout.write("\n")

    def __add_execute_parser(self, workspace_subparsers) -> None:
        execute_parser = workspace_subparsers.add_parser("execute")
        pipelines: Set["str"] = self.workspace.describe_pipelines()
        pipelines_with_all = pipelines.union({"all"})
        execute_parser.add_argument(
            "pipeline",
            help=f"Pipeline to execute, 'all' or one of: {' '.join(pipelines)}",
            choices=pipelines_with_all,
            metavar="PIPELINE",
        )
        execute_parser.add_argument(
            "--reset-cache",
            help=f"Resets the cache of the pipeline",
            action="store_true",
        )
        execute_parser.add_argument(
            "-j", "--jobs", help="Number of parallel jobs", type=int, default=None
        )
        execute_parser.add_argument(
            "--retries",
            help="Number of retries if failing",
            default=DEFAULT_RETRY_COUNT,
            type=int,
        )
        execute_parser.add_argument(
            "-r",
            "--recursive",
            help="Recursive run pipelines per the needs",
            action="store_true",
        )

    def __add_execute_action_parser(self, workspace_subparsers) -> None:
        execute_action_parser = workspace_subparsers.add_parser("execute-action")
        execute_action_subparsers = execute_action_parser.add_subparsers(dest="execute_action")
        pipelines = self.workspace.describe_pipelines()
        pipelines.add("all")
        for pipeline_name in pipelines:
            pipeline = self.workspace.pipeline(pipeline_name)
            pipeline_execute_parser = execute_action_subparsers.add_parser(pipeline_name,
                                                                           help=f"Execute the {pipeline_name} pipeline")
            pipeline_execute_action_subparsers = pipeline_execute_parser.add_subparsers(dest="execute_action_type")
            if pipeline:
                added_actions = []
                for action in pipeline.describe_pipeline().actions:
                    for item in [action.action_type.value, action.action_name]:
                        if item and item not in added_actions:
                            action_parser = pipeline_execute_action_subparsers.add_parser(item)
                            action_parser.add_argument("-j", "--jobs", help="Number of parallel jobs",
                                                       default=None, type=int)
                            action_parser.add_argument("-r", "--recursive",
                                                       help="Recursive run pipelines per the needs",
                                                       action="store_true")
                            action_parser.add_argument("--retries", help="Number of retries if failing",
                                                       default=DEFAULT_RETRY_COUNT, type=int)
                            added_actions.append(item)
            else:
                for action_type in ActionType:
                    action_parser = pipeline_execute_action_subparsers.add_parser(action_type)
                    action_parser.add_argument("-j", "--jobs", help="Number of parallel jobs",
                                               default=None, type=int)
                    action_parser.add_argument("-r", "--recursive",
                                               help="Recursive run pipelines per the needs",
                                               action="store_true")
                    action_parser.add_argument("--retries", help="Number of retries if failing",
                                               default=DEFAULT_RETRY_COUNT, type=int)

    def __add_clean_parser(self, workspace_subparsers) -> None:
        clean_parser = workspace_subparsers.add_parser("clean")
        clean_subparsers = clean_parser.add_subparsers(dest="clean_action",
                                                       required=True)
        pipelines = self.workspace.describe_pipelines()
        pipelines.add("all")
        for pipeline_name in pipelines:
            pipeline_clean_parser = clean_subparsers.add_parser(pipeline_name,
                                                                help=f"Clean the {pipeline_name} pipeline")
            pipeline_clean_parser.add_argument("--no-reset-cache",
                                               help=f"Do not resets the cache of {pipeline_name} pipeline",
                                               action="store_false")
            pipeline_clean_parser.add_argument("-j", "--jobs", help="Number of parallel jobs",
                                               default=None)
            pipeline_clean_parser.add_argument("--retries", help="Number of retries if failing",
                                               default=DEFAULT_RETRY_COUNT, type=int)
            pipeline_clean_parser.add_argument("-r", "--recursive", help="Recursive run pipelines per the needs",
                                               action="store_true")

    def __add_clean_action_parser(self, workspace_subparsers) -> None:
        clean_action_parser = workspace_subparsers.add_parser("clean-action")
        clean_action_subparsers = clean_action_parser.add_subparsers(dest="clean_action")
        pipelines = self.workspace.describe_pipelines()
        pipelines.add("all")
        for pipeline_name in pipelines:
            pipeline = self.workspace.pipeline(pipeline_name)
            pipeline_clean_parser = clean_action_subparsers.add_parser(pipeline_name,
                                                                       help=f"Clean the {pipeline_name} pipeline")
            pipeline_clean_action_subparsers = pipeline_clean_parser.add_subparsers(dest="clean_action_type")
            added_actions = []
            if pipeline:
                for action in pipeline.describe_pipeline().actions:
                    for item in [action.action_type.value, action.action_name]:
                        if item and item not in added_actions:
                            action_parser = pipeline_clean_action_subparsers.add_parser(item)
                            action_parser.add_argument("-j", "--jobs", help="Number of parallel jobs",
                                                       default=None, type=int)
                            action_parser.add_argument("-r", "--recursive",
                                                       help="Recursive run pipelines per the needs",
                                                       action="store_true")
                            action_parser.add_argument("--retries", help="Number of retries if failing",
                                                       default=DEFAULT_RETRY_COUNT, type=int)
                            added_actions.append(item)
            else:
                for action_type in ActionType:
                    action_parser = pipeline_clean_action_subparsers.add_parser(action_type)
                    action_parser.add_argument("-j", "--jobs", help="Number of parallel jobs",
                                               default=None, type=int)
                    action_parser.add_argument("-r", "--recursive",
                                               help="Recursive run pipelines per the needs",
                                               action="store_true")
                    action_parser.add_argument("--retries", help="Number of retries if failing",
                                               default=DEFAULT_RETRY_COUNT, type=int)

    def define_command(self, subparsers) -> None:
        workspace_parser = subparsers.add_parser("workspace")
        workspace_subparsers = workspace_parser.add_subparsers(dest="workspace_action")
        workspace_subparsers.required = True
        workspace_subparsers.add_parser("describe", help="Describe the workspace")
        workspace_subparsers.add_parser("describe-pipelines", help="Describe the workspace")
        state_parser = workspace_subparsers.add_parser("state", help="Print out the state of the workspace")
        state_parser.add_argument("--quick", help="Quickly evaluate the state without working with remote repo",
                                  action="store_true")

        class ParserArguments(NamedTuple):
            args: Tuple[Any, ...] = tuple()
            kwargs: Dict[str, Any] = {}

        sync_arguments: Final[Tuple[ParserArguments, ...]] = (
            ParserArguments(args=("-j", "--jobs",),
                            kwargs={"help": "Number of parallel jobs", "type": int,
                                    "default": min(multiprocessing.cpu_count() / 2, 8)}),
            ParserArguments(args=("--retries",),
                            kwargs={"help": "Number of retries if failing to sync pipeline",
                                    "type": int, "default": 3, "dest": "sync_retry"}),
            ParserArguments(args=("--backoff-factor",),
                            kwargs={"help": "Backoff factor on retrying failed pipeline", "type": float,
                                    "default": 1.3}),
        )
        sync_parser = workspace_subparsers.add_parser("sync", help="Sync the workspace")
        sync_parser.add_argument("--no-code-sync", help="Do not try and git pull for latest code", action="store_true")

        init_pipeline = workspace_subparsers.add_parser("init",
                                                        help="Tries to initialize an existing pipeline remotely")
        init_pipeline.add_argument("--org", help="Which organization to look for the pipeline repo", required=True)
        init_pipeline.add_argument("--name", help="Name of the pipeline", required=True)
        init_pipeline.add_argument("--head", help="Branch of the pipeline", default="master")
        init_pipeline.add_argument("--scm", help="Base SCM to go to look on", default="https://github.com")
        init_pipeline.add_argument("--no-sync", help="Do not sync the workspace after cloning", action="store_true")
        init_pipeline.add_argument("--workspace-dir", help="A new folder name to create the new workspace in",
                                   default=".")

        for arg in sync_arguments:
            sync_parser.add_argument(*arg.args, **arg.kwargs)
            init_pipeline.add_argument(*arg.args, **arg.kwargs)
        if self.workspace:
            self.__add_execute_parser(workspace_subparsers)
            self.__add_execute_action_parser(workspace_subparsers)
            self.__add_clean_parser(workspace_subparsers)
            self.__add_clean_action_parser(workspace_subparsers)

    def run_command(self, args: argparse.Namespace) -> ActionResultCode:
        result = ActionResultCode.SUCCESS
        if args.workspace_action == "init":
            source_dir = os.getcwd()
            if self.workspace and self.workspace.context.source_dir == source_dir:
                if self.workspace.context.name == args.name:
                    source_dir = os.path.join(self.workspace.context.source_dir, args.name)
                    logger.info(f"Workspace [{args.name}] already exists, "
                                f"will only try to checkout to branch [{args.head}] and sync")
                    try:
                        repo = git.Repo(source_dir)
                        repo.git.checkout(args.head)
                    except:
                        logger.warning(f"Failed to checkout [{args.name}] to [{args.head}]")
                        return ActionResultCode.FAILURE
                else:
                    logger.error(f"Cannot initialize one workspace in another workspace folder, "
                                 f"please move to another folder")
                    return ActionResultCode.FAILURE
            else:
                source_dir = os.path.join(source_dir, args.workspace_dir)
                try:
                    os.makedirs(source_dir, exist_ok=False)
                    logger.info(f"Workspace initializes to [{source_dir}].")
                except FileExistsError as os_err:
                    if os.path.isfile(source_dir):
                        logger.error(f"{source_dir}] is an file and not an empty or new directory name")
                    elif len(os.listdir(source_dir)) != 0:
                        logger.error(f"Provided destination [{source_dir}] is not an empty directory")
                    return ActionResultCode.FAILURE
                self.workspace: Workspace = \
                    Workspace.init_workspace_to(args.org, args.name, args.scm, source_dir, args.head)
            if self.workspace:
                logger.info("Successfully initialized workspace")
                if not args.no_sync:
                    unresolved: List[str] = self.workspace.sync_workspace(parallel_jobs=args.jobs,
                                                                          sync_retry=args.sync_retry,
                                                                          backoff_factor=args.backoff_factor)
                    if len(unresolved) > 0:
                        logger.error("Failed to fully sync workspace")
                    else:
                        logger.info("Synced workspace successfully")
                        return ActionResultCode.SUCCESS
                else:
                    return ActionResultCode.SUCCESS
            else:
                logger.error("Failed to initialize workspace")
            return ActionResultCode.FAILURE
        if not self.workspace:
            logger.error("Failed to initialize workspace, cannot continue")
            return ActionResultCode.FAILURE
        if args.workspace_action == "describe":
            logger.set_verbose(False)
            sys.stdout.write(self.workspace.describe_workspace().json(indent=4))
        elif args.workspace_action == "describe-pipelines":
            logger.set_verbose(False)
            sys.stdout.write("\n".join(self.workspace.describe_pipelines()))
        elif args.workspace_action == "state":
            state = self.workspace.workspace_state(args.quick)
            WorkspaceCommand.__print_pipelines(state.unresolved_pipelines, "Unresolved Pipelines",
                                               Back.WHITE, Fore.WHITE)
            WorkspaceCommand.__print_pipelines(state.unsynced_pipelines, "Unsynced Pipelines",
                                               Back.YELLOW, Fore.YELLOW)
            WorkspaceCommand.__print_pipelines(state.synced_pipelines, "Synced Pipelines",
                                               Back.CYAN, Fore.CYAN)
            WorkspaceCommand.__print_pipelines(state.read_only_pipelines, "Read Only Pipelines",
                                               Back.MAGENTA, Fore.MAGENTA)
            WorkspaceCommand.__print_pipelines(state.failed_pipelines, "Failed Pipelines",
                                               Back.RED, Fore.RED)
            WorkspaceCommand.__print_pipelines(state.completed_pipelines, "Completed Pipelines",
                                               Back.GREEN, Fore.GREEN)
        elif args.workspace_action == "sync":
            unresolved: List[str] = self.workspace.sync_workspace(args.no_code_sync, parallel_jobs=args.jobs,
                                                                  sync_retry=args.sync_retry,
                                                                  backoff_factor=args.backoff_factor)
            if len(unresolved) > 0:
                logger.error("Failed to fully sync workspace")
                result = ActionResultCode.FAILURE
            else:
                logger.info("Synced workspace successfully")
        elif args.workspace_action == "execute":
            pipeline_name = args.pipeline
            if pipeline_name == "all":
                result = self.workspace.execute_pipelines(self.backends_context, [],
                                                          args.reset_cache, args.jobs,
                                                          args.retries, args.recursive)
            else:
                result = self.workspace.execute_pipelines(self.backends_context, [pipeline_name],
                                                          args.reset_cache, args.jobs,
                                                          args.retries, args.recursive)
        elif args.workspace_action == "execute-action":
            pipeline_name = args.execute_action
            action_type = args.execute_action_type
            if pipeline_name == "all":
                result = self.workspace.execute_pipelines_action(self.backends_context, action_type, [],
                                                                 args.jobs, args.retries, args.recursive)
            else:
                result = self.workspace.execute_pipelines_action(self.backends_context, action_type, [pipeline_name],
                                                                 args.jobs, args.retries, args.recursive)
        elif args.workspace_action == "clean":
            pipeline_name = args.clean_action
            if pipeline_name == "all":
                result = self.workspace.clean_pipelines(self.backends_context, [],
                                                        args.no_reset_cache, args.jobs,
                                                        args.retries, args.recursive,
                                                        rm_working_dir=True)
            else:
                result = self.workspace.clean_pipelines(self.backends_context, [pipeline_name],
                                                        args.no_reset_cache, args.jobs,
                                                        args.retries, args.recursive,
                                                        rm_working_dir=False)
        elif args.workspace_action == "clean-action":
            pipeline_name = args.clean_action
            action_type = args.clean_action_type
            if pipeline_name == "all":
                result = self.workspace.clean_pipelines_action(self.backends_context, action_type, [],
                                                               args.jobs, args.retries, args.recursive)
            else:
                result = self.workspace.clean_pipelines_action(self.backends_context, action_type, [pipeline_name],
                                                               args.jobs, args.retries, args.recursive)
        return result

    def can_run_command(self, command_name: str, args: argparse.Namespace) -> bool:
        return command_name == 'workspace'
