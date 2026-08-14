"""Tests for OpenAI provider — gpt-image-1 transparency support."""
import asyncio
import base64
import json
from contextlib import contextmanager

import httpx
import pytest
import inspect

from vulca.providers.openai_provider import OpenAIImageProvider


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
        b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@contextmanager
def _httpx_with_handler(handler):
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(httpx, "AsyncClient", factory)
        yield


class TestOpenAIProviderConfig:
    def test_default_model_is_gpt_image_1(self):
        provider = OpenAIImageProvider(api_key="test")
        assert provider.model == "gpt-image-1"

    def test_supports_background_parameter(self):
        provider = OpenAIImageProvider(api_key="test")
        sig = inspect.signature(provider.generate)
        params = list(sig.parameters.keys())
        assert "background" in params, "generate() must accept background parameter"

    def test_legacy_dalle3_still_works(self):
        provider = OpenAIImageProvider(api_key="test", model="dall-e-3")
        assert provider.model == "dall-e-3"


def test_gpt_image_2_drops_input_fidelity_from_edit_form():
    captured_bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_bodies.append(request.content)
        return httpx.Response(200, json={"data": [{"b64_json": "AAAA"}]})

    ref_b64 = base64.b64encode(_png_bytes()).decode()
    with _httpx_with_handler(handler):
        result = asyncio.run(
            OpenAIImageProvider(api_key="test-token", model="gpt-image-2").generate(
                "edit this",
                reference_image_b64=ref_b64,
                input_fidelity="high",
                quality="high",
                output_format="webp",
            )
        )

    body = captured_bodies[0]
    assert b'name="input_fidelity"' not in body
    assert b'name="quality"' in body
    assert b'name="output_format"' in body
    assert result.mime == "image/webp"
    assert result.metadata["output_format"] == "webp"


def test_gpt_image_15_keeps_input_fidelity_in_edit_form():
    captured_bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_bodies.append(request.content)
        return httpx.Response(200, json={"data": [{"b64_json": "AAAA"}]})

    ref_b64 = base64.b64encode(_png_bytes()).decode()
    with _httpx_with_handler(handler):
        asyncio.run(
            OpenAIImageProvider(api_key="test-token", model="gpt-image-1.5").generate(
                "edit this",
                reference_image_b64=ref_b64,
                input_fidelity="high",
                quality="high",
                output_format="webp",
            )
        )

    body = captured_bodies[0]
    assert b'name="input_fidelity"' in body


def test_usage_cost_populates_cost_usd_metadata():
    captured_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payloads.append(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json={
                "data": [{"b64_json": "AAAA"}],
                "usage": {"input_tokens": 2_000, "output_tokens": 4_000},
            },
        )

    with _httpx_with_handler(handler):
        result = asyncio.run(
            OpenAIImageProvider(api_key="test-token", model="gpt-image-1").generate(
                "a sunset",
                quality="high",
            )
        )

    assert captured_payloads[0]["quality"] == "high"
    assert result.metadata["cost_usd"] == pytest.approx(0.18)


def test_openai_compatible_base_url_routes_image_generation(monkeypatch):
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(200, json={"data": [{"b64_json": "AAAA"}]})

    monkeypatch.setenv("OPENAI_BASE_URL", "https://globalai.example/v1")
    with _httpx_with_handler(handler):
        asyncio.run(
            OpenAIImageProvider(api_key="sk-test", model="gpt-image-2").generate(
                "a flower",
                quality="low",
            )
        )

    assert captured_urls == ["https://globalai.example/v1/images/generations"]


def test_openai_compatible_base_url_routes_masked_edits(monkeypatch, tmp_path):
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(200, json={"data": [{"b64_json": "AAAA"}]})

    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    image_path.write_bytes(_png_bytes())
    mask_path.write_bytes(_png_bytes())

    monkeypatch.setenv("OPENAI_BASE_URL", "https://globalai.example/v1/")
    with _httpx_with_handler(handler):
        asyncio.run(
            OpenAIImageProvider(api_key="sk-test", model="gpt-image-2").inpaint_with_mask(
                image_path=str(image_path),
                mask_path=str(mask_path),
                prompt="paint flowers",
                quality="low",
            )
        )

    assert captured_urls == ["https://globalai.example/v1/images/edits"]


