from __future__ import annotations

from vulca.content_lock import (
    ContentLock,
    apply_content_fidelity_gate,
    build_blind_relation_gate,
    build_blind_relation_read_prompt,
    build_content_fidelity_gate,
    build_content_fidelity_prompt,
    build_content_lock_prompt,
    extract_content_lock,
)


def test_extracts_required_subjects_and_attributes_from_caption():
    lock = extract_content_lock(
        "Ink and wash painting of delicate bamboo and orchid grasses beside "
        "vertical Chinese calligraphy and red seals on aged paper, with sparse "
        "brushwork and a calm scholarly composition."
    )

    assert lock.required_subjects == ["bamboo", "orchid grasses"]
    assert lock.required_text_elements == ["vertical Chinese calligraphy", "red seals"]
    assert lock.required_surface == ["aged paper"]
    assert "sparse brushwork" in lock.required_style_attributes
    assert "calm scholarly composition" in lock.required_mood


def test_extracts_generic_required_subjects_from_caption():
    lock = extract_content_lock(
        "Editorial illustration of a silver astronaut, cracked moon rover, and "
        "orange emergency flare under a black sky."
    )

    assert lock.required_subjects == [
        "silver astronaut",
        "cracked moon rover",
        "orange emergency flare",
    ]


def test_extracts_declarative_graph_paper_branching_caption():
    lock = extract_content_lock(
        "Abstract hand-drawn branching lines fill a rectangular frame on graph "
        "paper, forming a dense tree-like network with a small heart and "
        "geometric marks in monochrome pencil style."
    )

    assert "hand-drawn branching lines" in lock.required_subjects
    assert "dense tree-like network" in lock.required_subjects
    assert "small heart" in lock.required_subjects
    assert "geometric marks" in lock.required_subjects
    assert lock.required_surface == ["graph paper"]
    assert "rectangular frame" in lock.required_style_attributes
    assert "monochrome pencil style" in lock.required_style_attributes


def test_extracts_gongbi_album_leaf_subjects_and_format():
    lock = extract_content_lock(
        "Gongbi album leaf with a small bird perched beside sparse branches, "
        "a circular calligraphy panel, and an ornate pale patterned border."
    )

    assert "small bird" in lock.required_subjects
    assert "sparse branches" in lock.required_subjects
    assert "circular calligraphy panel" in lock.required_text_elements
    assert "ornate pale patterned border" in lock.required_surface
    assert "Gongbi album leaf" in lock.required_style_attributes


def test_extracts_relation_semantics_for_escort_evacuation_caption():
    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    assert "mounted soldiers" in lock.required_subjects
    assert "fleeing civilians" in lock.required_subjects
    assert "burning village ruins" in lock.required_subjects
    assert "aircraft overhead" in lock.required_subjects
    assert lock.required_relations == [
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
        {
            "subject": "aircraft overhead",
            "relation": "overhead_threat_or_wartime_context",
            "object": "scene",
        },
    ]
    assert "soldiers chasing civilians" in lock.forbidden_readings
    assert "escort/protect" in lock.composition_intent


def test_extracts_relation_semantics_with_modifier_between_mounted_and_soldiers():
    lock = extract_content_lock(
        "A Socialist Realism poster with mounted Soviet soldiers escorting and "
        "protecting civilians as they flee burning village ruins, aircraft overhead."
    )

    assert "mounted soldiers" in lock.required_subjects
    assert "fleeing civilians" in lock.required_subjects
    assert "aircraft overhead" in lock.required_subjects
    assert lock.required_relations[0] == {
        "subject": "mounted soldiers",
        "relation": "escort/protect",
        "object": "fleeing civilians",
    }
    assert "soldiers chasing civilians" in lock.forbidden_readings


def test_content_lock_prompt_makes_subjects_non_negotiable():
    lock = extract_content_lock(
        "Ink and wash painting of delicate bamboo and orchid grasses beside "
        "vertical Chinese calligraphy and red seals on aged paper."
    )

    prompt = build_content_lock_prompt(lock)

    assert "NON-NEGOTIABLE CONTENT REQUIREMENTS" in prompt
    assert "bamboo" in prompt
    assert "orchid grasses" in prompt
    assert "vertical Chinese calligraphy" in prompt
    assert "red seals" in prompt
    assert (
        "Do not replace these subjects with mountains, generic landscapes, "
        "or unrelated tradition prototypes."
    ) in prompt


