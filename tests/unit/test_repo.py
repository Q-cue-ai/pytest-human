from pathlib import Path

import git
import pytest

from pytest_human.repo import Repo


def test_repo_init_git(pytester: pytest.Pytester) -> None:
    git.Repo.init(pytester.path)
    repo = Repo()
    assert repo.project_root == pytester.path


def test_project_root_git(pytester: pytest.Pytester) -> None:
    git.Repo.init(pytester.path)
    repo = Repo()
    assert repo.project_root == pytester.path


def test_get_repo_url_github(pytester: pytest.Pytester) -> None:
    r = git.Repo.init(pytester.path)
    r.create_remote("origin", "https://github.com/user/repo.git")
    repo = Repo()
    assert repo.repo_url == "https://github.com/user/repo"


def test_get_repo_url_ssh(pytester: pytest.Pytester) -> None:
    r = git.Repo.init(pytester.path)
    r.create_remote("origin", "git@github.com:user/repo.git")
    repo = Repo()
    assert repo.repo_url == "https://github.com/user/repo"


def test_get_repo_url_non_github(pytester: pytest.Pytester) -> None:
    r = git.Repo.init(pytester.path)
    r.create_remote("origin", "git@gitlab.com:user/repo.git")
    repo = Repo()
    assert repo.repo_url is None


def test_get_repo_url_no_remote(pytester: pytest.Pytester) -> None:
    git.Repo.init(pytester.path)
    repo = Repo()
    assert repo.repo_url is None


def test_get_current_commit(pytester: pytest.Pytester) -> None:
    r = git.Repo.init(pytester.path)
    (pytester.path / "file.txt").touch()
    r.index.add(["file.txt"])
    r.index.commit("Initial commit")
    repo = Repo()
    # should be commit hash, but master because there's no remote branch
    assert repo.ref_name == "master"


def test_is_repo_path(pytester: pytest.Pytester) -> None:
    git.Repo.init(pytester.path)
    repo = Repo()
    assert repo.is_repo_path(pytester.path / "file.txt")
    assert not repo.is_repo_path(Path("/total/not/in/tmp.txt"))


def test_relative_to_repo(pytester: pytest.Pytester) -> None:
    git.Repo.init(pytester.path)
    repo = Repo()
    assert repo.relative_to_repo(pytester.path / "dir" / "file.txt") == Path("dir/file.txt")


def test_relative_to_repo_out_of_repo(pytester: pytest.Pytester) -> None:
    git.Repo.init(pytester.path)
    repo = Repo()
    assert repo.relative_to_repo(Path("/somewhere/over/file.txt")) == Path(
        "/somewhere/over/file.txt"
    )


def test_create_github_url(pytester: pytest.Pytester) -> None:
    r = git.Repo.init(pytester.path)
    r.create_remote("origin", "git@github.com:user/repo.git")
    (pytester.path / "file.txt").touch()
    r.index.add(["file.txt"])
    r.index.commit("Initial commit")

    repo = Repo()
    url = repo.create_github_url(pytester.path / "file.txt", line_num=10)
    assert url is not None
    assert url == "https://github.com/user/repo/blob/master/file.txt#L10"
