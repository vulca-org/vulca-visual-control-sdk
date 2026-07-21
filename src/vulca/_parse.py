"""Robust JSON parsing for LLM outputs."""

from __future__ import annotations

import json
import re


def parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM output, handling common formatting issues.

    Handles: markdown fences, trailing commas, single quotes,
    comments, and other non-standard JSON from LLMs.
    """
    # Strip markdown code fences
    if "```" in text:
        # Extract content between fences
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    # Try standard parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fix trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Fix a rare LLM typo where a key starts with two double quotes:
    #   { "L5": 0.7, ""missing_required_subjects": [] }
    text = re.sub(r'([,{]\s*)""([A-Za-z_][A-Za-z0-9_]*"\s*:)', r'\1"\2', text)

    # Fix single quotes → double quotes (careful with apostrophes in text)
    # Only replace quotes that look like JSON keys/values
    text = re.sub(r"(?<=[\[{,:])\s*'([^']*?)'\s*(?=[,}\]:])", r' "\1"', text)

    # Remove inline comments
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)

    # Try again
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Last resort: find the first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidate = match.group(0)
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Last resort 2: some local models (Gemma-class) emit each dimension in
    # its own {...} block, separated by commas, either entirely:
    #     { "L1": 0.9, ... }, { "L2": 0.8, ... }, { "risk_flags": [] }
    # or in a hybrid shape where the outer {} wraps 5 pseudo-objects plus a
    # bare trailing key:
    #     { { "L1": 0.9, ... }, { "L2": 0.8, ... }, ..., "risk_flags": [] }
    # Collapsing `},{` → `,` turns both forms into a single flat object that
    # ``json.loads`` will accept.
    try:
        flat = text.strip()
        # 1. Collapse `},{` boundaries between pseudo-objects.
        flat = re.sub(r"\}\s*,\s*\{", ",", flat)
        # 2. Collapse `},"key":` (dimension object immediately followed by a
        #    bare trailing key like risk_flags) into `,"key":`.
        flat = re.sub(r'\}\s*,\s*(")', r",\1", flat)
        # 3. Drop stray trailing commas that would otherwise sink the parse.
        flat = re.sub(r",\s*([}\]])", r"\1", flat)
        # 4. Restore outer braces if the collapse ate them entirely.
        if not flat.startswith("{"):
            flat = "{" + flat
        if not flat.rstrip().endswith("}"):
            flat = flat.rstrip() + "}"
        return json.loads(flat)
    except json.JSONDecodeError:
        pass

    # Last resort 3: fall back to array wrap + merge, in case the collapse
    # above misfired on a genuinely-array-shaped payload.
    try:
        array_text = "[" + text.strip() + "]"
        array_text = re.sub(r",\s*([}\]])", r"\1", array_text)
        items = json.loads(array_text)
        if isinstance(items, list) and items and all(isinstance(x, dict) for x in items):
            merged: dict = {}
            for x in items:
                merged.update(x)
            return merged
    except json.JSONDecodeError:
        pass

    raise ValueError(f"Could not parse JSON from LLM output: {text[:200]}...")
