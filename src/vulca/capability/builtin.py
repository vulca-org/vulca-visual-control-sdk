"""Provider-backed visual capability Cells for the first JobClass.

These adapters are intentionally narrow.  They resolve one trusted binding,
make one provider operation, and return a capability envelope.  They do not
own Job state, release authority, retry policy, or evaluator decisions.
"""

from __future__ import annotations

import base64
import binascii
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from vulca.evaluate import aevaluate
from vulca.inpaint import ainpaint
from vulca.providers.base import ImageProvider
from vulca.types import EvalResult

from .registry import CapabilityRegistry
from .runtime import CapabilityRuntime, EnvironmentCapabilityRuntime
from .types import (
    Capability,
    CapabilityArtifact,
    CapabilityInvocation,
    CapabilityMaturity,
    CapabilityManifest,
    CapabilityResult,
    CapabilityStatus,
    JsonValue,
    SideEffectState,
    sha256_bytes,
)


_VERSION = "1.0.0"
_USD = "USD"
_IMAGE_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
_OUTPUT_FORMAT_MIMES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}
_COORDINATE_RE = re.compile(r"^\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*$")
_PROVIDER_CONSTRUCTION_ERRORS = (ValueError, TypeError, OSError, NotImplementedError)


class _PreflightFailure(Exception):
    """A declared input/binding failure that happened before side effects."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _PostflightFailure(Exception):
    """A declared adapter failure after a provider operation was attempted."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _InputBytes:
    data: bytes
    source_path: Path | None


def _manifest(
    capability_id: str,
    *,
    kind: str,
    deterministic: bool,
    authority_requirements: tuple[str, ...] = (),
    evaluator_bindings: tuple[str, ...] = (),
    retryable_codes: tuple[str, ...] = (),
) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id=capability_id,
        version=_VERSION,
        kind=kind,
        owner="vulca",
        maturity=CapabilityMaturity.NATIVE,
        input_schema={},
        output_schema={},
        authority_requirements=authority_requirements,
        evaluator_bindings=evaluator_bindings,
        retryable_codes=retryable_codes,
        deterministic=deterministic,
    )


def _elapsed_ms(start: float) -> int:
    return max(0, int((time.perf_counter() - start) * 1000))


def _failed(
    invocation: CapabilityInvocation,
    *,
    code: str,
    state: SideEffectState,
    start: float,
) -> CapabilityResult:
    return CapabilityResult(
        invocation_id=invocation.invocation_id,
        status=CapabilityStatus.FAILED,
        side_effect_state=state,
        output={},
        artifacts=(),
        provider_receipt={},
        latency_ms=_elapsed_ms(start),
        cost_minor=0,
        currency=_USD,
        error_code=code,
    )


def _mapping(value: object, *, code: str = "INVALID_OPTIONS") -> dict[str, JsonValue]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _PreflightFailure(code)
    return cast(dict[str, JsonValue], dict(value))


def _text(
    values: Mapping[str, JsonValue],
    key: str,
    *,
    default: str | None = "",
    required: bool = False,
) -> str:
    value = values.get(key, default)
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise _PreflightFailure("INVALID_INPUT")
    if required and not value.strip():
        raise _PreflightFailure("INVALID_INPUT")
    return value


def _optional_int(values: Mapping[str, JsonValue], key: str, default: int | None = None) -> int | None:
    value = values.get(key, default)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise _PreflightFailure("INVALID_INPUT")
    return value


def _optional_float(values: Mapping[str, JsonValue], key: str, default: float | None = None) -> float | None:
    value = values.get(key, default)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _PreflightFailure("INVALID_INPUT")
    return float(value)


def _required_binding(options: Mapping[str, JsonValue]) -> tuple[str, str, dict[str, JsonValue]]:
    provider = options.get("provider", options.get("provider_name"))
    binding_ref = options.get("binding_ref")
    if not isinstance(provider, str) or not provider.strip():
        raise _PreflightFailure("INVALID_PROVIDER_BINDING")
    if not isinstance(binding_ref, str) or not binding_ref.strip():
        raise _PreflightFailure("INVALID_PROVIDER_BINDING")
    constructor_options = _mapping(options.get("constructor_options", {}))
    return provider, binding_ref, constructor_options


