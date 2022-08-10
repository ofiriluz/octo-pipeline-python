import os
import re
from typing import List, Optional

import git

from octo_pipeline_python.utils.logger import logger


class GitUtils:
    @staticmethod
    def create_ssh_scm_for(base_scm: str, org: str, name: str) -> str:
        if base_scm.startswith("http://") or base_scm.startswith("https://"):
            base_scm = re.sub("(https://)|(http://)", "git@", base_scm)
        base_scm = f"{base_scm}:{org}/{name}"
        return base_scm

    @staticmethod
    def get_scm_for(path: str) -> Optional[List[str]]:
        try:
            repo = git.Repo(path)
            urls = []
            for remote in repo.remotes:
                urls.extend([str(url) for url in remote.urls])
            return urls
        except git.exc.InvalidGitRepositoryError:
            pass
        return None

    @staticmethod
    def get_head_branch(path: str) -> Optional[str]:
        try:
            repo = git.Repo(path)
            return str(repo.active_branch)
        except:
            if "BRANCH_NAME" in os.environ:
                return os.environ["BRANCH_NAME"]
        return ""

    @staticmethod
    def get_head_commit(path: str) -> Optional[str]:
        try:
            repo = git.Repo(path)
            return str(repo.active_branch.commit)
        except:
            if "GIT_COMMIT" in os.environ:
                return os.environ["GIT_COMMIT"]
        return ""

    @staticmethod
    def checkout_to_branch(path: str, branch: str) -> bool:
        try:
            repo = git.Repo(path)
            if repo.active_branch != branch:
                repo.git.checkout(branch)
            return True
        except:
            pass
        return False

    @staticmethod
    def clone_and_checkout(scm: str, org: str, name: str, to_path, branch: str) -> Optional[str]:
        ssh_scm = GitUtils.create_ssh_scm_for(scm, org, name)
        try:
            logger.info(f"Trying to checkout [{name}] from org [{org}] ")
            repo = git.Repo.clone_from(ssh_scm, to_path)
            repo.git.checkout(branch)
            return ssh_scm
        except:
            pass
        return None

    @staticmethod
    def is_behind_on_commits(path: str, remote: str = "origin") -> bool:
        try:
            repo = git.Repo(path)
            head_branch = repo.active_branch
            repo.git.fetch(remote)
            commits_behind = sum(1 for c in repo.iter_commits(f"{head_branch}..{remote}/{head_branch}"))
            if commits_behind > 0:
                return True
            return False
        except:
            pass
        return True

    @staticmethod
    def is_ahead_on_commits(path: str, remote: str = "origin") -> bool:
        try:
            repo = git.Repo(path)
            head_branch = repo.active_branch
            repo.git.fetch(remote)
            commits_ahead = sum(1 for c in repo.iter_commits(f"{remote}/{head_branch}..{head_branch}"))
            if commits_ahead > 0:
                return True
            return False
        except:
            pass
        return True

    @staticmethod
    def pull_latest_code(path: str, remote: str = "origin") -> bool:
        try:
            repo = git.Repo(path)
            remote = repo.remote(remote)
            remote.pull(repo.active_branch)
            return True
        except:
            pass
        return False
