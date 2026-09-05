"""Frozen, hash-bound official OpenAI image generation price schedule and estimator.

Observed 2026-08-14 from official OpenAI pricing documentation.
Provides deterministic canonical schedule hashing and conservative pre-call
maximum cost estimation to support accountable runtime spend reservation.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
import math
from typing import Any, Mapping


class PriceEstimationError(ValueError):
    """Raised when a pre-call cost estimate cannot be proven or verified."""

    def __init__(self, code: str, message: str = "") -> None:
        full_msg = f"{code}: {message}" if message else code
        super().__init__(full_msg)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ImagePriceSchedule:
    schedule_id: str
    provider: str
    observed_date: str
    currency: str
    schedule_hash: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class ImagePriceEstimate:
    estimated_max_cost_usd: float
    estimated_max_cost_minor: int
    currency: str
    schedule_id: str
    schedule_hash: str
    model: str
    operation: str
    image_count: int
    size: str
    quality: str
    output_format: str
    input_tokens_upper_bound: int
    output_tokens_upper_bound: int
    details: dict[str, Any]


# Canonical frozen schedule dictionary observed 2026-08-14
OPENAI_IMAGE_PRICE_SCHEDULE_2026_08_14: dict[str, Any] = {
    "schedule_id": "openai.image.pricing@2026-08-14",
    "provider": "openai",
    "observed_date": "2026-08-14",
    "currency": "USD",
    "models": {
        "gpt-image-2-2026-04-21": {
            "pricing_type": "token",
            "input_cost_per_million": 8.0,
            "output_cost_per_million": 30.0,
            "allowed_operations": ["generate", "edit"],
            "allowed_formats": ["png", "jpeg", "jpg", "webp"],
            "image_output_tokens": {
                "1024x1024": {
                    "low": 884,
                    "medium": 1768,
                    "high": 3536,
                },
                "1024x1536": {
                    "low": 1326,
                    "medium": 2652,
                    "high": 5304,
                },
                "1536x1024": {
                    "low": 1326,
                    "medium": 2652,
                    "high": 5304,
                },
                "1024x1792": {
                    "low": 1547,
                    "medium": 3094,
                    "high": 6188,
                },
                "1792x1024": {
                    "low": 1547,
                    "medium": 3094,
                    "high": 6188,
                },
            },
        },
        "gpt-image-2": {
            "pricing_type": "token",
            "input_cost_per_million": 8.0,
            "output_cost_per_million": 30.0,
            "allowed_operations": ["generate", "edit"],
            "allowed_formats": ["png", "jpeg", "jpg", "webp"],
            "image_output_tokens": {
                "1024x1024": {
                    "low": 884,
                    "medium": 1768,
                    "high": 3536,
                },
                "1024x1536": {
                    "low": 1326,
                    "medium": 2652,
                    "high": 5304,
                },
                "1536x1024": {
                    "low": 1326,
                    "medium": 2652,
                    "high": 5304,
                },
                "1024x1792": {
                    "low": 1547,
                    "medium": 3094,
                    "high": 6188,
                },
                "1792x1024": {
                    "low": 1547,
                    "medium": 3094,
                    "high": 6188,
                },
            },
        },
        "gpt-image-1.5": {
            "pricing_type": "token",
            "input_cost_per_million": 8.0,
            "output_cost_per_million": 32.0,
            "allowed_operations": ["generate", "edit"],
            "allowed_formats": ["png", "jpeg", "jpg", "webp"],
            "image_output_tokens": {
                "1024x1024": {
                    "low": 884,
                    "medium": 1768,
                    "high": 3536,
                },
            },
        },
        "gpt-image-1": {
            "pricing_type": "token",
            "input_cost_per_million": 10.0,
            "output_cost_per_million": 40.0,
            "allowed_operations": ["generate", "edit"],
            "allowed_formats": ["png", "jpeg", "jpg", "webp"],
            "image_output_tokens": {
                "1024x1024": {
                    "medium": 1768,
                },
            },
        },
        "dall-e-3": {
            "pricing_type": "per_image",
            "allowed_operations": ["generate"],
            "allowed_formats": ["png"],
            "rates": {
                "standard": {
                    "1024x1024": 0.040,
                    "1024x1792": 0.080,
                    "1792x1024": 0.080,
                },
                "hd": {
                    "1024x1024": 0.080,
                    "1024x1792": 0.120,
                    "1792x1024": 0.120,
                },
            },
        },
        "dall-e-2": {
            "pricing_type": "per_image",
            "allowed_operations": ["generate", "edit"],
            "allowed_formats": ["png"],
            "rates": {
                "standard": {
                    "1024x1024": 0.020,
                    "1024x1536": 0.018,
                    "1536x1024": 0.020,
                },
            },
        },
    },
}


def _compute_canonical_hash(payload: Mapping[str, Any]) -> str:
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


_SCHEDULE_HASH_2026_08_14 = _compute_canonical_hash(OPENAI_IMAGE_PRICE_SCHEDULE_2026_08_14)


def get_openai_image_price_schedule() -> ImagePriceSchedule:
    """Return the frozen canonical OpenAI image price schedule and its hash."""
    return ImagePriceSchedule(
        schedule_id=OPENAI_IMAGE_PRICE_SCHEDULE_2026_08_14["schedule_id"],
        provider=OPENAI_IMAGE_PRICE_SCHEDULE_2026_08_14["provider"],
        observed_date=OPENAI_IMAGE_PRICE_SCHEDULE_2026_08_14["observed_date"],
        currency=OPENAI_IMAGE_PRICE_SCHEDULE_2026_08_14["currency"],
        schedule_hash=_SCHEDULE_HASH_2026_08_14,
        raw=copy.deepcopy(OPENAI_IMAGE_PRICE_SCHEDULE_2026_08_14),
    )


def estimate_openai_image_cost(
    *,
    model: str,
    operation: str = "generate",
    image_count: int = 1,
    size: str = "1024x1024",
    quality: str = "medium",
    output_format: str = "png",
    allow_reference_image: bool = False,
    reference_image: bool = False,
    prompt: str | None = None,
    max_prompt_chars: int = 4000,
    schedule_id: str | None = None,
    expected_schedule_hash: str | None = None,
) -> ImagePriceEstimate:
    """Calculate conservative pre-call maximum cost for an OpenAI image operation.

    Rejects unknown or unsupported models, operations, dimensions, qualities,
    disallowed references, invalid prompt bounds, and schedule mismatches.
    Never guesses or returns unverified pricing.
    """
    schedule = get_openai_image_price_schedule()

    live_hash = _compute_canonical_hash(schedule.raw)
    if live_hash != schedule.schedule_hash:
        raise PriceEstimationError(
            "SCHEDULE_HASH_MISMATCH",
            f"Schedule content hash {live_hash!r} does not match the frozen {schedule.schedule_hash!r}",
        )
    if schedule_id is not None and schedule_id != schedule.schedule_id:
        raise PriceEstimationError(
            "SCHEDULE_ID_MISMATCH",
            f"Expected schedule_id {schedule.schedule_id!r}, got {schedule_id!r}",
        )
    if expected_schedule_hash is not None and expected_schedule_hash != schedule.schedule_hash:
        raise PriceEstimationError(
            "SCHEDULE_HASH_MISMATCH",
            f"Expected schedule_hash {schedule.schedule_hash!r}, got {expected_schedule_hash!r}",
        )

    models = schedule.raw["models"]
    if model not in models:
        raise PriceEstimationError(
            "UNKNOWN_MODEL",
            f"Model {model!r} is not present in frozen price schedule {schedule.schedule_id}",
        )

    model_entry = models[model]
    allowed_ops = model_entry.get("allowed_operations", ["generate"])
    if operation not in allowed_ops:
        raise PriceEstimationError(
            "UNSUPPORTED_OPERATION",
            f"Operation {operation!r} not supported for model {model!r}; allowed: {allowed_ops}",
        )

    allowed_formats = model_entry.get("allowed_formats", ["png"])
    if not isinstance(output_format, str) or not output_format.strip():
        raise PriceEstimationError(
            "UNSUPPORTED_FORMAT",
            f"Output format must be a non-empty string, got {output_format!r}",
        )
    normalized_format = output_format.strip().lower()
    if normalized_format not in allowed_formats:
        raise PriceEstimationError(
            "UNSUPPORTED_FORMAT",
            f"Format {output_format!r} not supported for model {model!r}; allowed: {allowed_formats}",
        )

    if not isinstance(image_count, int) or image_count <= 0 or image_count > 10:
        raise PriceEstimationError(
            "INVALID_IMAGE_COUNT",
            f"Image count must be an integer between 1 and 10, got {image_count!r}",
        )

    if not allow_reference_image and reference_image:
        raise PriceEstimationError(
            "REFERENCE_IMAGE_DISALLOWED",
            "Reference image is disallowed for this request profile",
        )

    if not isinstance(max_prompt_chars, int) or max_prompt_chars <= 0:
        raise PriceEstimationError(
            "INVALID_PROMPT_BOUND",
            f"max_prompt_chars must be a positive integer, got {max_prompt_chars!r}",
        )

    if prompt is not None and len(prompt) > max_prompt_chars:
        raise PriceEstimationError(
            "PROMPT_EXCEEDS_BOUND",
            f"Prompt length ({len(prompt)} chars) exceeds bound ({max_prompt_chars} chars)",
        )

    pricing_type = model_entry["pricing_type"]
    if pricing_type == "token":
        output_token_matrix = model_entry.get("image_output_tokens", {})
        if size not in output_token_matrix:
            raise PriceEstimationError(
                "UNSUPPORTED_SIZE",
                f"Size {size!r} not supported for model {model!r}; available: {list(output_token_matrix.keys())}",
            )
        quality_map = output_token_matrix[size]
        if quality not in quality_map:
            raise PriceEstimationError(
                "UNSUPPORTED_QUALITY",
                f"Quality {quality!r} not supported for size {size!r} on model {model!r}; available: {list(quality_map.keys())}",
            )

        output_tokens_per_image = quality_map[quality]
        total_output_tokens = output_tokens_per_image * image_count
        output_rate = model_entry["output_cost_per_million"]
        output_cost_usd = (total_output_tokens * output_rate) / 1_000_000

        # Conservative prompt token upper bound (1 char <= 1 token)
        input_tokens_upper_bound = max_prompt_chars
        input_rate = model_entry["input_cost_per_million"]
        input_cost_usd = (input_tokens_upper_bound * input_rate) / 1_000_000

        total_cost_usd = round(output_cost_usd + input_cost_usd, 6)
        total_cost_minor = math.ceil(round(total_cost_usd * 100, 4))

        return ImagePriceEstimate(
            estimated_max_cost_usd=total_cost_usd,
            estimated_max_cost_minor=total_cost_minor,
            currency="USD",
            schedule_id=schedule.schedule_id,
            schedule_hash=schedule.schedule_hash,
            model=model,
            operation=operation,
            image_count=image_count,
            size=size,
            quality=quality,
            output_format=normalized_format,
            input_tokens_upper_bound=input_tokens_upper_bound,
            output_tokens_upper_bound=total_output_tokens,
            details={
                "pricing_type": "token",
                "output_tokens_per_image": output_tokens_per_image,
                "output_cost_usd": round(output_cost_usd, 6),
                "input_cost_usd": round(input_cost_usd, 6),
            },
        )

    elif pricing_type == "per_image":
        rates = model_entry.get("rates", {})
        normalized_quality = quality.lower()
        if normalized_quality in ("high", "auto"):
            normalized_quality = "hd"
        elif normalized_quality in ("medium", "low"):
            normalized_quality = "standard"

        if normalized_quality not in rates:
            raise PriceEstimationError(
                "UNSUPPORTED_QUALITY",
                f"Quality {quality!r} not supported for model {model!r}; available: {list(rates.keys())}",
            )
        by_size = rates[normalized_quality]
        if size not in by_size:
            raise PriceEstimationError(
                "UNSUPPORTED_SIZE",
                f"Size {size!r} not supported for model {model!r} at quality {quality!r}; available: {list(by_size.keys())}",
            )
        rate_per_image = by_size[size]
        total_cost_usd = round(rate_per_image * image_count, 6)
        total_cost_minor = math.ceil(round(total_cost_usd * 100, 4))

        return ImagePriceEstimate(
            estimated_max_cost_usd=total_cost_usd,
            estimated_max_cost_minor=total_cost_minor,
            currency="USD",
            schedule_id=schedule.schedule_id,
            schedule_hash=schedule.schedule_hash,
            model=model,
            operation=operation,
            image_count=image_count,
            size=size,
            quality=quality,
            output_format=normalized_format,
            input_tokens_upper_bound=0,
            output_tokens_upper_bound=0,
            details={
                "pricing_type": "per_image",
                "rate_per_image": rate_per_image,
            },
        )

    raise PriceEstimationError("UNSUPPORTED_PRICING_TYPE", f"Unknown pricing type: {pricing_type!r}")