def test_chat_completions_image_endpoint_routes_masked_edit(monkeypatch, tmp_path):
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "url": str(request.url),
                "payload": json.loads(request.content.decode()),
            }
        )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "![result](data:image/png;base64,AAAA)"
                        }
                    }
                ]
            },
        )

    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    image_path.write_bytes(_png_bytes())
    mask_path.write_bytes(_png_bytes())

    monkeypatch.setenv("OPENAI_BASE_URL", "https://globalai.example/v1")
    monkeypatch.setenv("VULCA_OPENAI_IMAGE_ENDPOINT", "chat_completions")
    with _httpx_with_handler(handler):
        result = asyncio.run(
            OpenAIImageProvider(api_key="sk-test", model="gpt-image-2").inpaint_with_mask(
                image_path=str(image_path),
                mask_path=str(mask_path),
                prompt="paint flowers",
                quality="low",
            )
        )

    assert captured[0]["url"] == "https://globalai.example/v1/chat/completions"
    payload = captured[0]["payload"]
    assert payload["model"] == "gpt-image-2"
    content = payload["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[2]["type"] == "image_url"
    assert content[2]["image_url"]["url"].startswith("data:image/png;base64,")
    assert result.image_b64 == "AAAA"
    assert result.metadata["endpoint"] == "chat/completions"


def test_chat_completions_image_endpoint_fetches_returned_url(monkeypatch, tmp_path):
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        if str(request.url).endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "generated: https://cdn.example/out.png"
                            }
                        }
                    ]
                },
            )
        return httpx.Response(200, content=_png_bytes(), headers={"content-type": "image/png"})

    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    image_path.write_bytes(_png_bytes())
    mask_path.write_bytes(_png_bytes())

    monkeypatch.setenv("OPENAI_BASE_URL", "https://globalai.example/v1")
    monkeypatch.setenv("VULCA_OPENAI_IMAGE_ENDPOINT", "chat_completions")
    with _httpx_with_handler(handler):
        result = asyncio.run(
            OpenAIImageProvider(api_key="sk-test", model="gpt-image-2").inpaint_with_mask(
                image_path=str(image_path),
                mask_path=str(mask_path),
                prompt="paint flowers",
            )
        )

    assert captured_urls == [
        "https://globalai.example/v1/chat/completions",
        "https://cdn.example/out.png",
    ]
    assert result.image_b64 == base64.b64encode(_png_bytes()).decode()


def test_custom_base_url_is_used_for_image_generations():
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, json={"data": [{"b64_json": "AAAA"}]})

    with _httpx_with_handler(handler):
        asyncio.run(
            OpenAIImageProvider(
                api_key="test-token",
                model="gpt-image-2",
                base_url="https://gateway.example/v1/",
            ).generate("a sunset")
        )

    assert requested_urls == ["https://gateway.example/v1/images/generations"]


def test_openai_base_url_can_come_from_environment(monkeypatch):
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, json={"data": [{"b64_json": "AAAA"}]})

    monkeypatch.setenv("VULCA_OPENAI_BASE_URL", "https://env-gateway.example")

    with _httpx_with_handler(handler):
        asyncio.run(
            OpenAIImageProvider(api_key="test-token", model="gpt-image-2").generate(
                "a sunset"
            )
        )

    assert requested_urls == ["https://env-gateway.example/v1/images/generations"]


def test_gpt_image_2_snapshot_model_configured_and_priced():
    from vulca.providers.openai_provider import (
        MODEL_CAPABILITIES,
        MODEL_TOKEN_PRICING_PER_MILLION,
        _openai_edit_capabilities,
    )

    snapshot = "gpt-image-2-2026-04-21"
    assert snapshot in MODEL_CAPABILITIES
    assert MODEL_CAPABILITIES[snapshot] == {
        "input_fidelity": False,
        "quality": True,
        "output_format": True,
    }
    assert snapshot in MODEL_TOKEN_PRICING_PER_MILLION
    assert MODEL_TOKEN_PRICING_PER_MILLION[snapshot] == {"input": 8.0, "output": 30.0}

    edit_caps = _openai_edit_capabilities(snapshot)
    assert edit_caps.supports_edits is True
    assert edit_caps.requires_mask_for_edits is True
    assert edit_caps.supports_input_fidelity is False
    assert edit_caps.supports_quality is True
    assert edit_caps.supports_output_format is True


def test_gpt_image_2_snapshot_generation_wire_payload_and_cost():
    captured_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payloads.append(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json={
                "data": [{"b64_json": "AAAA"}],
                "usage": {"input_tokens": 1_000, "output_tokens": 1_768},
            },
        )

    with _httpx_with_handler(handler):
        result = asyncio.run(
            OpenAIImageProvider(
                api_key="sk-test",
                model="gpt-image-2-2026-04-21",
                timeout=120.0,
                max_retries=0,
            ).generate(
                "a serene ink landscape",
                quality="medium",
                output_format="png",
            )
        )

    assert captured_payloads[0]["model"] == "gpt-image-2-2026-04-21"
    assert captured_payloads[0]["quality"] == "medium"
    assert captured_payloads[0]["output_format"] == "png"
    assert result.metadata["model"] == "gpt-image-2-2026-04-21"
    # 1000 * 8/1M + 1768 * 30/1M = 0.008 + 0.05304 = 0.06104
    assert result.metadata["cost_usd"] == pytest.approx(0.06104)


def test_openai_provider_timeout_and_max_retries_defaults_and_custom():
    default_provider = OpenAIImageProvider(api_key="sk-test")
    assert default_provider.timeout == 120.0
    assert default_provider.max_retries == 3

    custom_provider = OpenAIImageProvider(
        api_key="sk-test",
        model="gpt-image-2-2026-04-21",
        timeout=45.0,
        max_retries=0,
    )
    assert custom_provider.timeout == 45.0
    assert custom_provider.max_retries == 0


def test_openai_provider_zero_retries_fails_immediately_on_429():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, json={"error": {"message": "Rate limit reached"}})

    provider = OpenAIImageProvider(api_key="sk-test", max_retries=0)
    with _httpx_with_handler(handler):
        with pytest.raises(RuntimeError, match="rate limit"):
            asyncio.run(provider.generate("test"))
    assert attempts == 1
