import getpass
from typing import List, Optional

from pydantic import BaseModel, Field


class AnsibleModel(BaseModel):
    playbooks: List[str] = Field(description="List of playbooks to play")
    extra_vars: Optional[str] = Field(description="Ansible extra vars for the playbooks")
    inventory: Optional[str] = Field(description="Path to inventory file")
    hosts: Optional[List[str]] = Field(description="Target Hosts to work with")
    become: bool = Field(description="Become sudo on execution", default=False)
    become_user: str = Field(description="Become user", default="root")
    remote_user: str = Field(description="Remote user to connect with", default=getpass.getuser())
    remote_password: Optional[str] = Field(description="Remote password to connect with")
    private_key_path: Optional[str] = Field(description="Private key to use for connection")
    connection: str = Field(description="Ansible connection type", default="ssh")
    timeout: int = Field(description="Command timeout", default=360)
    retry_count: int = Field(description="Playbook failure retry count", default=1)
