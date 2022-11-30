import distutils.spawn
import os
import subprocess
import tempfile
import uuid
from typing import Final, Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.ansible.models import AnsibleModel
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

WINRM_PORT: Final[int] = 5986
INVENTORY_TEMPLATE: Final[str] = """
[env_machines]
{hosts}

[env_machines:vars]
{extra_vars}
"""


class AnsiblePlay(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        return True

    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        ansible_args: AnsibleModel = backend.backend_args(backends_context,
                                                          pipeline_context,
                                                          workspace_context,
                                                          self.action_type,
                                                          action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running play action")
        temp_folder = tempfile.gettempdir()
        temp_inventory_file = os.path.join(temp_folder, f"{str(uuid.uuid4())}.ini")
        inventory_path = temp_inventory_file
        try:
            logger.info(f"Running ansible playbooks [{ansible_args.playbooks}]")
            extra_vars = {
                "ansible_connection": ansible_args.connection,
                "ansible_command_timeout": ansible_args.timeout,
                "ansible_timeout": ansible_args.timeout
            }
            if ansible_args.connection == "winrm":
                extra_vars.update({
                    "ansible_winrm_connection_timeout": ansible_args.timeout,
                    "ansible_winrm_operation_timeout_sec": ansible_args.timeout,
                    "ansible_winrm_read_timeout_sec": ansible_args.timeout,
                    "ansible_winrm_scheme": "https",
                    "ansible_winrm_port": WINRM_PORT,
                    "ansible_winrm_transport": "ntlm",
                    "ansible_winrm_user": ansible_args.remote_user,
                    "ansible_winrm_password": ansible_args.remote_password,
                    "ansible_winrm_server_cert_validation": "ignore",
                    "ansible_shell_type": "powershell"
                })
            elif ansible_args.connection == "ssh":
                extra_vars.update({
                    "ansible_become": ansible_args.become,
                    "ansible_become_user": ansible_args.become_user,
                    "ansible_ssh_timeout": ansible_args.timeout,
                    "ansible_ssh_host_key_checking": "no",
                    "ansible_ssh_user": ansible_args.remote_user
                })
                if ansible_args.private_key_path:
                    extra_vars.update({
                        "ansible_ssh_private_key_file": ansible_args.private_key_path,
                    })
                if ansible_args.remote_password:
                    extra_vars.update({
                        "ansible_ssh_password": ansible_args.remote_password,
                    })
            if ansible_args.extra_vars:
                if isinstance(ansible_args.extra_vars, str):
                    ansible_args.extra_vars = {v.split('=')[0].strip(): v.split('=')[1].strip() for v in ansible_args.extra_vars.split()}
                extra_vars.update(ansible_args.extra_vars)
            logger.info(f"Using extra vars [{extra_vars.keys()}]")
            extra_vars_str = ' '.join([f"{k}={str(v)}" for k, v in extra_vars.items()])
            if ansible_args.inventory:
                inventory_path = ansible_args.inventory
            elif ansible_args.hosts:
                hosts = '\n'.join(ansible_args.hosts)
                extra_vars_str = '\n'.join([f"{k}={str(v)}" for k, v in extra_vars.items()])
                with open(temp_inventory_file, "w") as f:
                    f.write(INVENTORY_TEMPLATE.format(hosts=hosts, extra_vars=extra_vars_str))
            retry_count = ansible_args.retry_count
            if not distutils.spawn.find_executable('ansible-playbook'):
                return ActionResult(action_type=self.action_type,
                                    result=[f"Failed to find ansible playbook executable"],
                                    result_code=ActionResultCode.FAILURE)
            for playbook in ansible_args.playbooks:
                while retry_count > 0:
                    if ansible_args.inventory:
                        p = pipeline_context.run_contextual(f"ansible-playbook -i {inventory_path} --extra-vars=\"{extra_vars_str}\" {playbook}",
                                                            universal_newlines=True, stdout=subprocess.PIPE)
                    elif ansible_args.hosts:
                        p = pipeline_context.run_contextual(f"ansible-playbook -i {inventory_path} {playbook}",
                                                            universal_newlines=True, stdout=subprocess.PIPE)
                    else:
                        p = pipeline_context.run_contextual(f"ansible-playbook --extra-vars=\"{extra_vars_str}\" {playbook}",
                                                            universal_newlines=True, stdout=subprocess.PIPE)
                    for stdout_line in iter(p.stdout.readline, ""):
                        if stdout_line.strip():
                            logger.info(stdout_line.strip())
                    p.stdout.close()
                    return_code = p.wait()
                    if return_code != 0:
                        retry_count = retry_count - 1
                        continue
                    break
            if retry_count <= 0:
                return ActionResult(action_type=self.action_type,
                                    result=[f"Failed to run ansible playbook [{return_code}]"],
                                    result_code=ActionResultCode.FAILURE)
            return ActionResult(action_type=self.action_type,
                                result=[],
                                result_code=ActionResultCode.SUCCESS)
        finally:
            if os.path.exists(temp_inventory_file):
                os.remove(temp_inventory_file)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        pass

    @property
    def action_type(self) -> ActionType:
        return ActionType.Play
