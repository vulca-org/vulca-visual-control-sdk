# Blind Relation Gate And Track1 Champion Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generic blind relation gate to Vulca so relation semantics are judged from the image before caption anchoring, then use it to harden AffectiveArt Track1 candidate evaluation.

**Architecture:** Vulca keeps the reusable capability: a blind image-only relation read, a deterministic relation comparator, and content-fidelity score capping when the blind read contradicts required relations. The challenge repo remains a consumer: it runs champion/candidate audits and only accepts replacements that are clear wins under caption fidelity, artifact boundary, style, emotion, and blind relation checks.

**Tech Stack:** Python 3, pytest, LiteLLM/Gemini VLM scoring path, existing `vulca.content_lock` and `vulca.pipeline.nodes.evaluate` modules, existing Track1 audit scripts in `/Users/yhryzy/dev/emoart-130k`.

---

## File Structure

- Modify: `src/vulca/content_lock.py`
  - Add blind-relation prompt construction.
  - Add deterministic blind-relation gate construction.
  - Extend `apply_content_fidelity_gate` to cap high scores when blind relation decision is `reject` or `hold`.
- Modify: `src/vulca/_vlm.py`
  - Add a second image-only VLM call for content locks with required relations.
  - Merge blind relation gate output into `content_fidelity_gate`.
  - Keep primary scoring usable if the blind VLM call fails.
- Modify: `tests/test_content_lock.py`
  - Unit-test blind prompt non-anchoring, reject/hold/pass gate decisions, and score cap behavior.
- Modify: `tests/test_evaluate.py` or `tests/test_vlm_prompt.py`
  - Integration-test that `score_image`/`EvaluateNode` propagates blind gate metadata without requiring live network.
- Read-only consumer: `/Users/yhryzy/dev/emoart-130k/scripts/track1_quality_review.py`
  - Use existing heuristic/VLM review first. Do not mutate Track1 submission packages during this plan.

## Task 1: Content-Lock Blind Relation Helpers

**Files:**
- Modify: `src/vulca/content_lock.py`
- Test: `tests/test_content_lock.py`

- [ ] **Step 1: Write failing tests**

Add tests that express the API before implementation:

```python
from vulca.content_lock import (
    build_blind_relation_gate,
    build_blind_relation_read_prompt,
)


def test_blind_relation_prompt_does_not_anchor_on_caption_or_forbidden_reading():
    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    prompt = build_blind_relation_read_prompt(lock)

    assert "caption" not in prompt.lower()
    assert "escort" not in prompt.lower()
    assert "protect" not in prompt.lower()
    assert "soldiers chasing civilians" not in prompt.lower()
    assert "visible relationships" in prompt.lower()


def test_blind_relation_gate_rejects_forbidden_primary_reading():
    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    gate = build_blind_relation_gate(
        lock,
        {
            "primary_reading": "Mounted soldiers appear to chase fleeing civilians.",
            "apparent_relations": ["mounted soldiers chasing civilians"],
            "ambiguous_readings": [],
        },
    )

    assert gate["blind_relation_decision"] == "reject"
    assert "soldiers chasing civilians" in gate["blind_forbidden_readings_present"]


def test_blind_relation_gate_holds_ambiguous_relation_reading():
    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    gate = build_blind_relation_gate(
        lock,
        {
            "primary_reading": "The riders could be escorting or pursuing the civilians.",
            "apparent_relations": ["riders behind fleeing civilians"],
            "ambiguous_readings": ["escort or pursuit"],
        },
    )

    assert gate["blind_relation_decision"] == "hold"
    assert gate["blind_ambiguous_readings"] == ["escort or pursuit"]


def test_blind_relation_gate_passes_clear_escort_reading():
    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    gate = build_blind_relation_gate(
        lock,
        {
            "primary_reading": "Mounted soldiers flank civilians and guide them away from burning ruins.",
            "apparent_relations": ["mounted soldiers guiding civilians away from burning ruins"],
            "ambiguous_readings": [],
        },
    )

    assert gate["blind_relation_decision"] == "pass"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
PYTHONPATH=src pytest tests/test_content_lock.py -k "blind_relation" -q
```

