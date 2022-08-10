import getpass
import os
import re
from typing import Final, Optional

from git import Repo

PROJECT_DIR_KEY: Final[str] = 'PROJECT_DIR'


# pylint: disable=too-many-arguments
def create_stack_name(user_name: str, base_name: str, project_path: Optional[str] = None, branch_name: Optional[str] = None,
                      remote_master: Optional[bool] = False, prefix: Optional[str] = None) -> str:
    if branch_name is None:
        branch_name = read_git_branch(project_path)
    if remote_master and branch_name.lower().startswith('pr-'):
        branch_name = 'master'
    if prefix is None:
        prefix = ''
    # remove special characters from branch name
    branch_name = ''.join(e for e in branch_name if e.isalnum()).capitalize()
    build_id = '' if branch_name.lower() in ('master', 'main') else os.environ.get('BUILD_NUMBER') if 'BUILD_NUMBER' in os.environ else ''
    stack_name: str = f'{prefix}{user_name}{base_name}{branch_name}{build_id}'
    return stack_name


def get_alphanumeric_username() -> str:
    return re.sub(r'\W+', '', getpass.getuser().capitalize())


def get_stack_name(base_name: str, project_path: Optional[str] = None, branch_name: Optional[str] = None,
                   remote_master: Optional[bool] = False, prefix: Optional[str] = None) -> str:
    user_name = get_alphanumeric_username()
    return create_stack_name(user_name, base_name, project_path, branch_name, remote_master, prefix)


# pylint: disable=too-many-arguments
def get_shortened_stack_name(base_name: str, project_path: Optional[str] = None, branch_name: Optional[str] = None,
                             remote_master: Optional[bool] = False, prefix: Optional[str] = None, max_user_name_length: int = 7) -> str:

    user_name = get_alphanumeric_username()[:max_user_name_length]
    return create_stack_name(user_name, base_name, project_path, branch_name, remote_master, prefix)


def read_git_branch(project_path: str = None) -> str:
    # in Jenkins git branch name is taken from environment variable
    branch_name: Optional[str] = os.environ.get('GIT_BRANCH') if 'GIT_BRANCH' in os.environ else None
    if branch_name:
        return branch_name

    if not project_path:
        project_path = os.environ[PROJECT_DIR_KEY]
    # load git branch name in development environment
    repo = Repo(project_path)
    return repo.active_branch.name
