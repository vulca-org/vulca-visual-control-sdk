"""Content-lock helpers for caption-faithful generation and evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContentLock:
    """Explicit user-requested content that should survive style optimization."""

    original_intent: str
    required_subjects: list[str] = field(default_factory=list)
    required_text_elements: list[str] = field(default_factory=list)
    required_surface: list[str] = field(default_factory=list)
    required_style_attributes: list[str] = field(default_factory=list)
    required_mood: list[str] = field(default_factory=list)
    required_relations: list[dict[str, str]] = field(default_factory=list)
    composition_intent: str = ""
    forbidden_readings: list[str] = field(default_factory=list)
    output_is_artwork_itself: bool = False

    @property
    def has_requirements(self) -> bool:
        return any(
            (
                self.required_subjects,
                self.required_text_elements,
                self.required_surface,
                self.required_style_attributes,
                self.required_mood,
                self.required_relations,
                self.composition_intent,
                self.forbidden_readings,
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "original_intent": self.original_intent,
            "required_subjects": list(self.required_subjects),
            "required_text_elements": list(self.required_text_elements),
            "required_surface": list(self.required_surface),
            "required_style_attributes": list(self.required_style_attributes),
            "required_mood": list(self.required_mood),
            "required_relations": [dict(relation) for relation in self.required_relations],
            "composition_intent": self.composition_intent,
            "forbidden_readings": list(self.forbidden_readings),
            "output_is_artwork_itself": self.output_is_artwork_itself,
        }


def content_lock_from_dict(data: dict[str, Any] | ContentLock) -> ContentLock:
    if isinstance(data, ContentLock):
        return data
    allowed = {
        "original_intent",
        "required_subjects",
        "required_text_elements",
        "required_surface",
        "required_style_attributes",
        "required_mood",
        "required_relations",
        "composition_intent",
        "forbidden_readings",
        "output_is_artwork_itself",
    }
    cleaned = {key: value for key, value in data.items() if key in allowed}
    return ContentLock(
        original_intent=str(cleaned.get("original_intent") or ""),
        required_subjects=_as_string_list(cleaned.get("required_subjects")),
        required_text_elements=_as_string_list(cleaned.get("required_text_elements")),
        required_surface=_as_string_list(cleaned.get("required_surface")),
        required_style_attributes=_as_string_list(cleaned.get("required_style_attributes")),
        required_mood=_as_string_list(cleaned.get("required_mood")),
        required_relations=_as_relation_list(cleaned.get("required_relations")),
        composition_intent=str(cleaned.get("composition_intent") or ""),
        forbidden_readings=_as_string_list(cleaned.get("forbidden_readings")),
        output_is_artwork_itself=bool(cleaned.get("output_is_artwork_itself")),
    )


def extract_content_lock(
    intent: str,
    *,
    output_is_artwork_itself: bool = True,
) -> ContentLock:
    """Extract explicit visual requirements from a short caption-like intent.

    This is intentionally conservative: it locks concrete, named objects and
    visible text/material requirements, but leaves broad style words to the
    tradition guidance unless they are clearly phrased as explicit attributes.
    """
    text = " ".join(intent.strip().split())
    lower = text.lower()

    subjects = _extract_subjects(text)
    subjects = _replace_known_subjects(subjects, lower)
    subjects.extend(_extract_keyword_subjects(lower))
    (
        relation_subjects,
        required_relations,
        composition_intent,
        forbidden_readings,
    ) = _extract_relation_semantics(lower)
    subjects.extend(relation_subjects)

    text_elements: list[str] = []
    if re.search(r"\bcircular calligraphy panel\b", lower):
        text_elements.append("circular calligraphy panel")
    elif re.search(r"\bvertical chinese calligraphy\b", lower):
        text_elements.append("vertical Chinese calligraphy")
    elif re.search(r"\bcalligraphy along the side\b", lower):
        text_elements.append("calligraphy along the side")
    elif re.search(r"\bcalligraphy\b", lower):
        text_elements.append("calligraphy")
    if re.search(r"\bred seals?\b", lower):
        text_elements.append("red seals")

    surface: list[str] = []
    if re.search(r"\baged paper\b", lower):
        surface.append("aged paper")
    if re.search(r"\bgraph paper\b", lower):
        surface.append("graph paper")
    if re.search(r"\bpale beige silk ground\b", lower):
        surface.append("pale beige silk ground")
    if re.search(r"\bornate pale patterned border\b", lower):
        surface.append("ornate pale patterned border")

    style_attributes: list[str] = []
    if re.search(r"\bgongbi vertical hanging scroll\b", lower):
        style_attributes.append("Gongbi vertical hanging scroll")
    elif re.search(r"\bvertical hanging scroll\b", lower):
        style_attributes.append("vertical hanging scroll")
    if re.search(r"\bgongbi album leaf\b", lower):
        style_attributes.append("Gongbi album leaf")
    if re.search(r"\brectangular frame\b", lower):
        style_attributes.append("rectangular frame")
    if re.search(r"\bmonochrome pencil style\b", lower):
        style_attributes.append("monochrome pencil style")
    if re.search(r"\bdelicate linework\b", lower):
        style_attributes.append("delicate linework")
    if re.search(r"\bmuted brown tones\b", lower):
        style_attributes.append("muted brown tones")
    if re.search(r"\bsparse brushwork\b", lower):
        style_attributes.append("sparse brushwork")

    mood: list[str] = []
    if re.search(r"\bcalm scholarly composition\b", lower):
        mood.append("calm scholarly composition")

    return ContentLock(
        original_intent=text,
        required_subjects=subjects,
        required_text_elements=_dedupe(text_elements),
        required_surface=_dedupe(surface),
        required_style_attributes=_dedupe(style_attributes),
        required_mood=_dedupe(mood),
        required_relations=required_relations,
        composition_intent=composition_intent,
        forbidden_readings=forbidden_readings,
        output_is_artwork_itself=output_is_artwork_itself,
    )


def build_content_lock_prompt(lock: ContentLock) -> str:
    """Build generation instructions that make explicit content non-negotiable."""
    if not lock.has_requirements and not lock.output_is_artwork_itself:
        return ""

    lines: list[str] = []
    if lock.output_is_artwork_itself:
        lines.extend(_build_artifact_boundary_lines(lock.original_intent))

    if lock.has_requirements:
        if lines:
            lines.append("")
        lines.extend(
            [
                "NON-NEGOTIABLE CONTENT REQUIREMENTS:",
                (
                    "The following requirements come from the user's explicit request "
                    "and must be satisfied before style optimization."
                ),
            ]
        )
    if lock.required_subjects:
        lines.append(f"- Required subjects: {', '.join(lock.required_subjects)}.")
    if lock.required_text_elements:
        lines.append(
            f"- Required text/seal elements: {', '.join(lock.required_text_elements)}."
        )
    if lock.required_surface:
        lines.append(f"- Required surface/material: {', '.join(lock.required_surface)}.")
    if lock.required_style_attributes:
        lines.append(
            f"- Required style attributes: {', '.join(lock.required_style_attributes)}."
        )
    if lock.required_mood:
        lines.append(f"- Required mood/composition: {', '.join(lock.required_mood)}.")
    if lock.required_relations:
        lines.append("RELATION SEMANTICS REQUIREMENTS:")
        for relation in lock.required_relations:
            lines.append(f"- {_format_required_relation(relation)}.")
    if lock.composition_intent:
        lines.append(f"COMPOSITION INTENT: {lock.composition_intent}.")
    if lock.forbidden_readings:
        lines.append(f"FORBIDDEN RELATION READINGS: {', '.join(lock.forbidden_readings)}.")
    if lock.has_requirements:
        lines.append(
            "Do not replace these subjects with mountains, generic landscapes, "
            "or unrelated tradition prototypes."
        )
        lines.append(
            "Do not render sample IDs, filenames, watermarks, large labels, gallery "
            "walls, exhibition labels, framed museum installations, or photographed "
            "artwork mockups unless the user explicitly requested them."
        )
        lines.append(
            "If any required subject is absent, the image is a failed response even "
            "if the cultural style is strong."
        )
    return "\n".join(lines)


def build_content_fidelity_prompt(lock: ContentLock) -> str:
    """Build VLM scoring instructions for explicit content presence checks."""
    if not lock.has_requirements and not lock.output_is_artwork_itself:
        return ""

    lines = [
        "CONTENT FIDELITY CHECK:",
        (
            "Before final scoring, verify whether the artwork visibly contains "
            "the user's non-negotiable content requirements."
        ),
    ]
    if lock.required_subjects:
        lines.append(f"- Required subjects: {', '.join(lock.required_subjects)}")
    if lock.required_text_elements:
        lines.append(
            f"- Required text/seal elements: {', '.join(lock.required_text_elements)}"
        )
    if lock.required_surface:
        lines.append(f"- Required surface/material: {', '.join(lock.required_surface)}")
    if lock.required_style_attributes:
        lines.append(
            f"- Required style attributes: {', '.join(lock.required_style_attributes)}"
        )
    if lock.required_relations:
        lines.append(
            "- Required relations: "
            f"{'; '.join(_format_required_relation(relation) for relation in lock.required_relations)}"
        )
    if lock.composition_intent:
        lines.append(f"- Required composition intent: {lock.composition_intent}")
    if lock.forbidden_readings:
        lines.append(f"- Forbidden relation readings: {', '.join(lock.forbidden_readings)}")
    if lock.output_is_artwork_itself:
        lines.append(
            (
                "- Required artifact boundary: output_is_artwork_itself must be true; "
                "the image must be the requested artwork surface, not a photo, "
                "gallery scene, installation, catalog/mockup, or framed display."
            )
        )
    lines.extend(
        [
            (
                "Also check for forbidden visual artifacts: visible sample IDs, "
                "filenames, watermarks, large labels, gallery walls, exhibition "
                "labels, framed museum installations, and photographed artwork mockups."
            ),
            "Add these exact fields to the JSON inside <scoring>:",
            '"missing_required_subjects": [strings copied exactly from the required subjects list],',
            '"missing_required_text_elements": [strings copied exactly from the required text/seal list],',
            '"missing_required_surface": [strings copied exactly from the required surface/material list].',
            '"missing_required_style_attributes": [strings copied exactly from the required style attributes list],',
            '"apparent_relations": [short strings describing visible subject-relation-object readings],',
            '"relation_semantics_failed": true or false,',
            '"forbidden_readings_present": [strings copied from forbidden relation readings, or close visual readings],',
            '"forbidden_visual_artifacts": [visible forbidden artifacts, or an empty list].',
            '"unwanted_visible_text": true or false,',
            '"output_is_artwork_itself": true or false.',
            "Use an empty list when every item in a category is visible or no forbidden artifact is present.",
        ]
    )
    return "\n".join(lines)


def build_blind_relation_read_prompt(lock: ContentLock | dict[str, Any]) -> str:
    """Build an image-only relation-reading prompt without caption anchors."""
    content_lock = content_lock_from_dict(lock) if isinstance(lock, dict) else lock
    if not content_lock.required_relations:
        return ""

    return "\n".join(
        [
            "BLIND IMAGE RELATION READ:",
            (
                "Describe only what is visible in the image. Do not use any "
                "external prompt, sample id, filename, or expected story."
            ),
            (
                "Focus on visible relationships among people, animals, vehicles, "
                "objects, threats, movement direction, gaze, weapons, gestures, "
                "and safety cues."
            ),
            "Return exactly one JSON object with these fields:",
            '"visible_entities": [short strings],',
            (
                '"primary_reading": "one sentence describing the most natural '
                'visible relationship reading",'
            ),
            (
                '"apparent_relations": [short subject-relation-object strings '
                'visible in the image],'
            ),
            '"threat_cues": [short strings],',
            '"safety_cues": [short strings],',
            (
                '"ambiguous_readings": [short strings for plausible alternate '
                'readings, or empty list],'
            ),
            '"confidence": number from 0.0 to 1.0.',
        ]
    )


def build_blind_relation_gate(
    lock: ContentLock | dict[str, Any],
    blind_read: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare image-only relation reading against required relations."""
    content_lock = content_lock_from_dict(lock) if isinstance(lock, dict) else lock
    if not content_lock.required_relations:
        return {"blind_relation_decision": "not_applicable"}
    if not blind_read:
        return {
            "blind_relation_decision": "unavailable",
            "blind_relation_reason": "blind relation read unavailable",
        }
    if blind_read.get("_error"):
        return {
            "blind_relation_decision": "unavailable",
            "blind_relation_reason": str(blind_read.get("_error")),
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
    has_high_confidence_forbidden = any(
        reading != "soldiers chasing civilians" for reading in forbidden_present
    )
    if forbidden_present and has_high_confidence_forbidden:
        decision = "reject"
        reason = "blind read matches forbidden relation reading"
    elif ambiguous:
        decision = "hold"
        reason = "blind read is ambiguous for required relations"
    elif forbidden_present:
        decision = "reject"
        reason = "blind read matches forbidden relation reading"

    return {
        "blind_relation_decision": decision,
        "blind_relation_reason": reason,
        "blind_primary_reading": primary,
        "blind_apparent_relations": apparent,
        "blind_ambiguous_readings": ambiguous,
        "blind_forbidden_readings_present": forbidden_present,
    }


def build_content_fidelity_gate(
    lock: ContentLock | dict[str, Any],
    scoring_data: dict[str, Any],
) -> dict[str, Any]:
    """Create deterministic gate data from VLM missing-item fields."""
    content_lock = content_lock_from_dict(lock) if isinstance(lock, dict) else lock
    apparent_relations = _as_string_list(scoring_data.get("apparent_relations"))
    forbidden_artifacts = _as_string_list(
        scoring_data.get("forbidden_visual_artifacts")
    )
    inferred_artifacts = _infer_artifacts_from_readings(content_lock, apparent_relations)
    unwanted_visible_text = _as_optional_bool(scoring_data.get("unwanted_visible_text"))
    if "unrequested visible text labels" in inferred_artifacts:
        unwanted_visible_text = True
    return {
        "required_subjects": list(content_lock.required_subjects),
        "missing_required_subjects": _as_string_list(
            scoring_data.get("missing_required_subjects")
        ),
        "required_text_elements": list(content_lock.required_text_elements),
        "missing_required_text_elements": _as_string_list(
            scoring_data.get("missing_required_text_elements")
        ),
        "required_surface": list(content_lock.required_surface),
        "missing_required_surface": _as_string_list(
            scoring_data.get("missing_required_surface")
        ),
        "required_style_attributes": list(content_lock.required_style_attributes),
        "missing_required_style_attributes": _as_string_list(
            scoring_data.get("missing_required_style_attributes")
        ),
        "required_relations": [
            dict(relation) for relation in content_lock.required_relations
        ],
        "apparent_relations": apparent_relations,
        "relation_semantics_failed": _as_optional_bool(
            scoring_data.get("relation_semantics_failed")
        ),
        "forbidden_readings": list(content_lock.forbidden_readings),
        "forbidden_readings_present": _as_string_list(
            scoring_data.get("forbidden_readings_present")
        ),
        "forbidden_visual_artifacts": _dedupe([*forbidden_artifacts, *inferred_artifacts]),
        "required_output_is_artwork_itself": content_lock.output_is_artwork_itself,
        "output_is_artwork_itself": _as_optional_bool(
            scoring_data.get("output_is_artwork_itself")
        ),
        "unwanted_visible_text": unwanted_visible_text,
    }


def apply_content_fidelity_gate(result: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    """Cap high scores when required caption content is known missing."""
    missing_subjects = _as_string_list(gate.get("missing_required_subjects"))
    missing_text = _as_string_list(gate.get("missing_required_text_elements"))
    missing_surface = _as_string_list(gate.get("missing_required_surface"))
    missing_style = _as_string_list(gate.get("missing_required_style_attributes"))
    relation_semantics_failed = (
        _as_optional_bool(gate.get("relation_semantics_failed")) is True
    )
    forbidden_readings_present = _as_string_list(
        gate.get("forbidden_readings_present")
    )
    forbidden_artifacts = _as_string_list(gate.get("forbidden_visual_artifacts"))
    required_artwork_itself = bool(gate.get("required_output_is_artwork_itself"))
    output_is_artwork_itself = gate.get("output_is_artwork_itself")
    unwanted_visible_text = gate.get("unwanted_visible_text")
    artifact_boundary_failed = (
        required_artwork_itself and output_is_artwork_itself is False
    )
    unwanted_text_failed = unwanted_visible_text is True
    blind_relation_decision = str(gate.get("blind_relation_decision") or "")
    blind_relation_failed = blind_relation_decision in {"reject", "hold"}

    if not (
        missing_subjects
        or missing_text
        or missing_surface
        or missing_style
        or relation_semantics_failed
        or forbidden_readings_present
        or forbidden_artifacts
        or artifact_boundary_failed
        or unwanted_text_failed
        or blind_relation_failed
    ):
        return result

    updated = dict(result)
    scores = dict(updated.get("scores") or {})
    for key in ("L1", "L3", "L4", "L5"):
        scores[key] = min(float(scores.get(key, 0.0)), 0.25)
    updated["scores"] = scores
    updated["weighted_total"] = min(float(updated.get("weighted_total", 0.0)), 0.25)

    rationale_parts: list[str] = []
    if missing_subjects:
        rationale_parts.append(f"Missing required subjects: {', '.join(missing_subjects)}")
    if missing_text:
        rationale_parts.append(
            f"Missing required text elements: {', '.join(missing_text)}"
        )
    if missing_surface:
        rationale_parts.append(
            f"Missing required surface/material: {', '.join(missing_surface)}"
        )
    if missing_style:
        rationale_parts.append(
            f"Missing required style attributes: {', '.join(missing_style)}"
        )
    if relation_semantics_failed:
        rationale_parts.append("Relation semantics failed")
    if forbidden_readings_present:
        rationale_parts.append(
            f"Forbidden relation readings: {', '.join(forbidden_readings_present)}"
        )
    if forbidden_artifacts:
        rationale_parts.append(
            f"Forbidden visual artifacts: {', '.join(forbidden_artifacts)}"
        )
    if artifact_boundary_failed:
        rationale_parts.append("Output is not the artwork itself")
    if unwanted_text_failed:
        rationale_parts.append("Unwanted visible text")
    if blind_relation_failed:
        rationale_parts.append(
            "Blind relation gate rejected image: "
            f"{gate.get('blind_relation_reason') or blind_relation_decision}"
        )
    rationales = dict(updated.get("rationales") or {})
    rationales["content_fidelity"] = "; ".join(rationale_parts)
    updated["rationales"] = rationales

    risk_flags = list(updated.get("risk_flags") or [])
    if "content_fidelity_failed" not in risk_flags:
        risk_flags.append("content_fidelity_failed")
    updated["risk_flags"] = risk_flags
    updated["content_fidelity_gate"] = dict(gate)
    return updated


def _extract_subjects(text: str) -> list[str]:
    match = re.search(
        r"\b(?:of|showing|featuring|depicting)\s+(.+?)(?:\s+"
        r"(?:beside|with|on|under|against|in|at|near|over|around)\b|,\s+with\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    segment = match.group(1)
    pieces = re.split(r",\s*(?:and\s+)?|\s+and\s+", segment)
    subjects = []
    for piece in pieces:
        normalized = _clean_subject(piece)
        if normalized:
            subjects.append(normalized)
    return _dedupe(subjects)


def _infer_artifacts_from_readings(
    lock: ContentLock,
    apparent_relations: list[str],
) -> list[str]:
    """Infer obvious artifact-boundary failures from VLM free-text readings."""
    joined = " ".join(apparent_relations).lower()
    artifacts: list[str] = []
    if re.search(
        r"\b(meme|memes|social|icon|icons|qr|chat|ui|interface|screen|app|"
        r"notification|overlay|collage)\b",
        joined,
    ):
        artifacts.append("modern UI/collage artifacts")
    if _has_unrequested_text_label_reading(lock, joined):
        artifacts.append("unrequested visible text labels")
    return artifacts


def _has_unrequested_text_label_reading(lock: ContentLock, joined: str) -> bool:
    if not re.search(
        r"\b(english|label|labels|text|caption|captions|metadata|acquisition|"
        r"condition report|concept|concepts|speech bubble)\b",
        joined,
    ):
        return False
    if re.search(
        r"\b(english|metadata|acquisition|condition report|concept|concepts|"
        r"speech bubble|sample id|filename)\b",
        joined,
    ):
        return True

    allowed_text_terms = [
        *lock.required_text_elements,
        "cyrillic" if "cyrillic" in lock.original_intent.lower() else "",
        "calligraphy" if "calligraphy" in lock.original_intent.lower() else "",
        "lettering" if "lettering" in lock.original_intent.lower() else "",
    ]
    normalized_allowed = [term.lower() for term in allowed_text_terms if term]
    if normalized_allowed and any(term in joined for term in normalized_allowed):
        return False
    return True


def _replace_known_subjects(subjects: list[str], lower: str) -> list[str]:
    known: list[str] = []
    if re.search(r"\bbamboo\b", lower):
        known.append("bamboo")
    if re.search(r"\borchid grasses?\b", lower):
        known.append("orchid grasses")
    elif re.search(r"\borchids?\b", lower):
        known.append("orchids")
    if known:
        remaining = [
            subject
            for subject in subjects
            if "bamboo" not in subject and "orchid" not in subject
        ]
        return _dedupe([*known, *remaining])
    return subjects


def _build_artifact_boundary_lines(intent: str) -> list[str]:
    lower = intent.lower()
    lines = [
        "ARTIFACT BOUNDARY REQUIREMENT:",
        (
            "The output image must be the artwork itself, not a photograph or "
            "display of the artwork."
        ),
        (
            "Fill the entire canvas with the requested poster/scroll/album/artwork "
            "surface."
        ),
        (
            "Do not include gallery walls, museum displays, framed mockups, "
            "installation views, catalog layouts, UI screens, QR codes, filename "
            "labels, sample IDs, watermarks, or unrequested readable text."
        ),
        "Do not show the artwork as an object in a room.",
    ]
    if re.search(r"\bposter\b|\bpropaganda poster\b", lower):
        lines.append(
            "Render a flat, front-facing propaganda poster artwork that fills the canvas."
        )
        lines.append("Do not render a poster hanging on a wall or photographed in a room.")
    if re.search(r"\bscroll\b|\balbum leaf\b|\balbum-leaf\b", lower):
        lines.append("Render the scroll/album-leaf artwork as the primary image surface.")
        lines.append(
            "Do not render a gallery wall, catalog spread, side-by-side detail mockup, "
            "or framed display."
        )
    return lines


def _extract_keyword_subjects(lower: str) -> list[str]:
    subjects: list[str] = []
    for pattern, label in (
        (r"\blotus blossoms?\b", "lotus blossoms"),
        (r"\bslender stems?\b", "slender stems"),
        (r"\bsmall leaves\b", "small leaves"),
        (r"\bdense tree-like network\b", "dense tree-like network"),
        (r"\bsmall heart\b", "small heart"),
        (r"\bgeometric marks\b", "geometric marks"),
        (r"\bsparse branches\b", "sparse branches"),
        (r"\bworkers?\b", "workers"),
        (r"\bred banners?\b", "red banners"),
    ):
        if re.search(pattern, lower):
            subjects.append(label)
    if re.search(r"\bhand-drawn branching lines\b", lower):
        subjects.append("hand-drawn branching lines")
    elif re.search(r"\bbranching lines\b", lower):
        subjects.append("branching lines")
    if re.search(r"\bfinely detailed bird\b", lower):
        subjects.append("finely detailed bird")
    elif re.search(r"\bsmall bird\b", lower):
        subjects.append("small bird")
    elif re.search(r"\bbird\b", lower):
        subjects.append("bird")
    return _dedupe(subjects)


def _extract_relation_semantics(
    lower: str,
) -> tuple[list[str], list[dict[str, str]], str, list[str]]:
    """Extract conservative subject-relation-object locks from narrative captions."""
    has_mounted_soldiers = bool(
        re.search(r"\bmounted(?:\s+[a-z-]+){0,3}\s+soldiers?\b", lower)
    )
    has_fleeing_civilians = bool(
        re.search(r"\b(?:fleeing|evacuating|displaced)\s+civilians?\b", lower)
        or re.search(r"\bcivilians?\s+(?:as\s+they\s+)?(?:flee|evacuate)\b", lower)
        or re.search(r"\bcivilians?\s+(?:fleeing|evacuating|displaced)\b", lower)
    )
    has_burning_village_ruins = bool(
        re.search(r"\bburning village ruins?\b|\bburning villages?\b", lower)
    )
    has_aircraft_overhead = bool(
        re.search(r"\baircraft overhead\b|\baircraft\b|\bplanes? overhead\b", lower)
    )

    if not (has_mounted_soldiers and has_fleeing_civilians and has_burning_village_ruins):
        return [], [], "", []

    subjects = [
        "mounted soldiers",
        "fleeing civilians",
        "burning village ruins",
    ]
    relations = [
        {
            "subject": "mounted soldiers",
            "relation": "escort/protect",
            "object": "fleeing civilians",
        },
        {
            "subject": "fleeing civilians",
            "relation": "evacuate_from",
            "object": "burning village ruins",
        },
    ]
    composition_intent = (
        "mounted soldiers must read as escort/protect figures for fleeing "
        "civilians while the civilians evacuate from burning village ruins"
    )
    if has_aircraft_overhead:
        subjects.append("aircraft overhead")
        relations.append(
            {
                "subject": "aircraft overhead",
                "relation": "overhead_threat_or_wartime_context",
                "object": "scene",
            }
        )
        composition_intent += (
            " and the aircraft overhead reads as wartime threat/context"
        )

    forbidden_readings = [
        "soldiers chasing civilians",
        "soldiers attacking civilians",
        "civilians threatened by soldiers",
    ]
    return subjects, relations, composition_intent, forbidden_readings


def _format_required_relation(relation: dict[str, str]) -> str:
    subject = relation.get("subject", "").strip()
    predicate = relation.get("relation", "").strip()
    obj = relation.get("object", "").strip()
    if subject and predicate and obj:
        return f"{subject} must read as {predicate} {obj}"
    if subject and predicate:
        return f"{subject} must read as {predicate}"
    return subject or predicate or obj


def _clean_subject(value: str) -> str:
    value = value.strip(" .,:;")
    value = re.sub(r"^(?:a|an|the)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(?:delicate|detailed|high-quality)\s+", "", value, flags=re.IGNORECASE)
    return " ".join(value.split())


def _as_string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _as_relation_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, (list, tuple)):
        return []
    relations: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or "").strip()
        relation = str(item.get("relation") or "").strip()
        obj = str(item.get("object") or "").strip()
        if not (subject and relation and obj):
            continue
        relations.append({"subject": subject, "relation": relation, "object": obj})
    return relations


def _as_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _relation_reading_matches(reading: str, joined: str) -> bool:
    normalized = reading.lower()
    has_soldiers = "soldier" in joined or "rider" in joined or "mounted" in joined
    has_civilians = "civilian" in joined or "people" in joined or "refugee" in joined
    if "chasing" in normalized:
        return has_soldiers and has_civilians and re.search(r"\bchas\w*|\bpursu\w*", joined) is not None
    if "attacking" in normalized:
        return has_soldiers and has_civilians and re.search(r"\battack\w*|\bassault\w*|\bshoot\w*", joined) is not None
    if "threatened" in normalized:
        return has_soldiers and has_civilians and re.search(
            r"\bthreat\w*|\bmenac\w*|\bbrandish\w*|\bdrawn\s+swords?\b|"
            r"\bcharge\w*\b|\bweapon\w*",
            joined,
        ) is not None
    return reading.lower() in joined


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
