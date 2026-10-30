import asyncio
import logging
from typing import Protocol

import cloudinary.uploader

log = logging.getLogger("app.cloudinary")


class UploadFailed(Exception):
    """The image host rejected the upload or could not be reached."""


class UploadUnavailable(Exception):
    """Image uploads are not configured."""


class Uploader(Protocol):
    async def upload(self, data: bytes, *, folder: str) -> str:
        """Store an image and return its Cloudinary public_id."""
        ...


class UnconfiguredUploader:
    async def upload(self, data: bytes, *, folder: str) -> str:
        raise UploadUnavailable("Cloudinary is not configured")


class CloudinaryUploader:
    def __init__(self, cloud_name: str, api_key: str, api_secret: str) -> None:
        self._credentials = {"cloud_name": cloud_name, "api_key": api_key, "api_secret": api_secret}

    async def upload(self, data: bytes, *, folder: str) -> str:
        try:
            # The SDK is synchronous, so it runs in a worker thread to keep the event loop free.
            result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                data,
                folder=folder,
                resource_type="image",
                overwrite=False,
                **self._credentials,
            )
            return str(result["public_id"])
        except Exception as exc:  # the SDK raises many unrelated types
            log.error("cloudinary upload failed", exc_info=exc)
            raise UploadFailed from exc


def delivery_url(cloud_name: str, public_id: str) -> str:
    """CDN URL with automatic format and quality, which keeps pages light on slow phones."""
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/f_auto,q_auto/{public_id}"