Expected: fail because `build_blind_relation_gate` and `build_blind_relation_read_prompt` are not defined.

- [ ] **Step 3: Implement minimal helpers**

Add functions to `src/vulca/content_lock.py`:

```python
def build_blind_relation_read_prompt(lock: ContentLock | dict[str, Any]) -> str:
    content_lock = content_lock_from_dict(lock) if isinstance(lock, dict) else lock
    if not content_lock.required_relations:
        return ""
    return "\n".join(
        [
            "BLIND IMAGE RELATION READ:",
            "Describe only what is visible in the image. Do not use any external caption, prompt, sample id, filename, or expected story.",
            "Focus on visible relationships among people, animals, vehicles, objects, threats, movement direction, gaze, weapons, gestures, and protection cues.",
            "Return exactly one JSON object with these fields:",
            '"visible_entities": [short strings],',
            '"primary_reading": "one sentence describing the most natural visible relationship reading",',
            '"apparent_relations": [short subject-relation-object strings visible in the image],',
            '"threat_cues": [short strings],',
            '"protective_cues": [short strings],',
            '"ambiguous_readings": [short strings for plausible alternate readings, or empty list],',
            '"confidence": number from 0.0 to 1.0.',
        ]
    )


def build_blind_relation_gate(
    lock: ContentLock | dict[str, Any],
    blind_read: dict[str, Any] | None,
) -> dict[str, Any]:
    content_lock = content_lock_from_dict(lock) if isinstance(lock, dict) else lock
    if not content_lock.required_relations:
        return {"blind_relation_decision": "not_applicable"}
    if not blind_read:
        return {
            "blind_relation_decision": "unavailable",
            "blind_relation_reason": "blind relation read unavailable",
        }
    primary = str(blind_read.get("primary_reading") or "")
    apparent = _as_string_list(blind_read.get("apparent_relations"))
    ambiguous = _as_string_list(blind_read.get("ambiguous_readings"))
    joined = " ".join([primary, *apparent]).lower()
    forbidden_present = [
        reading
        for reading in content_lock.forbidden_readings
        if _relation_reading_matches(reading, joined)
    ]
    decision = "pass"
    reason = "blind read did not contradict required relations"
    if forbidden_present:
        decision = "reject"
        reason = "blind read matches forbidden relation reading"
    elif ambiguous:
        decision = "hold"
        reason = "blind read is ambiguous for required relations"
    return {
        "blind_relation_decision": decision,
        "blind_relation_reason": reason,
        "blind_primary_reading": primary,
        "blind_apparent_relations": apparent,
        "blind_ambiguous_readings": ambiguous,
        "blind_forbidden_readings_present": forbidden_present,
    }
```

