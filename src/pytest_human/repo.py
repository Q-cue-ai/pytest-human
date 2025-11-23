"""Utilities for manging project and repository information."""

import re
import site
from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.parse import quote as url_escape

import git
from exceptiongroup import suppress

from pytest_human.log import get_logger


class Repo:
    """Manages git repo information and project root detection."""

    def __init__(self) -> None:
        self.log = get_logger(__name__)
        self._git_repo = self._initialize_git_repo()
        self.project_root = self._get_project_root()
        self.repo_url = self._get_repo_url()
        self.ref_name = self._get_current_commit()

    def _initialize_git_repo(self) -> Optional[git.Repo]:
        """Initialize and return the git.Repo object if inside a git repository."""
        try:
            repo = git.Repo(search_parent_directories=True)
            return repo
        except git.GitError:
            self.log.debug("Not inside a Git repository.")
            return None

    def _get_git_repo_path(self) -> Optional[Path]:
        """Return the top-level path of the current Git repository."""

        if self._git_repo is None:
            return None

        return Path(self._git_repo.working_tree_dir)  # type: ignore

    def _search_for_project_root(self, start_path: Optional[Path] = None) -> Optional[Path]:
        """Search for the project root from start_path."""

        path = start_path or Path.cwd()

        root_indicators = [
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "pytest.ini",
            "requirements.txt",
        ]

        for folder in [path, *list(path.parents)]:
            for indicator in root_indicators:
                if (folder / indicator).is_file():
                    return folder
        return None

    def _get_project_root(self) -> Path:
        """Get the root path of the project.

        This is determined by finding the top-level Git repository path.
        If not inside a Git repository, searches for indicating files,
        fallsback to current dir.
        """
        git_repo_path = self._get_git_repo_path()
        if git_repo_path is not None:
            return git_repo_path

        project_root = self._search_for_project_root()
        if project_root is not None:
            return project_root

        self.log.debug("Falling back to current working directory as project root.")
        return Path.cwd()

    def _get_repo_remote(self) -> Optional[str]:
        """Get the URL of the remote origin of the Git repository."""
        repo = self._git_repo

        if repo is None:
            return None

        if "origin" in repo.remotes:
            url = repo.remotes.origin.url
            if "github.com" in url:
                return url
        for remote in repo.remotes:
            url = remote.url
            if "github.com" in url:
                return url
        return None

    def _get_repo_url(self) -> Optional[str]:
        """Get the GitHub URL of the repository."""
        remote = self._get_repo_remote()
        if remote is None:
            return None

        pattern = re.compile(
            r"""
            ^(?:                     # do not capture prefix
                https?://(?:www\.)github\.com/   # Match https://github.com/ addresses
                |                       # OR
                git@github\.com:        # Match SSH format git@github.com:
            )
            ([^/]+)                 # username / org
            /
            ([^/]+?)                # repo name
            (?:\.git)?$             # Remove .git suffix if present
            """,
            re.VERBOSE,
        )

        if not re.match(pattern, remote):
            return None

        return re.sub(pattern, r"https://github.com/\1/\2", remote)

    def _get_head_first_remote_commit(self) -> Optional[str]:
        try:
            repo = self._git_repo
            if repo is None:
                return None

            # first local commit that isn't on remote
            oldest_local_sha = repo.git.rev_list(
                "HEAD", "--not", "--remotes", max_count=1, reverse=True
            )

            if not oldest_local_sha:
                # All are remote commits
                return repo.head.commit.hexsha

            oldest_local_commit = repo.commit(oldest_local_sha)

            if oldest_local_commit.parents:
                pushed_ancestor = oldest_local_commit.parents[0]
                return pushed_ancestor.hexsha

            return None

        except git.GitCommandError:
            return None

    def _get_current_commit(self) -> Optional[str]:
        """Get the current commit hash of the Git repository."""
        # It's okay because it's cached for all tests
        repo = self._git_repo
        if repo is None:
            return None

        branch = None
        with suppress(TypeError):
            branch = repo.active_branch

        if branch:
            remote_branch = branch.tracking_branch()
            if remote_branch and remote_branch.is_valid():
                return remote_branch.commit.hexsha

        if first_remote := self._get_head_first_remote_commit():
            return first_remote

        for fallback in ["main", "master"]:
            with suppress(git.BadName):
                repo.commit(fallback)
                return fallback

        return None

    def is_repo_path(self, path: Path) -> bool:
        """Check if the given path is inside the project repository."""
        if self.project_root is None:
            return False

        if not path.is_relative_to(self.project_root):
            return False

        # third party package
        for site_path in [*site.getsitepackages(), site.getusersitepackages()]:
            if path.is_relative_to(Path(site_path)):
                return False

        return True

    def create_github_url(self, path: Path, line_num: Optional[int] = None) -> Optional[str]:
        """Create a GitHub URL for the given relative path in the repository."""
        if self.repo_url is None or self.ref_name is None:
            return None

        if not self.is_repo_path(path):
            return None

        relative_path = path.relative_to(self.project_root)

        path_component = PurePosixPath("blob") / self.ref_name / PurePosixPath(relative_path)
        path_in_url = url_escape(path_component.as_posix())

        url = f"{self.repo_url}/{path_in_url}"

        if line_num is not None:
            url += f"#L{line_num}"

        return url

    def relative_to_repo(self, path: Path) -> Path:
        """Get the path relative to the repository root."""
        if not path.is_relative_to(self.project_root):
            return path

        return path.relative_to(self.project_root)
