"""app/services/instagram/graph_client.py had zero test coverage despite
being the one piece of code that talks to a real, live Instagram
account -- found while verifying the existing (already-built) carousel
-generation-and-publish pipeline end to end. Mocked at httpx.AsyncClient.
get/post directly, matching this project's existing pattern (see
test_duckduckgo_search_metadata.py) rather than adding a new mocking
dependency."""
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.exceptions import PublishError
from app.services.instagram.graph_client import InstagramGraphClient, exchange_for_long_lived_token


def _response(json_body: dict, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("POST", "https://graph.facebook.com/v21.0/x")
    return httpx.Response(status_code, request=request, json=json_body)


@pytest.fixture
def client():
    return InstagramGraphClient(access_token="test-token", ig_user_id="17841400000000000")


@pytest.mark.asyncio
async def test_create_image_container_returns_the_container_id(monkeypatch, client):
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=_response({"id": "container-1"})))
    container_id = await client.create_image_container("https://cdn.test/slide1.png")
    assert container_id == "container-1"


@pytest.mark.asyncio
async def test_graph_api_error_response_raises_publish_error_with_message(monkeypatch, client):
    # Real Graph API errors come back as HTTP 200 with an "error" body, not
    # necessarily a 4xx/5xx status -- both shapes must be caught.
    monkeypatch.setattr(
        httpx.AsyncClient, "post",
        AsyncMock(return_value=_response({"error": {"code": 100, "error_subcode": 2207001, "message": "Invalid parameter"}})),
    )
    with pytest.raises(PublishError, match="Invalid parameter"):
        await client.create_image_container("https://cdn.test/slide1.png")


@pytest.mark.asyncio
async def test_http_error_status_without_error_body_still_raises(monkeypatch, client):
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=_response({}, status_code=500)))
    with pytest.raises(PublishError):
        await client.create_image_container("https://cdn.test/slide1.png")


@pytest.mark.asyncio
async def test_non_json_response_raises_publish_error_not_a_raw_json_decode_error(monkeypatch, client):
    request = httpx.Request("POST", "https://graph.facebook.com/v21.0/x")
    bad_response = httpx.Response(200, request=request, text="<html>not json</html>")
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=bad_response))
    with pytest.raises(PublishError, match="Non-JSON response"):
        await client.create_image_container("https://cdn.test/slide1.png")


@pytest.mark.asyncio
async def test_wait_for_container_ready_returns_on_finished(monkeypatch, client):
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=_response({"status_code": "FINISHED"})))
    await client.wait_for_container_ready("container-1")  # must not raise


@pytest.mark.asyncio
async def test_wait_for_container_ready_raises_on_error_status(monkeypatch, client):
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=_response({"status_code": "ERROR"})))
    with pytest.raises(PublishError, match="failed processing"):
        await client.wait_for_container_ready("container-1")


@pytest.mark.asyncio
async def test_wait_for_container_ready_times_out_if_never_finished(monkeypatch, client):
    import app.services.instagram.graph_client as gc_module

    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=_response({"status_code": "IN_PROGRESS"})))
    monkeypatch.setattr(gc_module, "_CONTAINER_POLL_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(gc_module.asyncio, "sleep", AsyncMock())  # don't actually wait in the test
    with pytest.raises(PublishError, match="did not finish processing"):
        await client.wait_for_container_ready("container-1")


@pytest.mark.asyncio
async def test_publish_full_carousel_rejects_fewer_than_two_images(client):
    with pytest.raises(PublishError, match="between 2 and 10"):
        await client.publish_full_carousel(["https://cdn.test/only-one.png"], caption="x")


@pytest.mark.asyncio
async def test_publish_full_carousel_rejects_more_than_ten_images(client):
    urls = [f"https://cdn.test/slide{i}.png" for i in range(11)]
    with pytest.raises(PublishError, match="between 2 and 10"):
        await client.publish_full_carousel(urls, caption="x")


@pytest.mark.asyncio
async def test_publish_full_carousel_runs_the_full_real_sequence(monkeypatch, client):
    """The exact 6-step sequence documented in the module docstring:
    create each child container, wait for each, create the carousel
    container, wait for it, publish, fetch the permalink."""
    post_responses = iter([
        _response({"id": "child-1"}),
        _response({"id": "child-2"}),
        _response({"id": "carousel-1"}),
        _response({"id": "ig-media-1"}),
    ])
    get_responses = iter([
        _response({"status_code": "FINISHED"}),  # child-1 ready
        _response({"status_code": "FINISHED"}),  # child-2 ready
        _response({"status_code": "FINISHED"}),  # carousel ready
        _response({"permalink": "https://www.instagram.com/p/xyz/"}),
    ])
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(side_effect=lambda *a, **k: next(post_responses)))
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(side_effect=lambda *a, **k: next(get_responses)))

    child_ids, carousel_id, ig_media_id, permalink = await client.publish_full_carousel(
        ["https://cdn.test/slide1.png", "https://cdn.test/slide2.png"], caption="Fact check caption",
    )

    assert child_ids == ["child-1", "child-2"]
    assert carousel_id == "carousel-1"
    assert ig_media_id == "ig-media-1"
    assert permalink == "https://www.instagram.com/p/xyz/"


@pytest.mark.asyncio
async def test_get_permalink_returns_none_when_absent(monkeypatch, client):
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=_response({})))
    assert await client.get_permalink("ig-media-1") is None


@pytest.mark.asyncio
async def test_exchange_for_long_lived_token_returns_the_raw_payload(monkeypatch):
    monkeypatch.setattr(
        httpx.AsyncClient, "get",
        AsyncMock(return_value=_response({"access_token": "long-lived-token", "expires_in": 5184000})),
    )
    result = await exchange_for_long_lived_token("short-lived-token")
    assert result["access_token"] == "long-lived-token"
    assert result["expires_in"] == 5184000