def _request_options(options: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    value = options.get("request_options", options.get("generate_options", {}))
    return _mapping(value)


def _decode_base64(value: str) -> bytes:
    payload = value.strip()
    if payload.startswith("data:"):
        marker = ",base64,"
        marker_index = payload.lower().find(marker)
        if marker_index < 0:
            raise _PreflightFailure("INVALID_BASE64")
        payload = payload[marker_index + len(marker) :]
    if not payload:
        raise _PreflightFailure("INVALID_BASE64")
    try:
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise _PreflightFailure("INVALID_BASE64") from None
    if not data:
        raise _PreflightFailure("EMPTY_ARTIFACT")
    return data


def _path_policy(options: Mapping[str, JsonValue]) -> tuple[list[Path], list[Path]]:
    paths_value = options.get("authorized_paths", [])
    roots_value = options.get("authorized_roots", [])
    if not isinstance(paths_value, list) or not isinstance(roots_value, list):
        raise _PreflightFailure("INVALID_AUTHORIZATION")
    try:
        paths = [Path(value).expanduser().resolve(strict=False) for value in paths_value if isinstance(value, str)]
        roots = [Path(value).expanduser().resolve(strict=False) for value in roots_value if isinstance(value, str)]
    except (OSError, RuntimeError, ValueError):
        raise _PreflightFailure("INVALID_AUTHORIZATION") from None
    if len(paths) != len(paths_value) or len(roots) != len(roots_value):
        raise _PreflightFailure("INVALID_AUTHORIZATION")
    return paths, roots


def _authorise_path(path: Path, options: Mapping[str, JsonValue], *, required: bool = False) -> Path:
    paths, roots = _path_policy(options)
    try:
        resolved = path.expanduser().resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        raise _PreflightFailure("MISSING_INPUT") from None
    if not paths and not roots:
        if required:
            raise _PreflightFailure("UNAUTHORIZED_PATH")
        return resolved
    if resolved in paths or any(resolved.is_relative_to(root) for root in roots):
        return resolved
    raise _PreflightFailure("UNAUTHORIZED_PATH")


def _read_input(value: object, options: Mapping[str, JsonValue], *, required_path_auth: bool = False) -> _InputBytes:
    if not isinstance(value, str) or not value.strip():
        raise _PreflightFailure("INVALID_INPUT")
    candidate = Path(value).expanduser()
    try:
        is_file = candidate.is_file()
    except (OSError, RuntimeError, ValueError):
        is_file = False
    if is_file:
        resolved = _authorise_path(candidate, options, required=required_path_auth)
        try:
            data = resolved.read_bytes()
        except OSError:
            raise _PreflightFailure("MISSING_INPUT") from None
        if not data:
            raise _PreflightFailure("EMPTY_ARTIFACT")
        return _InputBytes(data=data, source_path=resolved)
    return _InputBytes(data=_decode_base64(value), source_path=None)


def _mime_from_bytes(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _image_size(data: bytes, *, code: str = "CORRUPT_ARTIFACT") -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(BytesIO(data)) as image:
            image.load()
            return image.size
    except (OSError, ValueError, SyntaxError):
        raise _PreflightFailure(code) from None


def _cost_minor(value: object) -> tuple[int, bool]:
    if value is None:
        return 0, False
    try:
        decimal_value = Decimal(str(value))
        if not decimal_value.is_finite() or decimal_value < 0:
            raise InvalidOperation
        cents = (decimal_value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise _PostflightFailure("INVALID_COST") from None
    return int(cents), True


def _metadata_string(metadata: Mapping[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _provider_receipt(
    *,
    provider: str,
    model: str | None,
    request_id: str | None,
    cost_known: bool,
    latency_ms: int,
) -> dict[str, JsonValue]:
    receipt: dict[str, JsonValue] = {
        "provider": provider,
        "costKnown": cost_known,
        "latency_ms": latency_ms,
    }
    if model is not None:
        receipt["model"] = model
    if request_id is not None:
        receipt["request_id"] = request_id
    return receipt


def _artifact_name(inputs: Mapping[str, JsonValue], default: str) -> str:
    value = inputs.get("logical_name", default)
    return value if isinstance(value, str) and value.strip() else default


def _reference_b64(value: object, options: Mapping[str, JsonValue]) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or not value.strip():
        raise _PreflightFailure("INVALID_INPUT")
    candidate = Path(value).expanduser()
    try:
        is_file = candidate.is_file()
    except (OSError, RuntimeError, ValueError):
        is_file = False
    if is_file:
        return base64.b64encode(_read_input(value, options).data).decode("ascii")
    if value.strip().startswith("data:"):
        data = _decode_base64(value)
        return base64.b64encode(data).decode("ascii")
    _decode_base64(value)
    return value.strip()


def _image_argument(value: object, options: Mapping[str, JsonValue]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _PreflightFailure("INVALID_INPUT")
    candidate = Path(value).expanduser()
    try:
        is_file = candidate.is_file()
    except (OSError, RuntimeError, ValueError):
        is_file = False
    if is_file:
        return str(_authorise_path(candidate, options))
    data = _decode_base64(value)
    mime = _mime_from_bytes(data) or "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _cleanup_edit_paths(wrapper_dir: Path, paths: Sequence[object]) -> None:
    """Remove only wrapper-owned files and temporary inpaint scratch paths."""
    temp_root = Path(tempfile.gettempdir()).resolve()
    try:
        shutil.rmtree(wrapper_dir)
    except FileNotFoundError:
        pass
    except OSError:
        pass
    for value in paths:
        if not isinstance(value, str) or not value:
            continue
        path = Path(value)
        try:
            resolved = path.resolve(strict=False)
        except (OSError, RuntimeError, ValueError):
            continue
        if resolved == wrapper_dir or resolved.is_relative_to(wrapper_dir):
            continue
        parent = resolved.parent
        if not parent.name.startswith("vulca-inpaint-"):
            continue
        try:
            if parent.is_relative_to(temp_root):
                shutil.rmtree(parent)
        except (OSError, RuntimeError, ValueError):
            continue


def _selected_output_path(result: object) -> tuple[Path, list[object]]:
    variants = getattr(result, "variants", None)
    if not isinstance(variants, (list, tuple)) or not variants:
        raise _PostflightFailure("EMPTY_ARTIFACT")
    selected = getattr(result, "selected", 0)
    if isinstance(selected, bool) or not isinstance(selected, int) or selected < 0 or selected >= len(variants):
        raise _PostflightFailure("EMPTY_ARTIFACT")
    selected_path = variants[selected]
    if not isinstance(selected_path, str) or not selected_path:
        raise _PostflightFailure("EMPTY_ARTIFACT")
    return Path(selected_path), list(variants)


def _json_safe(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(nested) for key, nested in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(nested) for nested in value]
    return None


class GenerateImageCapability:
    """One direct ``ImageProvider.generate`` operation."""

    manifest = _manifest(
        "vulca.image.generate",
        kind="image-generation",
        deterministic=False,
        authority_requirements=("provider_binding", "secret_binding"),
        retryable_codes=("PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_FAILED"),
    )

    def __init__(self, *, runtime: CapabilityRuntime | None = None) -> None:
        self.runtime = runtime or EnvironmentCapabilityRuntime()

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        start = time.perf_counter()
        inputs = invocation.inputs
        options = invocation.options
        try:
            provider_name, binding_ref, constructor_options = _required_binding(options)
            prompt = _text(inputs, "prompt", default=None)
            if not prompt.strip():
                prompt = _text(inputs, "intent", required=True)
            tradition = _text(inputs, "tradition")
            subject = _text(inputs, "subject")
            reference = _reference_b64(
                inputs.get(
                    "reference_image_b64",
                    inputs.get("reference_image", inputs.get("reference")),
                ),
                options,
            )
            width = _optional_int(inputs, "width", 1024)
            height = _optional_int(inputs, "height", 1024)
            if width is None or height is None or width <= 0 or height <= 0:
                raise _PreflightFailure("INVALID_DIMENSIONS")
            seed = _optional_int(inputs, "seed")
            steps = _optional_int(inputs, "steps")
            cfg_scale = _optional_float(inputs, "cfg_scale")
            negative_prompt = _text(inputs, "negative_prompt")
            input_fidelity = _text(inputs, "input_fidelity") or None
            quality = _text(inputs, "quality") or None
            output_format = _text(inputs, "output_format") or None
            request_options = _request_options(options)
        except _PreflightFailure as failure:
            return _failed(invocation, code=failure.code, state=SideEffectState.NOT_STARTED, start=start)

        try:
            provider: ImageProvider = self.runtime.image_provider(
                provider_name=provider_name,
                binding_ref=binding_ref,
                constructor_options=constructor_options,
            )
        except _PROVIDER_CONSTRUCTION_ERRORS:
            return _failed(
                invocation,
                code="PROVIDER_CONSTRUCTION_FAILED",
                state=SideEffectState.NOT_STARTED,
                start=start,
            )

        try:
            result = await provider.generate(
                prompt,
                tradition=tradition,
                subject=subject,
                reference_image_b64=reference,
                negative_prompt=negative_prompt,
                seed=seed,
                steps=steps,
                cfg_scale=cfg_scale,
                width=width,
                height=height,
                input_fidelity=input_fidelity,
                quality=quality,
                output_format=output_format,
                **request_options,
            )
        except TimeoutError:
            return _failed(invocation, code="PROVIDER_TIMEOUT", state=SideEffectState.UNKNOWN, start=start)
        except OSError:
            return _failed(
                invocation,
                code="PROVIDER_TRANSPORT_FAILED",
                state=SideEffectState.UNKNOWN,
                start=start,
            )
        except NotImplementedError:
            return _failed(invocation, code="PROVIDER_UNSUPPORTED", state=SideEffectState.UNKNOWN, start=start)
        except ValueError:
            return _failed(invocation, code="PROVIDER_FAILED", state=SideEffectState.UNKNOWN, start=start)

        try:
            image_b64 = getattr(result, "image_b64")
            mime = getattr(result, "mime")
            if not isinstance(image_b64, str) or not image_b64.strip():
                raise _PostflightFailure("EMPTY_ARTIFACT")
            if not isinstance(mime, str) or mime.lower() not in _IMAGE_MIME_TYPES:
                raise _PostflightFailure("INVALID_MEDIA_TYPE")
            normalized_mime = mime.lower()
            if output_format and output_format.lower() in _OUTPUT_FORMAT_MIMES:
                if normalized_mime != _OUTPUT_FORMAT_MIMES[output_format.lower()]:
                    raise _PostflightFailure("INVALID_MEDIA_TYPE")
            image_bytes = _decode_base64(image_b64)
            metadata_value = getattr(result, "metadata", None)
            metadata: Mapping[str, object] = metadata_value if isinstance(metadata_value, dict) else {}
            cost_minor, cost_known = _cost_minor(metadata.get("cost_usd"))
            constructor_model = constructor_options.get("model")
            model = _metadata_string(metadata, "model") or (
                constructor_model if isinstance(constructor_model, str) else None
            )
            request_id = _metadata_string(metadata, "request_id")
            latency_ms = _elapsed_ms(start)
            artifact = CapabilityArtifact(
                logical_name=_artifact_name(inputs, "generated-image"),
                media_type=normalized_mime,
                content=image_bytes,
                sha256=sha256_bytes(image_bytes),
            )
            return CapabilityResult(
                invocation_id=invocation.invocation_id,
                status=CapabilityStatus.SUCCEEDED,
                side_effect_state=SideEffectState.COMPLETED,
                output={"media_type": normalized_mime, "byte_count": len(image_bytes)},
                artifacts=(artifact,),
                provider_receipt=_provider_receipt(
                    provider=provider_name,
                    model=model,
                    request_id=request_id,
                    cost_known=cost_known,
                    latency_ms=latency_ms,
                ),
                latency_ms=latency_ms,
                cost_minor=cost_minor,
                currency=_USD,
            )
        except (_PostflightFailure, _PreflightFailure) as failure:
            return _failed(invocation, code=failure.code, state=SideEffectState.UNKNOWN, start=start)


class EditImageCapability:
    """Bounded coordinate/mask edit using exactly one ``ainpaint`` variant."""

    manifest = _manifest(
        "vulca.image.edit",
        kind="image-edit",
        deterministic=False,
        authority_requirements=("source_binding", "provider_binding", "secret_binding"),
        retryable_codes=("PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_FAILED"),
    )

    def __init__(self, *, runtime: CapabilityRuntime | None = None) -> None:
        self.runtime = runtime or EnvironmentCapabilityRuntime()

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        start = time.perf_counter()
        wrapper_dir = Path(tempfile.mkdtemp(prefix="vulca-inpaint-"))
        cleanup_candidates: list[object] = []
        try:
            inputs = invocation.inputs
            options = invocation.options
            reference_type = _text(inputs, "reference_type", default=None, required=True).lower()
            instruction = _text(inputs, "instruction", required=True)
            tradition = _text(inputs, "tradition")
            source = _read_input(inputs.get("source"), options)
            _image_size(source.data)
            source_path = source.source_path
            if source_path is None:
                source_path = wrapper_dir / "source.png"
                source_path.write_bytes(source.data)
            mask_path = ""
            region = ""
            if reference_type == "coordinate":
                region = _text(inputs, "region", default=None, required=True)
                if not _COORDINATE_RE.match(region):
                    raise _PreflightFailure("INVALID_REGION")
                numbers = [int(part.strip()) for part in region.split(",")]
                x, y, width, height = numbers
                if min(numbers) < 0 or max(x + width, y + height) > 100 or width < 5 or height < 5:
                    raise _PreflightFailure("INVALID_REGION")
            elif reference_type == "mask":
                mask = _read_input(inputs.get("mask"), options)
                source_size = _image_size(source.data)
                mask_size = _image_size(mask.data, code="INVALID_MASK")
                if mask_size != source_size:
                    raise _PreflightFailure("MASK_SIZE_MISMATCH")
                if mask.source_path is None:
                    mask_file = wrapper_dir / "mask.png"
                    mask_file.write_bytes(mask.data)
                    mask_path = str(mask_file)
                else:
                    mask_path = str(mask.source_path)
            else:
                raise _PreflightFailure("INVALID_REFERENCE_TYPE")

            provider_name = options.get("provider", "openai" if mask_path else "gemini")
            binding_ref = options.get("binding_ref")
            if not isinstance(provider_name, str) or not provider_name.strip():
                raise _PreflightFailure("INVALID_PROVIDER_BINDING")
            if not isinstance(binding_ref, str) or not binding_ref.strip():
                raise _PreflightFailure("INVALID_PROVIDER_BINDING")
            api_key = self.runtime.api_key(binding_ref=binding_ref)
            if not isinstance(api_key, str):
                raise _PreflightFailure("INVALID_PROVIDER_BINDING")
            mock = options.get("mock", False)
            if not isinstance(mock, bool):
                raise _PreflightFailure("INVALID_OPTIONS")
            output_path = wrapper_dir / "selected.png"
            cleanup_candidates.append(str(output_path))
        except _PreflightFailure as failure:
            _cleanup_edit_paths(wrapper_dir, cleanup_candidates)
            return _failed(invocation, code=failure.code, state=SideEffectState.NOT_STARTED, start=start)
        except _PROVIDER_CONSTRUCTION_ERRORS:
            _cleanup_edit_paths(wrapper_dir, cleanup_candidates)
            return _failed(
                invocation,
                code="PROVIDER_CONSTRUCTION_FAILED",
                state=SideEffectState.NOT_STARTED,
                start=start,
            )
        except Exception:
            _cleanup_edit_paths(wrapper_dir, cleanup_candidates)
            raise

        try:
            result = await ainpaint(
                image=str(source_path),
                region=region,
                instruction=instruction,
                mask_path=mask_path,
                tradition=tradition,
                provider=cast(str, provider_name),
                count=1,
                select=0,
                output="",
                output_path=str(output_path),
                api_key=api_key,
                mock=mock,
            )
        except TimeoutError:
            _cleanup_edit_paths(wrapper_dir, cleanup_candidates)
            return _failed(invocation, code="PROVIDER_TIMEOUT", state=SideEffectState.UNKNOWN, start=start)
        except OSError:
            _cleanup_edit_paths(wrapper_dir, cleanup_candidates)
            return _failed(
                invocation,
                code="PROVIDER_TRANSPORT_FAILED",
                state=SideEffectState.UNKNOWN,
                start=start,
            )
        except NotImplementedError:
            _cleanup_edit_paths(wrapper_dir, cleanup_candidates)
            return _failed(invocation, code="PROVIDER_UNSUPPORTED", state=SideEffectState.UNKNOWN, start=start)
        except ValueError:
            _cleanup_edit_paths(wrapper_dir, cleanup_candidates)
            return _failed(invocation, code="PROVIDER_FAILED", state=SideEffectState.UNKNOWN, start=start)
        except Exception:
            _cleanup_edit_paths(wrapper_dir, cleanup_candidates)
            raise

        try:
            selected_path, variant_paths = _selected_output_path(result)
            cleanup_candidates.extend(variant_paths)
            cleanup_candidates.append(getattr(result, "blended", ""))
            try:
                output_bytes = selected_path.read_bytes()
            except (FileNotFoundError, OSError):
                raise _PostflightFailure("EMPTY_ARTIFACT") from None
            if not output_bytes:
                raise _PostflightFailure("EMPTY_ARTIFACT")
            cost_minor, cost_known = _cost_minor(getattr(result, "cost_usd", None))
            latency_ms = _elapsed_ms(start)
            output_mime = _mime_from_bytes(output_bytes) or "image/png"
            artifact = CapabilityArtifact(
                logical_name=_artifact_name(invocation.inputs, "edited-image"),
                media_type=output_mime,
                content=output_bytes,
                sha256=sha256_bytes(output_bytes),
            )
            return CapabilityResult(
                invocation_id=invocation.invocation_id,
                status=CapabilityStatus.SUCCEEDED,
                side_effect_state=SideEffectState.COMPLETED,
                output={
                    "source_sha256": sha256_bytes(source.data),
                    "output_sha256": sha256_bytes(output_bytes),
                    "media_type": output_mime,
                },
                artifacts=(artifact,),
                provider_receipt=_provider_receipt(
                    provider=cast(str, provider_name),
                    model=None,
                    request_id=None,
                    cost_known=cost_known,
                    latency_ms=latency_ms,
                ),
                latency_ms=latency_ms,
                cost_minor=cost_minor,
                currency=_USD,
            )
        except _PostflightFailure as failure:
            return _failed(invocation, code=failure.code, state=SideEffectState.UNKNOWN, start=start)
        finally:
            _cleanup_edit_paths(wrapper_dir, cleanup_candidates)


class EvaluateImageCapability:
    """Independent evaluation adapter around ``vulca.aevaluate``."""

    manifest = _manifest(
        "vulca.image.evaluate",
        kind="image-evaluation",
        deterministic=False,
        authority_requirements=("evaluator_binding", "secret_binding"),
        evaluator_bindings=("independent_vlm",),
        retryable_codes=("PROVIDER_TIMEOUT", "PROVIDER_TRANSPORT_FAILED"),
    )

    def __init__(self, *, runtime: CapabilityRuntime | None = None) -> None:
        self.runtime = runtime or EnvironmentCapabilityRuntime()

    async def invoke(self, invocation: CapabilityInvocation) -> CapabilityResult:
        start = time.perf_counter()
        try:
            inputs = invocation.inputs
            options = invocation.options
            image = _image_argument(inputs.get("image"), options)
            intent = _text(inputs, "intent")
            tradition = _text(inputs, "tradition")
            subject = _text(inputs, "subject")
            skills_value = inputs.get("skills", [])
            if not isinstance(skills_value, list) or not all(isinstance(skill, str) for skill in skills_value):
                raise _PreflightFailure("INVALID_INPUT")
            binding_ref = options.get("binding_ref")
            if not isinstance(binding_ref, str) or not binding_ref.strip():
                raise _PreflightFailure("INVALID_PROVIDER_BINDING")
            api_key = self.runtime.api_key(binding_ref=binding_ref)
            if not isinstance(api_key, str):
                raise _PreflightFailure("INVALID_PROVIDER_BINDING")
            mock = options.get("mock", False)
            if not isinstance(mock, bool):
                raise _PreflightFailure("INVALID_OPTIONS")
            mode = _text(inputs, "mode") or "strict"
            vlm_model = _text(inputs, "vlm_model")
        except _PreflightFailure as failure:
            return _failed(invocation, code=failure.code, state=SideEffectState.NOT_STARTED, start=start)
        except _PROVIDER_CONSTRUCTION_ERRORS:
            return _failed(
                invocation,
                code="PROVIDER_CONSTRUCTION_FAILED",
                state=SideEffectState.NOT_STARTED,
                start=start,
            )

        try:
            result = await aevaluate(
                image,
                intent=intent,
                tradition=tradition,
                subject=subject,
                skills=cast(list[str], skills_value),
                api_key=api_key,
                mock=mock,
                mode=mode,
                vlm_model=vlm_model,
            )
        except TimeoutError:
            return _failed(invocation, code="PROVIDER_TIMEOUT", state=SideEffectState.UNKNOWN, start=start)
        except OSError:
            return _failed(
                invocation,
                code="PROVIDER_TRANSPORT_FAILED",
                state=SideEffectState.UNKNOWN,
                start=start,
            )
        except NotImplementedError:
            return _failed(invocation, code="PROVIDER_UNSUPPORTED", state=SideEffectState.UNKNOWN, start=start)
        except ValueError:
            return _failed(invocation, code="PROVIDER_FAILED", state=SideEffectState.UNKNOWN, start=start)

        try:
            output = _evaluation_output(result)
            cost_value: object = result.cost_usd if isinstance(result, EvalResult) else (
                result.get("cost_usd") if isinstance(result, dict) else None
            )
            cost_minor, cost_known = _cost_minor(cost_value)
            latency_ms = _elapsed_ms(start)
            model = options.get("model")
            model_value = model if isinstance(model, str) and model.strip() else (vlm_model or None)
            provider = options.get("provider")
            provider_value = provider if isinstance(provider, str) and provider.strip() else "evaluator"
            return CapabilityResult(
                invocation_id=invocation.invocation_id,
                status=CapabilityStatus.SUCCEEDED,
                side_effect_state=SideEffectState.COMPLETED,
                output=output,
                artifacts=(),
                provider_receipt=_provider_receipt(
                    provider=provider_value,
                    model=model_value,
                    request_id=None,
                    cost_known=cost_known,
                    latency_ms=latency_ms,
                ),
                latency_ms=latency_ms,
                cost_minor=cost_minor,
                currency=_USD,
            )
        except _PostflightFailure as failure:
            return _failed(invocation, code=failure.code, state=SideEffectState.UNKNOWN, start=start)


def _evaluation_output(result: EvalResult | dict) -> dict[str, JsonValue]:
    if isinstance(result, EvalResult):
        values: Mapping[str, object] = {
            "score": result.score,
            "dimensions": result.dimensions,
            "rationales": result.rationales,
            "risk": result.risk_level,
            "risk_flags": result.risk_flags,
            "recommendations": result.recommendations,
            "summary": result.summary,
            "tradition": result.tradition,
            "latency_ms": result.latency_ms,
        }
    elif isinstance(result, dict):
        values = {
            "score": result.get("score"),
            "dimensions": result.get("dimensions", {}),
            "rationales": result.get("rationales", {}),
            "risk": result.get("risk", result.get("risk_level")),
            "risk_flags": result.get("risk_flags", []),
            "recommendations": result.get("recommendations", []),
            "summary": result.get("summary"),
            "tradition": result.get("tradition"),
            "latency_ms": result.get("latency_ms", 0),
        }
    else:
        raise _PostflightFailure("INVALID_EVALUATION_RESULT")
    output: dict[str, JsonValue] = {}
    for key, value in values.items():
        if value is not None:
            output[key] = _json_safe(value)
    return output


def builtin_registry(runtime: CapabilityRuntime | None = None) -> CapabilityRegistry:
    """Return a registry containing every exact first-JobClass Cell."""
    resolved_runtime = runtime or EnvironmentCapabilityRuntime()
    registry = CapabilityRegistry()
    registry.register(GenerateImageCapability(runtime=resolved_runtime))
    registry.register(EditImageCapability(runtime=resolved_runtime))
    from .static import AdaptStaticCapability, ComposeStaticCapability, ValidateStaticCapability

    registry.register(ComposeStaticCapability())
    registry.register(AdaptStaticCapability())
    registry.register(ValidateStaticCapability())
    registry.register(EvaluateImageCapability(runtime=resolved_runtime))
    return registry


__all__ = [
    "CapabilityRuntime",
    "EnvironmentCapabilityRuntime",
    "GenerateImageCapability",
    "EditImageCapability",
    "EvaluateImageCapability",
    "builtin_registry",
]