def test_content_lock_prompt_bans_visible_ids_and_gallery_artifacts():
    lock = extract_content_lock(
        "Abstract hand-drawn branching lines fill a rectangular frame on graph "
        "paper in monochrome pencil style."
    )

    prompt = build_content_lock_prompt(lock)

    assert "sample IDs" in prompt
    assert "gallery" in prompt.lower()
    assert "large labels" in prompt


def test_content_lock_prompt_makes_relations_non_negotiable():
    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    prompt = build_content_lock_prompt(lock)

    assert "RELATION SEMANTICS REQUIREMENTS" in prompt
    assert "mounted soldiers must read as escort/protect fleeing civilians" in prompt
    assert "fleeing civilians must read as evacuate_from burning village ruins" in prompt
    assert "COMPOSITION INTENT" in prompt
    assert "FORBIDDEN RELATION READINGS" in prompt
    assert "soldiers chasing civilians" in prompt


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


def test_blind_relation_gate_rejects_weapon_threat_to_civilians():
    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    gate = build_blind_relation_gate(
        lock,
        {
            "primary_reading": (
                "Soldiers on horseback charge forward with drawn swords past "
                "fleeing civilians."
            ),
            "apparent_relations": [
                "soldiers brandish swords",
                "civilians flee from fire",
            ],
            "ambiguous_readings": [],
        },
    )

    assert gate["blind_relation_decision"] == "reject"
    assert "civilians threatened by soldiers" in gate[
        "blind_forbidden_readings_present"
    ]


def test_blind_relation_gate_rejects_weapon_threat_even_with_ambiguity():
    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    gate = build_blind_relation_gate(
        lock,
        {
            "primary_reading": (
                "Soldiers on horseback charge forward with drawn swords past "
                "fleeing civilians."
            ),
            "apparent_relations": [
                "soldiers brandish swords",
                "civilians flee from fire",
            ],
            "ambiguous_readings": [
                "soldiers could be arriving to defend or passing through"
            ],
        },
    )

    assert gate["blind_relation_decision"] == "reject"
    assert "civilians threatened by soldiers" in gate[
        "blind_forbidden_readings_present"
    ]


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
            "primary_reading": (
                "Mounted soldiers flank civilians and guide them away from burning ruins."
            ),
            "apparent_relations": [
                "mounted soldiers guiding civilians away from burning ruins"
            ],
            "ambiguous_readings": [],
        },
    )

    assert gate["blind_relation_decision"] == "pass"


def test_artifact_boundary_prompt_for_poster_requires_flat_artwork_surface():
    lock = ContentLock(
        original_intent="Socialist Realism propaganda poster with workers and red banners.",
        output_is_artwork_itself=True,
    )

    prompt = build_content_lock_prompt(lock)

    assert "ARTIFACT BOUNDARY REQUIREMENT" in prompt
    assert "artwork itself" in prompt
    assert "flat, front-facing propaganda poster artwork" in prompt
    assert "poster hanging on a wall" in prompt


def test_artifact_boundary_prompt_for_scroll_rejects_catalog_displays():
    lock = ContentLock(
        original_intent="A Gongbi vertical hanging scroll with lotus blossoms.",
        output_is_artwork_itself=True,
    )

    prompt = build_content_lock_prompt(lock)

    assert "scroll/album-leaf artwork as the primary image surface" in prompt
    assert "catalog spread" in prompt
    assert "framed display" in prompt


def test_content_fidelity_prompt_requests_missing_elements():
    lock = extract_content_lock(
        "Ink and wash painting of bamboo beside vertical Chinese calligraphy."
    )

    prompt = build_content_fidelity_prompt(lock)

    assert "CONTENT FIDELITY CHECK" in prompt
    assert "missing_required_subjects" in prompt
    assert "missing_required_text_elements" in prompt
    assert "bamboo" in prompt
    assert "vertical Chinese calligraphy" in prompt
    assert "forbidden_visual_artifacts" in prompt
    assert "output_is_artwork_itself" in prompt
    assert "unwanted_visible_text" in prompt


def test_content_fidelity_prompt_requests_relation_semantics_fields():
    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    prompt = build_content_fidelity_prompt(lock)

    assert "Required relations" in prompt
    assert "Forbidden relation readings" in prompt
    assert "apparent_relations" in prompt
    assert "relation_semantics_failed" in prompt
    assert "forbidden_readings_present" in prompt


def test_content_fidelity_prompt_requests_missing_style_attributes():
    lock = extract_content_lock(
        "Abstract hand-drawn branching lines fill a rectangular frame on graph "
        "paper in monochrome pencil style."
    )

    prompt = build_content_fidelity_prompt(lock)

    assert "missing_required_style_attributes" in prompt
    assert "rectangular frame" in prompt
    assert "monochrome pencil style" in prompt


