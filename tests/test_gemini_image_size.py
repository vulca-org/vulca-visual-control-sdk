"""Tests for Gemini provider imageSize + aspectRatio mapping."""
import asyncio
import base64
import io
import sys
import types as py_types

import pytest
from PIL import Image

from vulca.providers.gemini import (
    _pixels_to_image_size,
    _dims_to_aspect_ratio,
    GeminiImageProvider,
)


class TestPixelsToImageSize:
    def test_256_maps_to_512(self):
        assert _pixels_to_image_size(256) == "512"

    def test_512_maps_to_512(self):
        assert _pixels_to_image_size(512) == "512"

    def test_768_maps_to_1K(self):
        assert _pixels_to_image_size(768) == "1K"

    def test_1024_maps_to_1K(self):
        assert _pixels_to_image_size(1024) == "1K"

    def test_1536_maps_to_2K(self):
        assert _pixels_to_image_size(1536) == "2K"

    def test_2048_maps_to_2K(self):
        assert _pixels_to_image_size(2048) == "2K"

    def test_3000_maps_to_4K(self):
        assert _pixels_to_image_size(3000) == "4K"

    def test_4096_maps_to_4K(self):
        assert _pixels_to_image_size(4096) == "4K"

    def test_8000_maps_to_4K(self):
        assert _pixels_to_image_size(8000) == "4K"


class TestDimsToAspectRatio:
    def test_square(self):
        assert _dims_to_aspect_ratio(1024, 1024) == "1:1"

    def test_square_any_size(self):
        assert _dims_to_aspect_ratio(256, 256) == "1:1"

    def test_landscape_16_9(self):
        result = _dims_to_aspect_ratio(1920, 1080)
        assert result == "16:9"

    def test_portrait_9_16(self):
        result = _dims_to_aspect_ratio(1080, 1920)
        assert result == "9:16"

    def test_4_3(self):
        result = _dims_to_aspect_ratio(1024, 768)
        assert result == "4:3"

    def test_3_4(self):
        result = _dims_to_aspect_ratio(768, 1024)
        assert result == "3:4"

    def test_3_2(self):
        result = _dims_to_aspect_ratio(1500, 1000)
        assert result == "3:2"

    def test_2_3(self):
        result = _dims_to_aspect_ratio(1000, 1500)
        assert result == "2:3"

    def test_ultrawide_21_9(self):
        result = _dims_to_aspect_ratio(2560, 1080)
        assert result == "21:9"


