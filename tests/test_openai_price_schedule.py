"""Tests for frozen OpenAI image price schedule and conservative pre-call estimator."""

from __future__ import annotations

import pytest

from vulca.providers.price_schedule import (
    OPENAI_IMAGE_PRICE_SCHEDULE_2026_08_14,
    ImagePriceEstimate,
    PriceEstimationError,
    estimate_openai_image_cost,
    get_openai_image_price_schedule,
)


def test_frozen_price_schedule_structure_and_deterministic_hash():
    schedule = get_openai_image_price_schedule()
    assert schedule.schedule_id == "openai.image.pricing@2026-08-14"
    assert schedule.provider == "openai"
    assert schedule.observed_date == "2026-08-14"
    assert schedule.currency == "USD"
    assert len(schedule.schedule_hash) == 64
    assert all(c in "0123456789abcdef" for c in schedule.schedule_hash)

    models = schedule.raw["models"]
    assert "gpt-image-2-2026-04-21" in models
    assert "gpt-image-2" in models
    assert "dall-e-3" in models


def test_estimate_cost_for_approved_gpt_image_2_snapshot_profile():
    schedule = get_openai_image_price_schedule()
    estimate = estimate_openai_image_cost(
        model="gpt-image-2-2026-04-21",
        operation="generate",
        image_count=1,
        size="1024x1024",
        quality="medium",
        output_format="png",
        allow_reference_image=False,
        max_prompt_chars=4000,
        schedule_id=schedule.schedule_id,
        expected_schedule_hash=schedule.schedule_hash,
    )
    assert isinstance(estimate, ImagePriceEstimate)
    assert estimate.model == "gpt-image-2-2026-04-21"
    assert estimate.operation == "generate"
    assert estimate.image_count == 1
    assert estimate.size == "1024x1024"
    assert estimate.quality == "medium"
    assert estimate.output_format == "png"
    assert estimate.output_tokens_upper_bound == 1768
    assert estimate.input_tokens_upper_bound == 4000
    # 1768 * 30/1M = 0.05304; 4000 * 8/1M = 0.032; total = 0.08504 USD
    assert estimate.estimated_max_cost_usd == pytest.approx(0.08504)
    # 0.08504 USD is 9 minor units (cents), which is <= 10 cents ceiling
    assert estimate.estimated_max_cost_minor == 9
    assert estimate.estimated_max_cost_minor <= 10
    assert estimate.currency == "USD"
    assert estimate.schedule_id == "openai.image.pricing@2026-08-14"
    assert estimate.schedule_hash == schedule.schedule_hash


def test_estimate_cost_rejects_unknown_model():
    with pytest.raises(PriceEstimationError) as exc_info:
        estimate_openai_image_cost(
            model="unknown-model-2026",
            operation="generate",
        )
    assert exc_info.value.code == "UNKNOWN_MODEL"


def test_estimate_cost_rejects_unsupported_operation():
    with pytest.raises(PriceEstimationError) as exc_info:
        estimate_openai_image_cost(
            model="gpt-image-2-2026-04-21",
            operation="video_generation",
        )
    assert exc_info.value.code == "UNSUPPORTED_OPERATION"


def test_estimate_cost_rejects_unsupported_size():
    with pytest.raises(PriceEstimationError) as exc_info:
        estimate_openai_image_cost(
            model="gpt-image-2-2026-04-21",
            operation="generate",
            size="512x512",
        )
    assert exc_info.value.code == "UNSUPPORTED_SIZE"


def test_estimate_cost_rejects_unsupported_quality():
    with pytest.raises(PriceEstimationError) as exc_info:
        estimate_openai_image_cost(
            model="gpt-image-2-2026-04-21",
            operation="generate",
            quality="ultra_hd",
        )
    assert exc_info.value.code == "UNSUPPORTED_QUALITY"


def test_estimate_cost_rejects_disallowed_reference_image():
    with pytest.raises(PriceEstimationError) as exc_info:
        estimate_openai_image_cost(
            model="gpt-image-2-2026-04-21",
            operation="generate",
            allow_reference_image=False,
            reference_image=True,
        )
    assert exc_info.value.code == "REFERENCE_IMAGE_DISALLOWED"


def test_estimate_cost_rejects_invalid_prompt_bounds():
    with pytest.raises(PriceEstimationError) as exc_info:
        estimate_openai_image_cost(
            model="gpt-image-2-2026-04-21",
            operation="generate",
            max_prompt_chars=0,
        )
    assert exc_info.value.code == "INVALID_PROMPT_BOUND"

    with pytest.raises(PriceEstimationError) as exc_info:
        estimate_openai_image_cost(
            model="gpt-image-2-2026-04-21",
            operation="generate",
            prompt="a" * 4001,
            max_prompt_chars=4000,
        )
    assert exc_info.value.code == "PROMPT_EXCEEDS_BOUND"


def test_estimate_cost_rejects_schedule_id_and_hash_mismatch():
    with pytest.raises(PriceEstimationError) as exc_info:
        estimate_openai_image_cost(
            model="gpt-image-2-2026-04-21",
            operation="generate",
            schedule_id="openai.image.pricing@2025-01-01",
        )
    assert exc_info.value.code == "SCHEDULE_ID_MISMATCH"

    schedule = get_openai_image_price_schedule()
    with pytest.raises(PriceEstimationError) as exc_info:
        estimate_openai_image_cost(
            model="gpt-image-2-2026-04-21",
            operation="generate",
            expected_schedule_hash="0000000000000000000000000000000000000000000000000000000000000000",
        )
    assert exc_info.value.code == "SCHEDULE_HASH_MISMATCH"


def test_estimate_cost_supports_dalle3_per_image():
    estimate = estimate_openai_image_cost(
        model="dall-e-3",
        operation="generate",
        image_count=1,
        size="1024x1024",
        quality="standard",
    )
    assert estimate.estimated_max_cost_usd == pytest.approx(0.04)
    assert estimate.estimated_max_cost_minor == 4