def test_missing_required_subject_caps_high_score():
    result = {
        "scores": {"L1": 0.95, "L2": 0.92, "L3": 1.0, "L4": 1.0, "L5": 0.94},
        "weighted_total": 0.965,
        "rationales": {},
    }
    gate = {
        "required_subjects": ["bamboo", "orchid grasses"],
        "missing_required_subjects": ["bamboo", "orchid grasses"],
    }

    gated = apply_content_fidelity_gate(result, gate)

    assert gated["weighted_total"] == 0.25
    assert gated["scores"]["L3"] <= 0.25
    assert "content_fidelity_failed" in gated["risk_flags"]
    assert (
        "Missing required subjects: bamboo, orchid grasses"
        in gated["rationales"]["content_fidelity"]
    )


def test_missing_required_text_element_caps_high_score():
    result = {
        "scores": {"L1": 0.95, "L2": 0.92, "L3": 1.0, "L4": 1.0, "L5": 0.94},
        "weighted_total": 0.965,
        "rationales": {},
    }
    gate = {
        "required_text_elements": ["vertical Chinese calligraphy"],
        "missing_required_text_elements": ["vertical Chinese calligraphy"],
    }

    gated = apply_content_fidelity_gate(result, gate)

    assert gated["weighted_total"] == 0.25
    assert "content_fidelity_failed" in gated["risk_flags"]
    assert "Missing required text elements" in gated["rationales"]["content_fidelity"]


def test_missing_required_style_attribute_caps_high_score():
    result = {
        "scores": {"L1": 0.95, "L2": 0.92, "L3": 1.0, "L4": 1.0, "L5": 0.94},
        "weighted_total": 0.965,
        "rationales": {},
    }
    gate = {
        "required_style_attributes": ["monochrome pencil style"],
        "missing_required_style_attributes": ["monochrome pencil style"],
    }

    gated = apply_content_fidelity_gate(result, gate)

    assert gated["weighted_total"] == 0.25
    assert "content_fidelity_failed" in gated["risk_flags"]
    assert "Missing required style attributes" in gated["rationales"]["content_fidelity"]


def test_forbidden_visual_artifact_caps_high_score():
    result = {
        "scores": {"L1": 0.95, "L2": 0.92, "L3": 1.0, "L4": 1.0, "L5": 0.94},
        "weighted_total": 0.965,
        "rationales": {},
    }
    gate = {
        "forbidden_visual_artifacts": ["visible sample ID", "gallery photo mockup"],
    }

    gated = apply_content_fidelity_gate(result, gate)

    assert gated["weighted_total"] == 0.25
    assert "content_fidelity_failed" in gated["risk_flags"]
    assert "Forbidden visual artifacts" in gated["rationales"]["content_fidelity"]


def test_artifact_boundary_violation_caps_high_score():
    result = {
        "scores": {"L1": 0.95, "L2": 0.92, "L3": 1.0, "L4": 1.0, "L5": 0.94},
        "weighted_total": 0.965,
        "rationales": {},
    }
    gate = {
        "required_output_is_artwork_itself": True,
        "output_is_artwork_itself": False,
        "unwanted_visible_text": True,
    }

    gated = apply_content_fidelity_gate(result, gate)

    assert gated["weighted_total"] == 0.25
    assert "content_fidelity_failed" in gated["risk_flags"]
    assert "Output is not the artwork itself" in gated["rationales"]["content_fidelity"]
    assert "Unwanted visible text" in gated["rationales"]["content_fidelity"]


def test_content_fidelity_gate_reads_artifact_boundary_fields():
    lock = ContentLock(
        original_intent="Graph-paper branching pencil drawing.",
        output_is_artwork_itself=True,
    )

    gate = build_content_fidelity_gate(
        lock,
        {
            "forbidden_visual_artifacts": ["gallery wall"],
            "unwanted_visible_text": True,
            "output_is_artwork_itself": False,
        },
    )

    assert gate["required_output_is_artwork_itself"] is True
    assert gate["output_is_artwork_itself"] is False
    assert gate["unwanted_visible_text"] is True
    assert gate["forbidden_visual_artifacts"] == ["gallery wall"]


