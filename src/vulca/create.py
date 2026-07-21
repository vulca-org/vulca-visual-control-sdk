"""Create API -- local pipeline execution or remote API call."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from vulca.types import CreateResult


async def acreate(
    intent: str,
    *,
    tradition: str = "",
    subject: str = "",
    provider: str = "nb2",
    image_provider: object | None = None,
    mode: str = "auto",
    base_url: str = "",
    api_key: str = "",
    hitl: bool = False,
    weights: dict[str, float] | None = None,
    eval_mode: str = "strict",
    reference: str = "",
    ref_type: str = "full",
    colors: str = "",
    content_lock: bool = False,
    output_is_artwork_itself: bool = False,
) -> CreateResult:
    """Create artwork via local pipeline or remote API (async).

    Parameters
    ----------
    intent:
        Natural language description of what to create.
    tradition:
        Cultural tradition. If empty, auto-detected.
    subject:
        Optional artwork subject/title.
    provider:
        Image generation provider name (nb2 | mock | gemini | openai | comfyui).
    image_provider:
        Custom ``ImageProvider`` instance. Overrides the ``provider`` string
        lookup in the registry. Must implement the ``ImageProvider`` protocol.
    mode:
        Execution mode: 'local' (pipeline engine), 'remote' (API call),
        or 'auto' (local if mock or custom provider, else remote).
    base_url:
        VULCA API base URL (remote mode). Defaults to VULCA_API_URL env.
    api_key:
        API key. Defaults to VULCA_API_KEY env.
    hitl:
        Enable human-in-the-loop. Pipeline pauses before 'decide' node.
    weights:
        Custom L1-L5 weights, e.g. {"L1": 0.3, "L2": 0.2, ...}.
    reference:
        Reference image path or base64. Also serves as sketch input --
        providers treat both identically as ``reference_image_b64``.
    content_lock:
        Treat explicit subjects and visible attributes in the intent as
        non-negotiable generation and evaluation requirements.
    output_is_artwork_itself:
        Treat the requested artwork as the full output surface. Generation and
        evaluation should reject gallery/display/mockup artifacts.

    Returns
    -------
    CreateResult
        Complete creation result with session ID, rounds, and scores.
    """
    use_local = (
        mode == "local"
        or image_provider is not None  # custom provider requires local execution
        or (mode == "auto" and not base_url and not os.environ.get("VULCA_API_URL"))
        # auto mode: prefer local unless a remote API URL is explicitly configured
    )
    if use_local:
        return await _create_local(
            intent,
            tradition=tradition,
            subject=subject,
            provider=provider,
            image_provider=image_provider,
            hitl=hitl,
            weights=weights,
            eval_mode=eval_mode,
            reference=reference,
            ref_type=ref_type,
            colors=colors,
            api_key=api_key,
            content_lock=content_lock,
            output_is_artwork_itself=output_is_artwork_itself,
        )
    return await _create_remote(
        intent,
        tradition=tradition,
        subject=subject,
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        content_lock=content_lock,
        output_is_artwork_itself=output_is_artwork_itself,
    )


async def _create_local(
    intent: str,
    *,
    tradition: str = "",
    subject: str = "",
    provider: str = "mock",
    image_provider: object | None = None,
    hitl: bool = False,
    weights: dict[str, float] | None = None,
    eval_mode: str = "strict",
    reference: str = "",
    ref_type: str = "full",
    colors: str = "",
    api_key: str = "",
    content_lock: bool = False,
    output_is_artwork_itself: bool = False,
) -> CreateResult:
    """Run the slim pipeline engine locally."""
    from vulca._image import resolve_image_input
    from vulca.pipeline.engine import execute
    from vulca.pipeline.hooks import default_on_complete
    from vulca.pipeline.templates import DEFAULT
    from vulca.pipeline.types import PipelineInput

    # Build node_params from custom weights
    node_params: dict[str, dict] = {}
    if weights:
        node_params["evaluate"] = {"custom_weights": weights}

    if content_lock or output_is_artwork_itself:
        from vulca.content_lock import ContentLock, extract_content_lock

        artifact_boundary = output_is_artwork_itself or content_lock
        if content_lock:
            lock = extract_content_lock(
                intent,
                output_is_artwork_itself=artifact_boundary,
            )
        else:
            lock = ContentLock(
                original_intent=" ".join(intent.strip().split()),
                output_is_artwork_itself=artifact_boundary,
            )
        if lock.has_requirements or lock.output_is_artwork_itself:
            lock_data = lock.to_dict()
            node_params["generate"] = {
                **node_params.get("generate", {}),
                "content_lock": lock_data,
            }
            node_params["evaluate"] = {
                **node_params.get("evaluate", {}),
                "content_lock": lock_data,
            }

    # Inject reference/colors into generate node params
    gen_params: dict[str, Any] = {}
    if reference:
        gen_params["reference_image_b64"] = resolve_image_input(reference)
        gen_params["reference_type"] = ref_type
    if colors:
        gen_params["color_palette"] = colors
    if gen_params:
        node_params["generate"] = {**node_params.get("generate", {}), **gen_params}

    pipeline_input = PipelineInput(
        subject=subject or intent,
        intent=intent,
        tradition=tradition or "default",
        provider=provider,
        api_key=api_key,
        node_params=node_params,
        image_provider=image_provider,
        eval_mode=eval_mode,
    )

    # HITL: interrupt before decide node; skip on_complete (pipeline incomplete)
    interrupt_before = {"decide"} if hitl else None
    on_complete = None if hitl else default_on_complete

    output = await execute(
        DEFAULT,
        pipeline_input,
        on_complete=on_complete,
        interrupt_before=interrupt_before,
    )

    # Extract suggestions/deviation_types/image_b64 from events
    suggestions: dict[str, str] = {}
    deviation_types: dict[str, str] = {}
    best_image_b64: str = ""
    for event in output.events:
        if event.event_type.value == "stage_completed" and event.stage == "evaluate":
            suggestions = event.payload.get("suggestions", {})
            deviation_types = event.payload.get("deviation_types", {})
        if event.event_type.value == "stage_completed" and event.stage in ("generate", "draft"):
            candidates = event.payload.get("candidates", [])
            if candidates:
                best_image_b64 = candidates[-1].get("image_b64", "")
            elif event.payload.get("image_b64"):
                best_image_b64 = event.payload["image_b64"]

    output_dict = output.to_dict()
    return CreateResult(
        session_id=output.session_id,
        mode="create",
        status=output.status,
        interrupted_at=output.interrupted_at,
        tradition=output.tradition,
        scores=output.final_scores,
        weighted_total=output.weighted_total,
        best_candidate_id=output.best_candidate_id,
        best_image_url=output.best_image_url,
        best_image_b64=best_image_b64,
        total_rounds=output.total_rounds,
        rounds=[r.to_dict() for r in output.rounds],
        summary=output.summary,
        recommendations=output.recommendations,
        risk_flags=output.risk_flags,
        content_fidelity_gate=output.content_fidelity_gate,
        evaluation_source=output.evaluation_source,
        evaluation_error=output.evaluation_error,
        suggestions=suggestions,
        deviation_types=deviation_types,
        eval_mode=eval_mode,
        latency_ms=output.total_latency_ms,
        cost_usd=output.total_cost_usd,
        raw=output_dict,
    )


async def _create_remote(
    intent: str,
    *,
    tradition: str = "",
    subject: str = "",
    provider: str = "nb2",
    base_url: str = "",
    api_key: str = "",
    content_lock: bool = False,
    output_is_artwork_itself: bool = False,
) -> CreateResult:
    """Call remote VULCA API for creation."""
    import httpx

    url = base_url or os.environ.get("VULCA_API_URL", "http://localhost:8001")
    key = api_key or os.environ.get("VULCA_API_KEY", "")

    body = {
        "intent": intent,
        "tradition": tradition or "default",
        "subject": subject or intent,
        "provider": provider,
        "stream": False,
    }
    if content_lock:
        body["content_lock"] = True
    if output_is_artwork_itself or content_lock:
        body["output_is_artwork_itself"] = True

    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{url}/api/v1/create",
            json=body,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    return CreateResult(
        session_id=data.get("session_id", ""),
        mode=data.get("mode", "create"),
        tradition=data.get("tradition", "default"),
        scores=data.get("scores") or {},
        weighted_total=data.get("weighted_total") or 0.0,
        best_candidate_id=data.get("best_candidate_id") or "",
        best_image_url=data.get("best_image_url") or "",
        total_rounds=data.get("total_rounds") or 0,
        rounds=data.get("rounds") or [],
        summary=data.get("summary") or "",
        recommendations=data.get("recommendations") or [],
        risk_flags=data.get("risk_flags") or [],
        content_fidelity_gate=data.get("content_fidelity_gate") or {},
        evaluation_source=data.get("evaluation_source") or "",
        evaluation_error=data.get("evaluation_error") or "",
        latency_ms=data.get("latency_ms", 0),
        cost_usd=data.get("cost_usd", 0.0),
        raw=data,
    )


def create(
    intent: str,
    *,
    tradition: str = "",
    subject: str = "",
    provider: str = "nb2",
    image_provider: object | None = None,
    mode: str = "auto",
    base_url: str = "",
    api_key: str = "",
    hitl: bool = False,
    weights: dict[str, float] | None = None,
    eval_mode: str = "strict",
    reference: str = "",
    ref_type: str = "full",
    colors: str = "",
    content_lock: bool = False,
    output_is_artwork_itself: bool = False,
) -> CreateResult:
    """Create artwork (synchronous wrapper).

    See :func:`acreate` for parameter documentation.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    coro = acreate(
        intent,
        tradition=tradition,
        subject=subject,
        provider=provider,
        image_provider=image_provider,
        mode=mode,
        base_url=base_url,
        api_key=api_key,
        hitl=hitl,
        weights=weights,
        eval_mode=eval_mode,
        reference=reference,
        ref_type=ref_type,
        colors=colors,
        content_lock=content_lock,
        output_is_artwork_itself=output_is_artwork_itself,
    )

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)
