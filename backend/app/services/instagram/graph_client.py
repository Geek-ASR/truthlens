"""Official Meta Graph API client for Instagram carousel publishing
(docs/API_REQUIREMENTS.md §1). No unofficial automation of any kind —
every call here is a documented Graph API endpoint.

Sequence (product spec §21):
  1. create_image_container()  x4  -> per-slide creation IDs
  2. wait_for_container_ready() x4 -> poll until each FINISHED
  3. create_carousel_container()   -> carousel creation ID
  4. wait_for_container_ready()    -> poll carousel FINISHED
  5. publish_carousel()            -> ig_media_id
  6. get_permalink()               -> public URL to store

Images must be reachable at a public URL (Instagram's servers fetch them
server-side) — this is why StorageClient.public_url() exists.
"""
import asyncio

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import PublishError

_CONTAINER_POLL_INTERVAL_SECONDS = 3
_CONTAINER_POLL_MAX_ATTEMPTS = 40  # ~2 minutes


class InstagramGraphClient:
    def __init__(self, access_token: str, ig_user_id: str):
        settings = get_settings()
        self._token = access_token
        self._ig_user_id = ig_user_id
        self._base_url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}"

    async def _post(self, path: str, **params) -> dict:
        params["access_token"] = self._token
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self._base_url}/{path}", data=params)
        return self._unwrap(response)

    async def _get(self, path: str, **params) -> dict:
        params["access_token"] = self._token
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self._base_url}/{path}", params=params)
        return self._unwrap(response)

    @staticmethod
    def _unwrap(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except ValueError as exc:
            raise PublishError(f"Non-JSON response from Graph API: {response.text[:500]}") from exc
        if response.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise PublishError(
                f"Graph API error {err.get('code')}/{err.get('error_subcode')}: "
                f"{err.get('message', response.text[:300])}"
            )
        return data

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def create_image_container(self, image_url: str) -> str:
        data = await self._post(
            f"{self._ig_user_id}/media", image_url=image_url, is_carousel_item="true"
        )
        return data["id"]

    async def wait_for_container_ready(self, container_id: str) -> None:
        for _ in range(_CONTAINER_POLL_MAX_ATTEMPTS):
            data = await self._get(container_id, fields="status_code")
            status = data.get("status_code")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise PublishError(f"Media container {container_id} failed processing")
            await asyncio.sleep(_CONTAINER_POLL_INTERVAL_SECONDS)
        raise PublishError(f"Media container {container_id} did not finish processing in time")

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def create_carousel_container(self, child_ids: list[str], caption: str) -> str:
        data = await self._post(
            f"{self._ig_user_id}/media",
            media_type="CAROUSEL",
            children=",".join(child_ids),
            caption=caption,
        )
        return data["id"]

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def publish_carousel(self, carousel_container_id: str) -> str:
        data = await self._post(f"{self._ig_user_id}/media_publish", creation_id=carousel_container_id)
        return data["id"]

    async def get_permalink(self, ig_media_id: str) -> str | None:
        data = await self._get(ig_media_id, fields="permalink")
        return data.get("permalink")

    async def publish_full_carousel(self, image_urls: list[str], caption: str) -> tuple[list[str], str, str, str | None]:
        """Runs the full sequence. Returns (child_container_ids,
        carousel_container_id, ig_media_id, permalink)."""
        if not (2 <= len(image_urls) <= 10):
            raise PublishError("Instagram carousels require between 2 and 10 items.")

        child_ids = [await self.create_image_container(url) for url in image_urls]
        for cid in child_ids:
            await self.wait_for_container_ready(cid)

        carousel_id = await self.create_carousel_container(child_ids, caption)
        await self.wait_for_container_ready(carousel_id)

        ig_media_id = await self.publish_carousel(carousel_id)
        permalink = await self.get_permalink(ig_media_id)
        return child_ids, carousel_id, ig_media_id, permalink


@retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
async def exchange_for_long_lived_token(short_lived_token: str) -> dict:
    """One-time OAuth step: exchange a short-lived user token for a
    long-lived (~60 day) token. Run interactively by the operator during
    initial account connection, not part of the automated pipeline."""
    settings = get_settings()
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": settings.META_APP_ID,
        "client_secret": settings.META_APP_SECRET,
        "fb_exchange_token": short_lived_token,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/oauth/access_token",
            params=params,
        )
    return InstagramGraphClient._unwrap(response)