def test_content_fidelity_gate_infers_modern_ui_text_artifacts():
    lock = extract_content_lock(
        "A Socialist Realism propaganda poster of a triumphant armored rider "
        "on horseback beside Soviet soldiers with rifles, fallen enemies in "
        "the foreground, and a fortified city rising in the background under "
        "bold Cyrillic lettering."
    )

    gate = build_content_fidelity_gate(
        lock,
        {
            "apparent_relations": [
                "rider-leads-soldiers",
                "memes-overlay-history",
                "text-labels-concepts",
                "social icons frame the city",
            ],
            "forbidden_visual_artifacts": [],
            "unwanted_visible_text": False,
            "output_is_artwork_itself": True,
        },
    )

    assert gate["unwanted_visible_text"] is True
    assert "modern UI/collage artifacts" in gate["forbidden_visual_artifacts"]
    assert "unrequested visible text labels" in gate["forbidden_visual_artifacts"]


def test_content_fidelity_gate_rejects_english_labels_even_with_allowed_cyrillic():
    lock = extract_content_lock(
        "A Socialist Realism propaganda poster of a triumphant armored rider "
        "under bold Cyrillic lettering."
    )

    gate = build_content_fidelity_gate(
        lock,
        {
            "apparent_relations": [
                "bold Cyrillic headline spans the poster",
                "English text labels explain concepts in the city",
            ],
            "forbidden_visual_artifacts": [],
            "unwanted_visible_text": False,
            "output_is_artwork_itself": True,
        },
    )

    assert gate["unwanted_visible_text"] is True
    assert "unrequested visible text labels" in gate["forbidden_visual_artifacts"]


def test_content_fidelity_gate_reads_relation_semantics_fields():
    lock = extract_content_lock(
        "Wartime illustration of mounted soldiers beside fleeing civilians, "
        "burning village ruins, and aircraft overhead."
    )

    gate = build_content_fidelity_gate(
        lock,
        {
            "apparent_relations": ["mounted soldiers appear to chase civilians"],
            "relation_semantics_failed": True,
            "forbidden_readings_present": ["soldiers chasing civilians"],
        },
    )

    assert gate["required_relations"] == lock.required_relations
    assert gate["apparent_relations"] == ["mounted soldiers appear to chase civilians"]
    assert gate["relation_semantics_failed"] is True
    assert gate["forbidden_readings"] == lock.forbidden_readings
    assert gate["forbidden_readings_present"] == ["soldiers chasing civilians"]


def test_relation_semantics_failure_caps_high_score():
    result = {
        "scores": {"L1": 0.95, "L2": 0.92, "L3": 1.0, "L4": 1.0, "L5": 0.94},
        "weighted_total": 0.965,
        "rationales": {},
    }
    gate = {
        "required_relations": [
            {
                "subject": "mounted soldiers",
                "relation": "escort/protect",
                "object": "fleeing civilians",
            }
        ],
        "relation_semantics_failed": True,
        "forbidden_readings_present": ["soldiers chasing civilians"],
    }

    gated = apply_content_fidelity_gate(result, gate)

    assert gated["weighted_total"] == 0.25
    assert gated["scores"]["L4"] <= 0.25
    assert "content_fidelity_failed" in gated["risk_flags"]
    assert "Relation semantics failed" in gated["rationales"]["content_fidelity"]
    assert "Forbidden relation readings: soldiers chasing civilians" in gated["rationales"]["content_fidelity"]


def test_blind_relation_reject_caps_high_score():
    result = {
        "scores": {"L1": 0.95, "L2": 0.92, "L3": 1.0, "L4": 1.0, "L5": 0.94},
        "weighted_total": 0.965,
        "rationales": {},
    }
    gate = {
        "blind_relation_decision": "reject",
        "blind_relation_reason": "blind read matches forbidden relation reading",
        "blind_forbidden_readings_present": ["soldiers chasing civilians"],
        "blind_primary_reading": "Mounted soldiers appear to chase civilians.",
    }

    gated = apply_content_fidelity_gate(result, gate)

    assert gated["weighted_total"] == 0.25
    assert (
        "Blind relation gate rejected image"
        in gated["rationales"]["content_fidelity"]
    )
    assert "content_fidelity_failed" in gated["risk_flags"]


def test_present_required_subjects_do_not_cap_score():
    result = {
        "scores": {"L1": 0.95, "L2": 0.92, "L3": 1.0, "L4": 1.0, "L5": 0.94},
        "weighted_total": 0.965,
        "rationales": {},
    }
    gate = {
        "required_subjects": ["bamboo", "orchid grasses"],
        "missing_required_subjects": [],
    }

    gated = apply_content_fidelity_gate(result, gate)

    assert gated["weighted_total"] == 0.965
    assert gated["scores"]["L3"] == 1.0
    assert gated.get("risk_flags", []) == []
