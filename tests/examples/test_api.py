from collections.abc import Iterator

import pytest
import requests

from pytest_human.human import Human
from pytest_human.log import get_logger
from pytest_human.tracing import trace_calls, traced

log = get_logger(__name__)


@pytest.fixture
def api_url() -> str:
    """Mock API URL"""
    return "https://jsonplaceholder.typicode.com"


@pytest.fixture
def timeout_sec() -> int:
    """Timeout for API requests in seconds."""
    return 5


@pytest.fixture(autouse=True)
def trace_api_calls() -> Iterator[None]:
    """Automatically trace API call functions in this module."""
    with trace_calls(
        "requests.get",
        requests.request,
        requests.Response.json,
        requests.Response.raise_for_status,
    ):
        yield


@traced
def fetch_users(api_url: str, timeout_sec: int) -> dict:
    """Fetch users from the mock API."""

    response = requests.get(f"{api_url}/users", timeout=timeout_sec)
    response.raise_for_status()
    return response.json()


@traced
def fetch_first_user(api_url: str, timeout_sec: int) -> dict:
    """Fetch the first user from the mock API."""

    users = fetch_users(api_url, timeout_sec)
    return users[0]


@traced
def fetch_user_posts(api_url: str, user_id: int, timeout_sec: int) -> dict:
    """Fetch posts for a specific user from the mock API."""

    response = requests.get(f"{api_url}/posts", params={"userId": user_id}, timeout=timeout_sec)
    response.raise_for_status()
    return response.json()


@traced(suppress_params=True)
def assert_all_posts_from_user(posts: dict, user_id: int) -> None:
    """Assert that all posts belong to the specified user."""

    for post in posts:
        log.debug(f"Post ID: {post['id']}, Title: {post['title']}")
        assert post["userId"] == user_id


def test_api(human: Human, api_url: str, timeout_sec: int) -> None:
    """
    A pytest-human demo test that verifies a mock API
    """

    user = fetch_first_user(api_url, timeout_sec)
    posts = fetch_user_posts(api_url, user["id"], timeout_sec)

    with human.span.info("Verify user data"):
        assert user["id"] == 1
        assert user["username"] == "Bret"
        assert user["email"] == "Sincere@april.biz"
        human.log.info("User data verified successfully.")

    with human.span.info("Verify user posts"):
        assert len(posts) == 10
        assert_all_posts_from_user(posts, user["id"])
