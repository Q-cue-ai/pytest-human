"""Human fixture object and helpers."""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pytest

from pytest_human.log import get_logger


class _AttachmentType(Enum):
    """Types of attachments."""

    LOG = "log"
    IMAGE = "image"


@dataclass(frozen=True, kw_only=True)
class _Attachment:
    """An attachment to the test report."""

    type: _AttachmentType
    """Type of the attachment."""

    content: str | bytes
    """Data of the attachment."""

    file_name: str
    """File name of the attachment. Alternatively the header name of the attachment."""

    description: str | None = None
    """Optional description of the attachment."""


class HumanAttachments:
    """Helper to attach files and images to the test report."""

    def __init__(self) -> None:
        self._images: list[_Attachment] = []
        self._logs: list[_Attachment] = []

    def add_log_file(self, file_path: Path | str, description: str | None = None) -> None:
        """Attach a log file to the test report."""
        file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Log file not found: {file_path}")

        log = file_path.read_text()
        self.add_log_text(log, file_path.name, description)

    def add_log_text(self, log_text: str, file_name: str, description: str | None = None) -> None:
        """Attach a log file in string form to the test report."""
        self._logs.append(
            _Attachment(
                type=_AttachmentType.LOG,
                content=log_text,
                file_name=file_name,
                description=description,
            )
        )

    def add_image(
        self,
        image_path: Path | str,
        description: str | None = None,
    ) -> None:
        """Attach an image file to the test report."""
        image_path = Path(image_path)
        if not image_path.is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        image = image_path.read_bytes()
        self.add_image_bytes(image, image_path.name, description)

    def add_image_bytes(
        self,
        image_bytes: bytes,
        file_name: str,
        description: str | None = None,
    ) -> None:
        """Attach an image in bytes form to the test report."""
        raise NotImplementedError("Image attachments are not yet implemented.")

    def images(self) -> Iterator[_Attachment]:
        """Get all attached images."""
        yield from self._images

    def logs(self) -> Iterator[_Attachment]:
        """Get all attached logs."""
        yield from self._logs


class Human:
    """Human fixture object."""

    def __init__(self, test: pytest.Item) -> None:
        self._test = test
        self.log = get_logger(test.name)
        self.artifacts = HumanAttachments()