Also add `_relation_reading_matches(reading: str, joined: str) -> bool` with conservative matching for `chasing`, `attacking`, `threatened`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
PYTHONPATH=src pytest tests/test_content_lock.py -k "blind_relation" -q
```

Expected: all selected tests pass.

## Task 2: Score Cap For Blind Reject/Hold

**Files:**
- Modify: `src/vulca/content_lock.py`
- Test: `tests/test_content_lock.py`

- [ ] **Step 1: Write failing test**

Add:

```python
def test_blind_relation_reject_caps_high_score():
    result = {
        "scores": {"L1": 0.95, "L2": 0.92, "L3": 1.0, "L4": 1.0, "L5": 0.94},
        "weighted_total": 0.965,
        "rationales": {},
    }
    gate = {
        "blind_relation_decision": "reject",
        "blind_forbidden_readings_present": ["soldiers chasing civilians"],
        "blind_primary_reading": "Mounted soldiers appear to chase civilians.",
    }

    gated = apply_content_fidelity_gate(result, gate)

    assert gated["weighted_total"] == 0.25
    assert "Blind relation gate rejected image" in gated["rationales"]["content_fidelity"]
    assert "content_fidelity_failed" in gated["risk_flags"]
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
PYTHONPATH=src pytest tests/test_content_lock.py::test_blind_relation_reject_caps_high_score -q
```

Expected: fail because current `apply_content_fidelity_gate` ignores `blind_relation_decision`.

- [ ] **Step 3: Implement score cap**

In `apply_content_fidelity_gate`, read:

```python
blind_relation_decision = str(gate.get("blind_relation_decision") or "")
blind_relation_failed = blind_relation_decision in {"reject", "hold"}
```

Include `blind_relation_failed` in the cap condition and add rationale:

```python
if blind_relation_failed:
    rationale_parts.append(
        f"Blind relation gate rejected image: {gate.get('blind_relation_reason') or blind_relation_decision}"
    )
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONPATH=src pytest tests/test_content_lock.py -k "blind_relation or relation_semantics" -q
```

Expected: selected tests pass.

## Task 3: VLM Blind Read Integration

**Files:**
- Modify: `src/vulca/_vlm.py`
- Test: `tests/test_vlm_prompt.py` or `tests/test_evaluate.py`

- [ ] **Step 1: Write failing integration test**

Patch `litellm.acompletion` with two responses: the normal caption-conditioned score and the blind relation read. Assert the returned `content_fidelity_gate` includes `blind_relation_decision="reject"` when the blind read says pursuit.

```python
@pytest.mark.asyncio
async def test_score_image_adds_blind_relation_gate_for_required_relations(monkeypatch):
    from vulca._vlm import score_image
    from vulca.content_lock import extract_content_lock

    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    normal_response = _completion_response(
        '<scoring>{"L1":0.9,"L2":0.9,"L3":0.9,"L4":0.9,"L5":0.9,'
        '"L1_rationale":"ok","L2_rationale":"ok","L3_rationale":"ok","L4_rationale":"ok","L5_rationale":"ok",'
        '"missing_required_subjects":[],"missing_required_text_elements":[],"missing_required_surface":[],'
        '"missing_required_style_attributes":[],"apparent_relations":["caption-conditioned escort"],'
        '"relation_semantics_failed":false,"forbidden_readings_present":[],'
        '"forbidden_visual_artifacts":[],"unwanted_visible_text":false,"output_is_artwork_itself":true,'
        '"risk_flags":[]}</scoring>'
    )
    blind_response = _completion_response(
        '{"visible_entities":["mounted soldiers","civilians"],'
        '"primary_reading":"Mounted soldiers appear to chase fleeing civilians.",'
        '"apparent_relations":["mounted soldiers chasing civilians"],'
        '"threat_cues":[],"protective_cues":[],"ambiguous_readings":[],"confidence":0.82}'
    )
    calls = [normal_response, blind_response]

    async def fake_completion(**kwargs):
        return calls.pop(0)

    monkeypatch.setattr("litellm.acompletion", fake_completion)

    result = await score_image(
        img_b64="iVBORw0KGgo=",
        mime="image/png",
        subject="track1_0747",
        tradition="default",
        api_key="fake-key",
        content_lock=lock.to_dict(),
    )

    gate = result["content_fidelity_gate"]
    assert gate["blind_relation_decision"] == "reject"
    assert gate["blind_forbidden_readings_present"] == ["soldiers chasing civilians"]
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
PYTHONPATH=src pytest tests/test_vlm_prompt.py -k "blind_relation_gate" -q
```

Expected: fail because `score_image` does not make a blind relation read yet.

- [ ] **Step 3: Implement integration**

In `src/vulca/_vlm.py`, after parsing the normal VLM scoring JSON and before returning data:

```python
blind_relation_gate = None
if resolved_content_lock is not None and resolved_content_lock.required_relations:
    from vulca.content_lock import build_blind_relation_gate

    blind_read = await _blind_relation_read(
        img_b64=img_b64,
        mime=mime,
        api_key=api_key,
        model=model,
        api_base=api_base,
    )
    blind_relation_gate = build_blind_relation_gate(resolved_content_lock, blind_read)
