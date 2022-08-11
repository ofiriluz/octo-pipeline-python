import argparse
import os
import sys
from typing import Set

import git

from octo_pipeline_python.actions.action_result import ActionResultCode
from octo_pipeline_python.backends.backend_settings import BackendSettings
from octo_pipeline_python.commands.command import Command
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_description import \
    WorkspaceDescription


class PipelineCommand(Command):
    def define_command(self, subparsers) -> None:
        pipeline_parser = subparsers.add_parser("pipeline")
        pipeline_subparsers = pipeline_parser.add_subparsers(dest="pipeline_action")
        pipeline_subparsers.required = True
        init_pipeline = pipeline_subparsers.add_parser("init",
                                                       help="Tries to initialize an existing pipeline remotely")
        init_pipeline.add_argument("--org", help="Which organization to look for the pipeline repo", required=True)
        init_pipeline.add_argument("--name", help="Name of the pipeline", required=True)
        init_pipeline.add_argument("--head", help="Branch of the pipeline", default="master")
        init_pipeline.add_argument("--scm", help="Base SCM to go to look on", default="https://github.com")
        execute_parser = pipeline_subparsers.add_parser("execute", help="Executes the entire pipeline actions")
        execute_parser.add_argument("--reset-cache", help="Resets the cache and starts the pipeline from the beginning",
                                    action="store_true")
        pipeline_subparsers.add_parser("describe", help="Prints out a detailed description of the pipeline")
        pipeline_subparsers.add_parser("describe-actions", help="Prints out the list of actions on the pipeline")
        pipeline_subparsers.add_parser("clean", help="Cleans up all the actions that ran so far")
        pipeline_subparsers.add_parser("name", help="Prints out the name of the pipeline")
        pipeline_subparsers.add_parser("version", help="Prints out the version of the pipeline")
        pipeline_subparsers.add_parser("build_number", help="Prints out the build number of the pipeline")
        pipeline_subparsers.add_parser("scm", help="Prints out the scm of the pipeline")
        set_setting_parser = pipeline_subparsers.add_parser("set-setting",
                                                            help="Alters a given setting in the settings file")
        get_setting_parser = pipeline_subparsers.add_parser("get-setting",
                                                            help="Gets a setting for the settings file")
        backends_set_setting_subparser = set_setting_parser.add_subparsers(dest="backend")
        backends_set_setting_subparser.required = True
        backends_get_setting_subparser = get_setting_parser.add_subparsers(dest="backend")
        backends_get_setting_subparser.required = True
        backends: Set[str] = set()
        if self.workspace:
            self.workspace.workspace_state(quick=True)
            workspace_desc: WorkspaceDescription = self.workspace.describe_workspace()
            if workspace_desc.pipelines:
                for pipelines in workspace_desc.pipelines.values():
                    for pipeline in pipelines:
                        for action in pipeline.actions:
                            backends.update(action.backends)
        for backend in backends:
            backend_set_setting_parser = backends_set_setting_subparser.add_parser(backend)
            backend_set_setting_parser.add_argument("--key", help="Key to set for backend", required=True)
            backend_set_setting_parser.add_argument("--value", help="Value to set for backend", required=True)
            backend_get_setting_parser = backends_get_setting_subparser.add_parser(backend)
            backend_get_setting_parser.add_argument("--key", help="Key to get for backend", required=True)
        disable_step_parser = pipeline_subparsers.add_parser("disable-step",
                                                             help="Disables a step from being executed in a pipeline")
        enable_step_parser = pipeline_subparsers.add_parser("enable-step",
                                                            help="Enables a step to be executed "
                                                                 "in a pipeline if it was disabled beforehand")
        disable_step_subparsers = disable_step_parser.add_subparsers(dest="step")
        disable_step_subparsers.required = True
        enable_step_subparsers = enable_step_parser.add_subparsers(dest="step")
        enable_step_subparsers.required = True
        execute_parser = pipeline_subparsers.add_parser("execute-action", help="Executes a specific type of action")
        execute_subparsers = execute_parser.add_subparsers(dest="pipeline_execute_action")
        execute_subparsers.required = True
        clean_parser = pipeline_subparsers.add_parser("clean-action", help="Cleans up a specific type of action")
        clean_subparsers = clean_parser.add_subparsers(dest="pipeline_clean_action")
        clean_subparsers.required = True
        added_actions = []
        if self.workspace and self.workspace.singular_pipeline:
            for action in self.workspace.singular_pipeline.describe_pipeline().actions:
                for item in [action.action_type.value, action.action_name]:
                    if item and item not in added_actions:
                        execute_subparsers.add_parser(item)
                        clean_subparsers.add_parser(item)
                        disable_step_action_parser = disable_step_subparsers.add_parser(item)
                        enable_step_action_parser = enable_step_subparsers.add_parser(item)
                        disable_step_action_parser.add_argument("--backend",
                                                                help="Step disabled only for a specific backend")
                        disable_step_action_parser.add_argument("--cmd",
                                                                help="Step disabled only for a specific command")
                        enable_step_action_parser.add_argument("--backend",
                                                               help="Step disabled only for a specific backend")
                        enable_step_action_parser.add_argument("--cmd",
                                                               help="Step disabled only for a specific command")
                        added_actions.append(item)
        step_parser = pipeline_subparsers.add_parser("step", help="Step execution of the pipeline")
        step_subparsers = step_parser.add_subparsers(dest="step")
        step_subparsers.required = True
        step_subparsers.add_parser("next", help="Move to the next action in the pipeline")
        step_subparsers.add_parser("previous", help="Move to the previous action in the pipeline")
        step_subparsers.add_parser("current", help="Prints out the current action in the pipeline")
        step_subparsers.add_parser("execute", help="Executes the current action in the pipeline")
        step_subparsers.add_parser("execute-forward",
                                   help="Executes the current action in the pipeline and moves forward")
        step_subparsers.add_parser("clean", help="Cleans the current action in the pipeline")
        step_subparsers.add_parser("clean-backward",
                                   help="Cleans the current action in the pipeline and moves backwards")
        step_subparsers.add_parser("reset", help="Resets the steps to 0")

    def run_command(self, args: argparse.Namespace) -> ActionResultCode:
        from pipeline.pipeline import Pipeline
        if args.pipeline_action == "init":
            source_dir = os.path.join(os.getcwd(), args.name)
            if self.workspace:
                source_dir = os.path.join(self.workspace.context.source_dir, args.name)
                if self.workspace.has_pipeline(args.name):
                    logger.info(f"Pipeline [{args.name}] already exists, "
                                f"will only try to checkout to branch [{args.head}]")
                    try:
                        repo = git.Repo(source_dir)
                        repo.git.checkout(args.head)
                        return ActionResultCode.SUCCESS
                    except Exception as e:
                        logger.warning(f"Failed to checkout [{args.name}] to [{args.head}] - [{str(e)}]")
                        return ActionResultCode.FAILURE
            pipeline: Pipeline = \
                Pipeline.init_pipeline_to([args.org], args.name, args.scm, source_dir, args.head)
            if pipeline:
                logger.info("Successfully initialized pipeline")
                return ActionResultCode.SUCCESS
            else:
                logger.error("Failed to initialize pipeline")
            return ActionResultCode.FAILURE
        if not self.workspace:
            logger.error("Failed to initialize workspace / pipeline, cannot continue")
            return ActionResultCode.FAILURE
        if not self.workspace.singular_pipeline:
            logger.error("This is not a singular pipeline, but a workspace, "
                         "Please step into a specific pipeline and rerun the command")
            return ActionResultCode.FAILURE
        result = ActionResultCode.SUCCESS
        if args.pipeline_action == "execute":
            result = self.workspace.singular_pipeline.execute_pipeline(self.backends_context,
                                                                       self.workspace.context,
                                                                       args.reset_cache)
        elif args.pipeline_action == "describe":
            logger.set_verbose(False)
            sys.stdout.write(self.workspace.singular_pipeline.describe_pipeline().json(indent=4))
        elif args.pipeline_action == "describe-actions":
            logger.set_verbose(False)
            sys.stdout.write("\n".join([action.action_type for action in
                                        self.workspace.singular_pipeline.describe_pipeline().actions
                                        if self.workspace.singular_pipeline.context.surrounding in
                                        action.surroundings]))
        elif args.pipeline_action == "clean":
            self.workspace.singular_pipeline.cleanup_pipeline(self.backends_context, self.workspace.context)
        elif args.pipeline_action == "name":
            logger.set_verbose(False)
            sys.stdout.write(self.workspace.singular_pipeline.context.name)
        elif args.pipeline_action == "version":
            logger.set_verbose(False)
            sys.stdout.write(self.workspace.singular_pipeline.context.version)
        elif args.pipeline_action == "build_number":
            logger.set_verbose(False)
            sys.stdout.write(str(self.workspace.singular_pipeline.context.build_number))
        elif args.pipeline_action == "scm":
            logger.set_verbose(False)
            sys.stdout.write(self.workspace.singular_pipeline.context.scm)
        elif args.pipeline_action == "execute-action":
            result = self.workspace.singular_pipeline.execute_pipeline_action(args.pipeline_execute_action,
                                                                              self.backends_context,
                                                                              self.workspace.context)
        elif args.pipeline_action == 'clean-action':
            self.workspace.singular_pipeline.cleanup_pipeline_action(args.pipeline_clean_action,
                                                                     self.backends_context,
                                                                     self.workspace.context)
        elif args.pipeline_action == "disable-step":
            self.workspace.singular_pipeline.disable_pipeline_step(args.step,
                                                                   args.backend,
                                                                   args.cmd)
        elif args.pipeline_action == "enable-step":
            self.workspace.singular_pipeline.enable_pipeline_step(args.step,
                                                                  args.backend,
                                                                  args.cmd)
        elif args.pipeline_action == "set-setting":
            if not BackendSettings.set_setting(self.workspace.singular_pipeline.context,
                                               self.backends_context,
                                               self.workspace.context,
                                               args.backend, args.key, args.value):
                result = ActionResultCode.FAILURE
        elif args.pipeline_action == "get-setting":
            logger.set_verbose(False)
            value = BackendSettings.get_setting(self.workspace.singular_pipeline.context,
                                                self.backends_context,
                                                self.workspace.context,
                                                args.backend,
                                                args.key)
            if value:
                sys.stdout.write(str(value))
            else:
                sys.stdout.write(f"Could not find key [{args.key}] for backend [{args.backend}]")
                result = ActionResultCode.FAILURE
        elif args.pipeline_action == "step":
            if args.step == "next":
                self.workspace.singular_pipeline.step_next_pipeline_action()
            elif args.step == "previous":
                self.workspace.singular_pipeline.step_previous_pipeline_action()
            elif args.step == "current":
                logger.set_verbose(False)
                action, idx = self.workspace.singular_pipeline.current_pipeline_step()
                if action:
                    sys.stdout.write(f"{idx} - {action.action_type}")
                else:
                    sys.stdout.write(f"{idx}")
            elif args.step == "execute":
                result = self.workspace.singular_pipeline.step_execute_pipeline_action(self.backends_context,
                                                                                       self.workspace.context)
            elif args.step == "execute-forward":
                result = self.workspace.singular_pipeline.step_execute_pipeline_action(self.backends_context,
                                                                                       self.workspace.context)
                if result == ActionResultCode.SUCCESS or result == ActionResultCode.PARTIAL_SUCCESS:
                    self.workspace.singular_pipeline.step_next_pipeline_action()
            elif args.step == "clean":
                self.workspace.singular_pipeline.step_clean_pipeline_action(self.backends_context,
                                                                            self.workspace.context)
            elif args.step == "clean-backward":
                self.workspace.singular_pipeline.step_clean_pipeline_action(self.backends_context,
                                                                            self.workspace.context)
                self.workspace.singular_pipeline.step_previous_pipeline_action()
            elif args.step == "reset":
                self.workspace.singular_pipeline.reset_pipeline_steps()
        return result

    def can_run_command(self, command_name: str, args: argparse.Namespace) -> bool:
        return command_name == 'pipeline'