class TestGeminiProviderConfig:
    def test_default_model(self):
        p = GeminiImageProvider(api_key="fake")
        assert p.model == "gemini-3.1-flash-image-preview"

    def test_custom_model(self):
        p = GeminiImageProvider(api_key="fake", model="gemini-2.5-flash-image")
        assert p.model == "gemini-2.5-flash-image"

    def test_build_prompt_no_hardcoded_resolution(self):
        """Prompt should NOT contain hardcoded 1024x1024."""
        p = GeminiImageProvider(api_key="fake")
        prompt = p._build_prompt("test artwork", "chinese_xieyi", "", "1:1", {})
        assert "1024x1024" not in prompt
        assert "resolution:" not in prompt.lower()

    def test_build_prompt_has_tradition(self):
        p = GeminiImageProvider(api_key="fake")
        prompt = p._build_prompt("test", "chinese_xieyi", "", "1:1", {})
        assert "chinese xieyi" in prompt.lower()

    def test_build_prompt_no_tradition_for_default(self):
        p = GeminiImageProvider(api_key="fake")
        prompt = p._build_prompt("test", "default", "", "1:1", {})
        assert "tradition" not in prompt.lower()

    def test_declares_masked_edit_adapter_capabilities(self):
        p = GeminiImageProvider(api_key="fake")

        caps = p.edit_capabilities()

        assert caps.supports_edits is True
        assert caps.supports_masked_edits is True
        assert caps.requires_mask_for_edits is True
        assert caps.supports_unmasked_edits is False

    def test_generate_missing_candidate_parts_reports_no_image_data(self, monkeypatch):
        class FakeImageConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeGenerateContentConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeModels:
            def generate_content(self, *, model, contents, config):
                return py_types.SimpleNamespace(
                    candidates=[
                        py_types.SimpleNamespace(
                            content=py_types.SimpleNamespace(parts=None)
                        )
                    ],
                    prompt_feedback=None,
                )

        class FakeClient:
            def __init__(self, api_key):
                self.models = FakeModels()

        fake_types = py_types.SimpleNamespace(
            ImageConfig=FakeImageConfig,
            GenerateContentConfig=FakeGenerateContentConfig,
        )
        fake_genai = py_types.SimpleNamespace(Client=FakeClient, types=fake_types)
        fake_google = py_types.SimpleNamespace(genai=fake_genai)
        monkeypatch.setitem(sys.modules, "google", fake_google)
        monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
        monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

        with pytest.raises(RuntimeError, match="Gemini returned no image data"):
            asyncio.run(GeminiImageProvider(api_key="gemini-key").generate("test"))

    def test_inpaint_with_mask_sends_source_and_mask_parts(
        self,
        tmp_path,
        monkeypatch,
    ):
        recorded = {}

        class FakeInlineData:
            mime_type = "image/png"

            def __init__(self, data):
                self.data = data

        class FakePart:
            def __init__(self, data=None, mime_type="", inline_data=None):
                self.data = data
                self.mime_type = mime_type
                self.inline_data = inline_data

            @classmethod
            def from_bytes(cls, *, data, mime_type):
                return cls(data=data, mime_type=mime_type)

        class FakeImageConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeGenerateContentConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeModels:
            def generate_content(self, *, model, contents, config):
                recorded["model"] = model
                recorded["contents"] = contents
                recorded["config"] = config
                out = Image.new("RGB", (8, 8), (232, 190, 42))
                buf = io.BytesIO()
                out.save(buf, format="PNG")
                inline = FakeInlineData(buf.getvalue())
                return py_types.SimpleNamespace(
                    candidates=[
                        py_types.SimpleNamespace(
                            content=py_types.SimpleNamespace(
                                parts=[FakePart(inline_data=inline)]
                            )
                        )
                    ],
                    prompt_feedback=None,
                )

        class FakeClient:
            def __init__(self, api_key):
                recorded["api_key"] = api_key
                self.models = FakeModels()

        fake_types = py_types.SimpleNamespace(
            Part=FakePart,
            ImageConfig=FakeImageConfig,
            GenerateContentConfig=FakeGenerateContentConfig,
        )
        fake_genai = py_types.SimpleNamespace(Client=FakeClient, types=fake_types)
        fake_google = py_types.SimpleNamespace(genai=fake_genai)
        monkeypatch.setitem(sys.modules, "google", fake_google)
        monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
        monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

        image_path = tmp_path / "source.png"
        mask_path = tmp_path / "mask.png"
        Image.new("RGB", (16, 12), (35, 92, 43)).save(image_path)
        mask = Image.new("RGBA", (16, 12), (0, 0, 0, 255))
        mask.putpixel((8, 6), (0, 0, 0, 0))
        mask.save(mask_path)

        result = asyncio.run(
            GeminiImageProvider(api_key="gemini-key").inpaint_with_mask(
                image_path=str(image_path),
                mask_path=str(mask_path),
                prompt="paint one compact yellow flower head",
                tradition="default",
            )
        )

        assert recorded["api_key"] == "gemini-key"
        assert recorded["model"] == "gemini-3.1-flash-image-preview"
        assert recorded["contents"][0].mime_type == "image/png"
        assert recorded["contents"][1].mime_type == "image/png"
        visible_mask = Image.open(io.BytesIO(recorded["contents"][1].data)).convert(
            "RGB"
        )
        assert visible_mask.getpixel((8, 6)) == (255, 255, 255)
        assert visible_mask.getpixel((0, 0)) == (0, 0, 0)
        assert "transparent mask pixels" in recorded["contents"][2]
        assert "opaque mask pixels" in recorded["contents"][2]
        assert "white mask pixels" in recorded["contents"][2]
        assert "black mask pixels" in recorded["contents"][2]
        assert "do not draw the mask" in recorded["contents"][2].lower()
        assert "not part of the output" in recorded["contents"][2].lower()
        assert "paint one compact yellow flower head" in recorded["contents"][2]
        assert result.mime == "image/png"
        assert base64.b64decode(result.image_b64).startswith(b"\x89PNG")
        assert result.metadata["mode"] == "gemini_mask_adapter"