```

Merge `blind_relation_gate` into `content_fidelity_gate` when present. Add `_blind_relation_read(...)` that calls LiteLLM with the image and `build_blind_relation_read_prompt`, then parses JSON with `parse_llm_json`. On exception, return `{"_error": str(exc)}` and let `build_blind_relation_gate` decide `unavailable`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONPATH=src pytest tests/test_content_lock.py tests/test_vlm_prompt.py -k "blind_relation or relation_semantics or content_fidelity" -q
```

Expected: selected tests pass.

## Task 4: Challenge Evaluation Pass

**Files:**
- Read: `/Users/yhryzy/dev/emoart-130k/submissions/track1_submission.json`
- Read: `/Users/yhryzy/dev/emoart-130k/submissions/track1_candidate_v2/submission.json`
- Read/write reports under `/Users/yhryzy/dev/emoart-130k/experiments/track1_champion_quality_review_*_20260510/`

- [ ] **Step 1: Run heuristic full-package scan**

Run:

```bash
python3 scripts/track1_quality_review.py --image-dir submissions/track1/images --out-dir experiments/track1_champion_quality_review_current_20260510 --heuristic-only
python3 scripts/track1_quality_review.py --image-dir submissions/track1_candidate_v2/images --out-dir experiments/track1_champion_quality_review_candidate_v2_20260510 --heuristic-only
```

Expected: each command writes `heuristic_risk_rank.json`, `quality_review_report.json`, and `quality_review_report.md`.

- [ ] **Step 2: Run live VLM review on top-risk samples**

Use the Gemini key from Keychain without printing it:

```bash
GEMINI_API_KEY="$(security find-generic-password -s affectiveart-gemini-api-key -a gemini -w)" python3 scripts/track1_quality_review.py --image-dir submissions/track1/images --out-dir experiments/track1_champion_quality_review_current_20260510 --model gemini-3-flash-preview --limit 40
GEMINI_API_KEY="$(security find-generic-password -s affectiveart-gemini-api-key -a gemini -w)" python3 scripts/track1_quality_review.py --image-dir submissions/track1_candidate_v2/images --out-dir experiments/track1_champion_quality_review_candidate_v2_20260510 --model gemini-3-flash-preview --limit 40
```

Expected: each report summarizes high-priority replacement risks. Quota exhaustion should be reported with exact retry delay if present.

- [ ] **Step 3: Run 0747 blind relation live dogfood**

After Vulca blind gate is implemented, evaluate:

```bash
PYTHONPATH=/Users/yhryzy/dev/vulca/.worktrees/caption-fidelity-content-lock-v1/src:$PWD \
GEMINI_API_KEY="$(security find-generic-password -s affectiveart-gemini-api-key -a gemini -w)" \
VULCA_VLM_MODEL=gemini/gemini-3-flash-preview \
python3 scripts/track1_challenger_130k_vulca.py \
  --sample-id track1_0747 \
  --out-dir experiments/track1_130k_compiler_gate_v1/blind_relation_gate_0747_dogfood \
  --force
```

Expected: the generated create JSON contains a content fidelity gate whose blind relation result does not allow a pursuit/chase image to be accepted.

## Self-Review Checklist

- Spec coverage: covers generic Vulca gate, 0747 false-negative root cause, and challenge-side champion evaluation.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: helper names are stable across tests and implementation snippets: `build_blind_relation_read_prompt`, `build_blind_relation_gate`, `blind_relation_decision`.
- Submission safety: the plan does not mutate `/Users/yhryzy/dev/emoart-130k/submissions/track1_submission.json`, `/Users/yhryzy/dev/emoart-130k/submissions/track1_submission.zip`, or `/Users/yhryzy/dev/emoart-130k/submissions/track1/images`.
