import argparse
import sys
from typing import Set

from octo_pipeline_python.actions.action_result import ActionResultCode
from octo_pipeline_python.commands.command import Command
from octo_pipeline_python.utils.logger import logger


class BackendsCommand(Command):
    def define_command(self, subparsers) -> None:
        from workspace.workspace_description import WorkspaceDescription
        backends_parser = subparsers.add_parser("backends")
        backends_subparsers = backends_parser.add_subparsers(dest="backend")
        backends_subparsers.required = True
        backends_subparsers.add_parser("init", help="Initializes the pipeline backends")
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
            backend_parser = backends_subparsers.add_parser(backend)
            backend_subparsers = backend_parser.add_subparsers(dest="backend_action")
            backend_subparsers.required = True
            authenticate_parser = backend_subparsers.add_parser("authenticate", help="Authenticate to a backend")
            username_required = False
            if backend == "conan":
                username_required = True
            authenticate_parser.add_argument("--username", help="Username to authenticate with",
                                             required=username_required, type=str)
            authenticate_parser.add_argument("--secret", help="Secret to authenticate with",
                                             required=True, type=str)
            authenticate_parser.add_argument("--target", help="Target to authenticate to",
                                             required=False, type=str, default=None)
            authenticate_parser.add_argument("--certificate", help="Certificate to use for authentication",
                                             required=False, type=str, default=None)
            backend_subparsers.add_parser("describe", help="Prints out a description of the backend")
            backend_subparsers.add_parser("working-dir", help="Prints out the working directory of the backend")
            get_parser = backend_subparsers.add_parser("get",
                                                       help="Gets a specific key from the context of the backend")
            get_parser.add_argument("--key", required=True, type=str,
                                    help="Which key to get from the backend")

    def run_command(self, args: argparse.Namespace) -> ActionResultCode:
        from backends.backend_auth_details import BackendAuthDetails
        result: ActionResultCode = ActionResultCode.SUCCESS
        if args.backend == "init":
            result = self.workspace.singular_pipeline.initialize_pipeline(self.backends_context,
                                                                          self.workspace.context)
        elif args.backend_action == "authenticate":
            auth_details: BackendAuthDetails = BackendAuthDetails(username=args.username,
                                                                  secret=args.secret,
                                                                  target=args.target,
                                                                  certificate=args.certificate)
            # Get all the context's in the workspace and authenticate with them
            pipeline_contexts = []
            if self.workspace:
                if self.workspace.singular_pipeline:
                    pipeline_contexts.append(self.workspace.singular_pipeline.context)
                else:
                    for pipelines in self.workspace.workspace_pipelines.values():
                        for pipeline in pipelines:
                            pipeline_contexts.append(pipeline.context)
            if len(pipeline_contexts) == 0:
                result = self.backends_context.authenticate_backend(args.backend, auth_details,
                                                                    self.workspace.context, None)
            else:
                for context in pipeline_contexts:
                    result = self.backends_context.authenticate_backend(args.backend, auth_details,
                                                                        self.workspace.context, context)
                    if result != ActionResultCode.SUCCESS:
                        break
            if result == ActionResultCode.SUCCESS:
                logger.info(f"Authenticated successfully to [{args.backend}]")
            else:
                logger.error(f"Failed to authenticate to [{args.backend}]")
        elif args.backend_action == "describe":
            logger.set_verbose(False)
            sys.stdout.write(str(self.backends_context.describe_backend(args.backend, self.workspace.context)))
        elif args.backend_action == 'get':
            logger.set_verbose(False)
            sys.stdout.write(self.backends_context.backend_context_attribute(args.backend,
                                                                             args.key, self.workspace.context))
        elif args.backend_action == 'working-dir':
            logger.set_verbose(False)
            sys.stdout.write(self.backends_context.describe_backend(args.backend, self.workspace.context).working_dir)
        return result

    def can_run_command(self, command_name: str, args: argparse.Namespace) -> bool:
        return command_name == 'backends'
