"""VULCA command-line interface.

Usage::

    vulca evaluate painting.jpg
    vulca evaluate painting.jpg --tradition chinese_xieyi --mode reference
    vulca evaluate painting.jpg -t chinese_xieyi,ukiyoe --mode fusion
    vulca create "水墨山水" --hitl --mode reference
    vulca create "水墨山水" --weights "L1=0.3,L2=0.2,L3=0.2,L4=0.15,L5=0.15"
    vulca tradition --init my_style > my_tradition.yaml
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from vulca._version import __version__

_VALID_MODES = ("strict", "reference", "fusion")

_DIM_NAMES = {
    "L1": "Visual Perception",
    "L2": "Technical Execution",
    "L3": "Cultural Context",
    "L4": "Critical Interpretation",
    "L5": "Philosophical Aesthetics",
}

_DEVIATION_LABELS = {
    "traditional": "traditional",
    "intentional_departure": "intentional departure",
    "experimental": "experimental",
}


def _parse_weights(raw: str) -> dict[str, float]:
    """Parse "L1=0.3,L2=0.2,..." into a weights dict.

    Accepts formats:
        "L1=0.3,L2=0.2,L3=0.2,L4=0.15,L5=0.15"
        "L1=0.3, L2=0.2, L3=0.2, L4=0.15, L5=0.15"
    """
    weights: dict[str, float] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(f"Invalid weight format: {pair!r}. Expected 'L1=0.3'.")
        key, val = pair.split("=", 1)
        key = key.strip().upper()
        if key not in ("L1", "L2", "L3", "L4", "L5"):
            raise ValueError(f"Unknown dimension: {key!r}. Expected L1-L5.")
        weights[key] = float(val.strip())
    return weights


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="vulca",
        description="VULCA -- AI-native cultural art advisor",
    )
    parser.add_argument("--version", action="version", version=f"vulca {__version__}")

    sub = parser.add_subparsers(dest="command")

    # evaluate command
    eval_p = sub.add_parser("evaluate", aliases=["eval", "e"], help="Evaluate an artwork")
    eval_p.add_argument("image", help="Image file path or URL")
    eval_p.add_argument("--intent", "-i", default="", help="Natural language evaluation intent")
    eval_p.add_argument("--tradition", "-t", default="", help="Cultural tradition or path to custom YAML")
    eval_p.add_argument("--subject", "-s", default="", help="Artwork subject/title")
    eval_p.add_argument("--mode", "-m", default="strict", choices=_VALID_MODES,
                        help="Evaluation mode: strict (judge), reference (advisor), fusion (multi-tradition)")
    eval_p.add_argument("--skills", default="", help="Comma-separated extra skills: brand,audience,trend")
    eval_p.add_argument("--json", action="store_true", help="Output raw JSON")
    eval_p.add_argument("--api-key", default="", help="Google API key (or set GOOGLE_API_KEY)")
    eval_p.add_argument("--mock", action="store_true", help="Use mock scoring (no API key required)")
    eval_p.add_argument("--vlm-model", default="", help="VLM model (LiteLLM format, e.g. ollama/llava)")
    eval_p.add_argument("--vlm-base-url", default="", help="VLM base URL (for local models)")
    eval_p.add_argument("--reference", default="", help="Reference image path or base64 for comparison")

    # create command
    create_p = sub.add_parser("create", aliases=["c"], help="Create artwork via pipeline")
    create_p.add_argument("intent", help="Natural language creation intent")
    create_p.add_argument("--tradition", "-t", default="", help="Cultural tradition or path to custom YAML")
    create_p.add_argument("--subject", "-s", default="", help="Artwork subject/title")
    create_p.add_argument("--provider", default="nb2", help="Image generation provider")
    create_p.add_argument("--mode", "-m", default="strict", choices=_VALID_MODES,
                          help="Evaluation mode: strict (judge), reference (advisor)")
    create_p.add_argument("--json", action="store_true", help="Output raw JSON")
    create_p.add_argument("--api-key", default="", help="VULCA API key (or set VULCA_API_KEY)")
    create_p.add_argument("--base-url", default="", help="VULCA API base URL")
    create_p.add_argument("--hitl", action="store_true", help="Enable human-in-the-loop (pause before decide)")
    create_p.add_argument("--layered", action="store_true", help="Generate structured layers (Artifact V3)")
    create_p.add_argument("--no-cache", action="store_true", help="Disable layered cache (forces re-generation)")
    create_p.add_argument("--strict", action="store_true", help="Layered mode: any failed layer fails the run")
    create_p.add_argument("--max-layers", type=int, default=8, help="Cap the number of layers (default 8, range 1..20)")
    create_p.add_argument("--weights", default="", help="Custom L1-L5 weights: 'L1=0.3,L2=0.2,...'")
    create_p.add_argument("--image-provider", default="", help="Image provider: mock|gemini|openai|comfyui")
    create_p.add_argument("--image-base-url", default="", help="Image provider base URL (for comfyui)")
    create_p.add_argument("--reference", default="", help="Reference image path or base64 (also serves as sketch input)")
    create_p.add_argument("--ref-type", default="full", choices=["style", "composition", "full"],
                          help="Reference type: style, composition, or full")
    create_p.add_argument("--colors", default="", help="Hex color palette (comma-separated, e.g. '#C87F4A,#5F8A50')")
    create_p.add_argument(
        "--content-lock",
        action="store_true",
        help="Treat explicit subjects and visible attributes in the intent as non-negotiable constraints",
    )
    create_p.add_argument(
        "--output-is-artwork-itself",
        action="store_true",
        help="Require the output to be the artwork surface itself, not a gallery/photo/mockup display",
    )
    create_p.add_argument("--output", "-o", default="", help="Save generated image to this path (default: ./vulca-<session>.png)")

    # traditions command
    sub.add_parser("traditions", aliases=["t"], help="List available cultural traditions")

    # tradition detail command
    trad_p = sub.add_parser("tradition", aliases=["td"], help="Get cultural tradition guide")
    trad_p.add_argument("name", nargs="?", default="", help="Tradition name (e.g. chinese_xieyi)")
    trad_p.add_argument("--init", default="", metavar="NAME", help="Generate a template YAML for a custom tradition")
    trad_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # evolution status command
    evo_p = sub.add_parser("evolution", aliases=["evo"], help="Get evolution status for a tradition")
    evo_p.add_argument("name", help="Tradition name")
    evo_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # Studio commands
    studio_parser = sub.add_parser("studio", help="Run interactive Studio session")
    studio_parser.add_argument("intent_or_dir", help="Creative intent or project dir (with --resume)")
    studio_parser.add_argument("--provider", "-p", default="mock", help="Image provider")
    studio_parser.add_argument("--count", "-n", type=int, default=4, help="Number of concepts")
    studio_parser.add_argument("--resume", action="store_true", help="Resume from saved session")
    studio_parser.add_argument("--auto", action="store_true", help="Non-interactive: skip prompts, auto-accept")
    studio_parser.add_argument("--max-rounds", type=int, default=3, help="Max rounds in auto mode (default 3)")
    studio_parser.add_argument("--api-key", default="", help="API key")

    brief_parser = sub.add_parser("brief", help="Create or show a Studio Brief")
    brief_parser.add_argument("project_dir", help="Project directory")
    brief_parser.add_argument("--intent", "-i", default="", help="Creative intent")
    brief_parser.add_argument("--mood", "-m", default="", help="Mood/atmosphere")

    brief_update_parser = sub.add_parser("brief-update", help="Update Brief with NL instruction")
    brief_update_parser.add_argument("project_dir", help="Project directory")
    brief_update_parser.add_argument("instruction", help="Natural language update")

    concept_parser = sub.add_parser("concept", help="Generate or select concepts")
    concept_parser.add_argument("project_dir", help="Project directory")
    concept_parser.add_argument("--count", "-n", type=int, default=4, help="Number of concepts")
    concept_parser.add_argument("--provider", "-p", default="mock", help="Image provider")
    concept_parser.add_argument("--select", "-s", type=int, default=None, help="Select concept (1-based)")
    concept_parser.add_argument("--notes", default="", help="Notes for selection")

    # sync command
    sync_parser = sub.add_parser("sync", help="Sync local session data with cloud")
    sync_parser.add_argument("--push-only", action="store_true", help="Only push local data")
    sync_parser.add_argument("--pull-only", action="store_true", help="Only pull evolved weights")

    # telemetry command
    telemetry_parser = sub.add_parser("telemetry", help="Inspect or change opt-in telemetry settings")
    telemetry_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    telemetry_sub = telemetry_parser.add_subparsers(dest="telemetry_command")
    telemetry_sub.add_parser("status", help="Show telemetry status")
    telemetry_sub.add_parser("enable", help="Enable local opt-in telemetry")
    telemetry_sub.add_parser("disable", help="Disable local opt-in telemetry")
    telemetry_sub.add_parser("reset-id", help="Reset the anonymous install id")

    # inpaint command
    inpaint_p = sub.add_parser("inpaint", help="Repaint a region of an artwork")
    inpaint_p.add_argument("image", help="Path to image")
    inpaint_p.add_argument("--region", required=True, help="Region: NL description or 'x,y,w,h' coordinates (%%)")
    inpaint_p.add_argument("--instruction", required=True, help="What to change in the region")
    inpaint_p.add_argument("--tradition", "-t", default="default", help="Cultural tradition")
    inpaint_p.add_argument("--count", "-n", type=int, default=4, help="Number of variants")
    inpaint_p.add_argument("--select", "-s", type=int, default=None, help="Auto-select variant (1-based)")
    inpaint_p.add_argument("--output", "-o", default="", help="Output path")
    inpaint_p.add_argument(
        "--provider", "-p", default="gemini",
        choices=("gemini", "openai", "comfyui"),
        help="Image provider",
    )
    inpaint_p.add_argument("--mock", action="store_true", help="Use mock mode")

    # layers command group
    layers_p = sub.add_parser("layers", help="Layered artwork analysis, editing, and export")
    layers_sub = layers_p.add_subparsers(dest="layers_command")

    layers_analyze = layers_sub.add_parser("analyze", help="Analyze image into semantic layers")
    layers_analyze.add_argument("image", help="Path to image")

    layers_split = layers_sub.add_parser("split", help="Split image into layer PNGs")
    layers_split.add_argument("image", help="Path to image")
    layers_split.add_argument("--output", "-o", default="", help="Output directory")
    layers_split.add_argument("--mode", "-m", default="regenerate",
                              choices=["regenerate", "extract", "sam", "vlm", "palette", "sam3"],
                              help="Split mode: regenerate | extract | sam | vlm | palette | sam3 (needs vulca[sam3] + GPU)")
    layers_split.add_argument("--provider", "-p", default="gemini", help="Image provider (regenerate mode)")
    layers_split.add_argument("--tradition", "-t", default="default", help="Cultural tradition")
    layers_split.add_argument(
        "--case-log",
        default="",
        help=(
            "Append a Learning Loop decompose_case JSONL record to this path. "
            "If omitted, VULCA_DECOMPOSE_CASE_LOG can enable logging."
        ),
    )

    layers_redraw = layers_sub.add_parser("redraw", help="Redraw layer(s) via img2img")
    layers_redraw.add_argument("artwork_dir", help="Directory with layers")
    layers_redraw.add_argument("--layer", help="Single layer name to redraw")
    layers_redraw.add_argument("--layers", help="Comma-separated layer names to merge+redraw")
    layers_redraw.add_argument("--instruction", "-i", required=True, help="Redraw instruction")
    layers_redraw.add_argument("--merge", action="store_true", help="Merge selected layers before redraw")
    layers_redraw.add_argument("--merged-name", default="merged", help="Name for merged output layer")
    layers_redraw.add_argument("--provider", "-p", default="gemini", help="Image provider")
    layers_redraw.add_argument("--tradition", "-t", default="default", help="Cultural tradition")
    layers_redraw.add_argument("--re-split", action="store_true",
                               help="After merge+redraw, re-analyze and split back")
    layers_redraw.add_argument(
        "--case-log",
        default="",
        help=(
            "Append a Learning Loop v0 redraw case JSONL record to this path. "
            "If omitted, VULCA_REDRAW_CASE_LOG can enable logging."
        ),
    )

    layers_composite = layers_sub.add_parser("composite", help="Composite layers into flat image")
    layers_composite.add_argument("artwork_dir", help="Directory with layer PNGs + manifest")
    layers_composite.add_argument("--output", "-o", default="", help="Output path")

    layers_export = layers_sub.add_parser("export", help="Export layers as PSD/PNG")
    layers_export.add_argument("artwork_dir", help="Directory with layers")
    layers_export.add_argument("--format", "-f", default="png", choices=["png", "psd"])
    layers_export.add_argument("--output", "-o", default="", help="Output path")

    layers_regen = layers_sub.add_parser("regenerate", help="Regenerate unified image from composite")
    layers_regen.add_argument("artwork_dir", help="Directory with composite + layers")
    layers_regen.add_argument("--tradition", "-t", default="default")
    layers_regen.add_argument("--provider", "-p", default="gemini")

    layers_eval = layers_sub.add_parser("evaluate", help="Per-layer L1-L5 evaluation")
    layers_eval.add_argument("artwork_dir", help="Directory with layers")
    layers_eval.add_argument("--tradition", "-t", default="default")

    # P2 layer editing subcommands
    layers_add = layers_sub.add_parser("add", help="Add new transparent layer")
    layers_add.add_argument("artwork_dir", help="Directory with layers")
    layers_add.add_argument("--name", "-n", required=True, help="Layer name")
    layers_add.add_argument("--description", "-d", default="", help="Layer description")
    layers_add.add_argument("--z-index", type=int, default=-1, help="Z-index (-1 = top)")
    layers_add.add_argument("--content-type", default="subject",
                            help="Layer role label (e.g. background, subject, ui_header, decoration)")
    layers_add.add_argument(
        "--semantic-path",
        default="",
        help="Hierarchical dot-notation label, e.g. 'subject.face.eyes' or 'person[0].hair'",
    )

    layers_remove = layers_sub.add_parser("remove", help="Remove a layer")
    layers_remove.add_argument("artwork_dir", help="Directory with layers")
    layers_remove.add_argument("--layer", "-l", required=True, help="Layer name to remove")

    layers_reorder = layers_sub.add_parser("reorder", help="Change layer z-index")
    layers_reorder.add_argument("artwork_dir", help="Directory with layers")
    layers_reorder.add_argument("--layer", "-l", required=True, help="Layer name")
    layers_reorder.add_argument("--z-index", type=int, required=True, help="New z-index")

    layers_toggle = layers_sub.add_parser("toggle", help="Toggle layer visibility")
    layers_toggle.add_argument("artwork_dir", help="Directory with layers")
    layers_toggle.add_argument("--layer", "-l", required=True, help="Layer name")
    layers_toggle.add_argument("--visible", required=True, help="true or false")

    layers_lock_p = layers_sub.add_parser("lock", help="Lock/unlock a layer")
    layers_lock_p.add_argument("artwork_dir", help="Directory with layers")
    layers_lock_p.add_argument("--layer", "-l", required=True, help="Layer name")
    layers_lock_p.add_argument("--locked", default="true", help="true or false (default: true)")

    layers_merge = layers_sub.add_parser("merge", help="Merge layers into one")
    layers_merge.add_argument("artwork_dir", help="Directory with layers")
    layers_merge.add_argument("--layers", required=True, help="Comma-separated layer names")
    layers_merge.add_argument("--name", "-n", default="merged", help="Merged layer name")

    layers_dup = layers_sub.add_parser("duplicate", help="Duplicate a layer")
    layers_dup.add_argument("artwork_dir", help="Directory with layers")
    layers_dup.add_argument("--layer", "-l", required=True, help="Source layer name")
    layers_dup.add_argument("--name", "-n", default="", help="New layer name")

    layers_cache = layers_sub.add_parser("cache", help="Layered cache management")
    layers_cache_sub = layers_cache.add_subparsers(dest="cache_cmd")
    layers_cache_clear = layers_cache_sub.add_parser("clear", help="Delete .layered_cache/")
    layers_cache_clear.add_argument("artifact_dir", help="Path to the artifact directory")

    layers_retry = layers_sub.add_parser("retry", help="Retry failed layers in a layered artifact")
    layers_retry.add_argument("artifact_dir", help="Path to the artifact directory")
    layers_retry.add_argument("--layer", default="", help="Retry only this layer name")
    layers_retry.add_argument("--all-failed", action="store_true", help="Retry every failed layer")
    layers_retry.add_argument(
        "--tradition", "-t", default="",
        help=("Tradition to re-derive anchor/canvas/keying from. "
              "If omitted, reads from manifest.json[tradition] (recommended). "
              "Passing a value that disagrees with the manifest will error."),
    )
    layers_retry.add_argument("--provider", default="", help="Image provider override")

    layers_transform = layers_sub.add_parser("transform", help="Move/scale/rotate/opacity a layer")
    layers_transform.add_argument("artwork_dir", help="Directory with layers")
    layers_transform.add_argument("--layer", "-l", required=True, help="Layer name")
    layers_transform.add_argument("--dx", type=float, default=0.0, help="Move X by percentage (relative)")
    layers_transform.add_argument("--dy", type=float, default=0.0, help="Move Y by percentage (relative)")
    layers_transform.add_argument("--scale", type=float, default=1.0, help="Scale factor (1.0=no change)")
    layers_transform.add_argument("--rotate", type=float, default=0.0, help="Rotate degrees (clockwise)")
    layers_transform.add_argument("--opacity", type=float, default=-1.0, help="Set opacity (0-1, -1=unchanged)")

    # sessions command group
    sessions_p = sub.add_parser("sessions", help="Session data analytics")
    sessions_sub = sessions_p.add_subparsers(dest="sessions_command")

    sessions_stats = sessions_sub.add_parser("stats", help="Show session statistics")
    sessions_stats.add_argument("--tradition", "-t", default="", help="Filter by tradition")
    sessions_stats.add_argument("--since", default="", help="Filter since date (YYYY-MM-DD)")
    sessions_stats.add_argument("--format", "-f", default="text", choices=["text", "json"], help="Output format")

    sessions_list = sessions_sub.add_parser("list", help="List sessions")
    sessions_list.add_argument("--tradition", "-t", default="", help="Filter by tradition")
    sessions_list.add_argument("--limit", "-n", type=int, default=20, help="Max sessions to show")
    sessions_list.add_argument("--sort", default="date", choices=["score", "date"], help="Sort order")

    # cases command group
    cases_p = sub.add_parser("cases", help="Review and label learning-loop case logs")
    cases_sub = cases_p.add_subparsers(dest="cases_command")
    cases_review = cases_sub.add_parser("review", help="Apply human review labels to one case")
    cases_review.add_argument("input", help="Input JSONL case log")
    cases_review.add_argument("--case-id", required=True, help="Case id to update")
    cases_review.add_argument(
        "--human-accept",
        default=None,
        help="Human acceptance label: true/false",
    )
    cases_review.add_argument("--failure-type", default=None, help="Failure taxonomy label")
    cases_review.add_argument("--preferred-action", default=None, help="Preferred next action label")
    cases_review.add_argument("--reviewer", default=None, help="Reviewer id/name")
    cases_review.add_argument("--reviewed-at", default=None, help="Review timestamp, ISO-8601 UTC recommended")
    cases_review.add_argument("--notes", default=None, help="Free-form review notes")
    cases_review.add_argument(
        "--output",
        "-o",
        default="",
        help="Output reviewed JSONL path (default: INPUT.reviewed.jsonl)",
    )
    cases_review.add_argument(
        "--sidecar-output",
        default="",
        help="Optional review-only JSONL sidecar path, appended if provided",
    )
    cases_intake_user = cases_sub.add_parser(
        "intake-user",
        help="Normalize reviewed private user case JSONL into a case source manifest",
    )
    cases_intake_user.add_argument("input", help="Reviewed user case JSONL")
    cases_intake_user.add_argument("--source-id", required=True, help="Stable user case source id")
    cases_intake_user.add_argument(
        "--output-dir",
        default="",
        help="Output directory for private user case log and source manifest",
    )
    cases_intake_user.add_argument(
        "--output-log",
        default="",
        help="Output private user case JSONL path (default: OUTPUT_DIR/SOURCE.private.user_cases.jsonl)",
    )
    cases_intake_user.add_argument(
        "--manifest-output",
        default="",
        help="Output case source manifest path (default: OUTPUT_DIR/SOURCE.case_source_manifest.json)",
    )
    cases_intake_user.add_argument(
        "--write-private-asset-map",
        action="store_true",
        help="Write a local-only private:// ref to absolute path sidecar map",
    )
    cases_intake_user.add_argument(
        "--asset-map-output",
        default="",
        help="Output private asset map path (default: OUTPUT_DIR/SOURCE.private.asset_map.json)",
    )
    cases_seed = cases_sub.add_parser("seed", help="Build local seed case JSONL logs")
    cases_seed.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output directory for seed JSONL logs",
    )
    cases_seed.add_argument(
        "--repo-root",
        default="",
        help="Repository root (default: current working directory)",
    )
    cases_seed.add_argument(
        "--manifest",
        default="",
        help="Seed manifest path (default: docs/benchmarks/learning/local_seed_manifest.json)",
    )
    cases_baseline = cases_sub.add_parser(
        "baseline-report",
        help="Build local seed baseline metrics report",
    )
    cases_baseline.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output JSON report path",
    )
    cases_baseline.add_argument(
        "--repo-root",
        default="",
        help="Repository root (default: current working directory)",
    )
    cases_baseline.add_argument(
        "--manifest",
        default="",
        help="Seed manifest path (default: docs/benchmarks/learning/local_seed_manifest.json)",
    )
    cases_baseline.add_argument(
        "--policy",
        action="append",
        default=[],
        choices=("label_oracle", "observable_signal"),
        help="Redraw router policy to evaluate; repeat to include multiple policies",
    )
    cases_baseline.add_argument(
        "--min-action-accuracy",
        action="append",
        default=[],
        metavar="POLICY=VALUE",
        help="Fail if a policy action_accuracy is below VALUE",
    )
    cases_baseline.add_argument(
        "--max-mismatches",
        action="append",
        default=[],
        metavar="POLICY=COUNT",
        help="Fail if a policy has more than COUNT mismatched cases",
    )
    cases_export = cases_sub.add_parser(
        "export-dataset",
        help="Export leak-resistant tiny model/agent dataset JSONL",
    )
    cases_export.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output JSONL dataset path",
    )
    cases_export.add_argument(
        "--repo-root",
        default="",
        help="Repository root (default: current working directory)",
    )
    cases_export.add_argument(
        "--manifest",
        default="",
        help="Seed manifest path (default: docs/benchmarks/learning/local_seed_manifest.json)",
    )
    cases_export.add_argument(
        "--case-log",
        action="append",
        default=[],
        help="Additional reviewed case JSONL path; repeat to include multiple logs",
    )
    cases_export.add_argument(
        "--case-source-manifest",
        default="",
        help="JSON manifest describing user/manual/synthetic reviewed case logs",
    )
    cases_export.add_argument(
        "--auxiliary-signal-manifest",
        default="",
        help=(
            "Explicit open-model signal promotion manifest to attach as "
            "reviewed auxiliary training features"
        ),
    )
    cases_export.add_argument(
        "--source-dependency-manifest",
        default="",
        help=(
            "Explicit source-dependency label manifest to attach as reviewed "
            "source-context training targets"
        ),
    )
    cases_export.add_argument(
        "--no-local-seeds",
        action="store_true",
        help="Only export records from --case-log inputs",
    )

    # resume command
    resume_p = sub.add_parser("resume", help="Resume pipeline from checkpoint")
    resume_p.add_argument("session_id", help="Session ID to resume")
    resume_p.add_argument("--from-round", type=int, default=0, help="Resume from this round (0 = last)")
    resume_p.add_argument("--provider", "-p", default="", help="Override provider (default: from checkpoint)")

    # tools command — delegates to CLI adapter
    tools_parser = sub.add_parser("tools", help="Run algorithmic analysis/processing tools")
    tools_parser.add_argument("tools_args", nargs=argparse.REMAINDER)

    # dream command — periodic evolution consolidation
    dream_p = sub.add_parser("dream", help="Run Dream-style evolution consolidation (Orient→Gather→Consolidate→Prune)")
    dream_p.add_argument("--force", action="store_true", help="Bypass gate checks and run immediately")
    dream_p.add_argument("--data-dir", default="", help="Path to VULCA data directory (default: ~/.vulca/data)")
    dream_p.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args(argv)

    try:
        from vulca.telemetry import emit_cli_invoked
        emit_cli_invoked(args.command or "help")
    except Exception:
        pass

    if args.command in ("evaluate", "eval", "e"):
        _cmd_evaluate(args)
    elif args.command in ("create", "c"):
        if not args.intent.strip():
            print("Error: intent cannot be empty.", file=sys.stderr)
            sys.exit(1)
        if args.hitl:
            _cmd_create_hitl(args)
        else:
            _cmd_create(args)
    elif args.command in ("traditions", "t"):
        _cmd_traditions()
    elif args.command in ("tradition", "td"):
        if args.init:
            _cmd_tradition_init(args)
        elif args.name:
            _cmd_tradition(args)
        else:
            print("Error: provide a tradition name or use --init NAME", file=sys.stderr)
            sys.exit(1)
    elif args.command in ("evolution", "evo"):
        _cmd_evolution(args)
    elif args.command == "studio":
        _cmd_studio(args)
    elif args.command == "brief":
        _cmd_brief(args)
    elif args.command == "brief-update":
        _cmd_brief_update(args)
    elif args.command == "concept":
        _cmd_concept(args)
    elif args.command == "sync":
        _cmd_sync(args)
    elif args.command == "telemetry":
        _cmd_telemetry(args)
    elif args.command == "inpaint":
        _cmd_inpaint(args)
    elif args.command == "layers":
        if not args.layers_command:
            layers_p.print_help()
            sys.exit(0)
        _cmd_layers(args)
    elif args.command == "sessions":
        if not args.sessions_command:
            sessions_p.print_help()
            sys.exit(0)
        _cmd_sessions(args)
    elif args.command == "cases":
        if not args.cases_command:
            cases_p.print_help()
            sys.exit(0)
        _cmd_cases(args)
    elif args.command == "resume":
        _cmd_resume(args)
    elif args.command == "tools":
        from vulca.tools.adapters.cli import build_tools_parser, run_tools_command
        from vulca.tools.registry import ToolRegistry
        reg = ToolRegistry()
        reg.discover()
        tools_p = build_tools_parser(reg)
        tools_args = tools_p.parse_args(args.tools_args)
        output = run_tools_command(tools_args, reg)
        print(output)
    elif args.command == "dream":
        _cmd_dream(args)
    else:
        parser.print_help()
        sys.exit(1)


# ---------------------------------------------------------------------------
# Evaluate command
# ---------------------------------------------------------------------------

def _cmd_evaluate(args: argparse.Namespace) -> None:
    import json as json_mod
    import os
    from vulca import evaluate

    if hasattr(args, 'vlm_model') and args.vlm_model:
        os.environ["VULCA_VLM_MODEL"] = args.vlm_model
    if hasattr(args, 'vlm_base_url') and args.vlm_base_url:
        os.environ["VULCA_VLM_BASE_URL"] = args.vlm_base_url

    skills = [s.strip() for s in args.skills.split(",") if s.strip()] if args.skills else None
    mode = args.mode

    # Fusion mode: evaluate against multiple traditions
    if mode == "fusion" and "," in args.tradition:
        _cmd_evaluate_fusion(args, skills)
        return

    try:
        result = evaluate(
            args.image,
            intent=args.intent,
            tradition=args.tradition,
            subject=args.subject,
            skills=skills,
            api_key=args.api_key,
            mock=args.mock,
            mode=mode,
        )
    except (ValueError, FileNotFoundError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        import dataclasses
        print(json_mod.dumps(dataclasses.asdict(result), indent=2, ensure_ascii=False))
        return

    if mode == "reference":
        _print_reference_result(result)
    else:
        _print_strict_result(result)



def _print_strict_result(result) -> None:
    """Strict mode output: judge style with pass/fail indicators."""
    print(f"\n  VULCA Evaluation Result")
    print(f"  {'=' * 50}")
    print(f"  Score:     {result.score:.0%}")
    print(f"  Tradition: {result.tradition}")
    print(f"  Risk:      {result.risk_level}")
    print()
    print(f"  Dimensions:")
    for level in ("L1", "L2", "L3", "L4", "L5"):
        score = result.dimensions.get(level, 0)
        bar = "\u2588" * int(score * 20) + "\u2591" * (20 - int(score * 20))
        indicator = "\u2713" if score >= 0.7 else "\u2717"
        print(f"    {level} {_DIM_NAMES[level]:<25s} {bar} {score:.0%}  {indicator}")

    # Extra dimensions (tradition-specific)
    if result.extra_scores:
        print(f"\n  Tradition-Specific:")
        for ekey, escore in result.extra_scores.items():
            extra_names = result.raw.get("_extra_names", {})
            ename = extra_names.get(ekey, ekey)
            bar = "\u2588" * int(escore * 20) + "\u2591" * (20 - int(escore * 20))
            mark = "\u2713" if escore >= 0.6 else "\u2717"
            print(f"    {ename:<32s} {bar} {escore:.0%}  {mark}")

    print()
    print(f"  Summary: {result.summary}")

    if result.suggestions:
        print(f"\n  Suggestions:")
        for level in ("L1", "L2", "L3", "L4", "L5"):
            s = result.suggestions.get(level, "")
            if s and result.dimensions.get(level, 0) < 0.7:
                print(f"    {level}: {s}")

    if result.recommendations:
        print(f"\n  Recommendations:")
        for r in result.recommendations:
            print(f"    - {r}")

    if result.skills:
        print(f"\n  Skills:")
        for name, sr in result.skills.items():
            print(f"    {name}: {sr.score:.0%} -- {sr.summary}")

    print(f"\n  Latency: {result.latency_ms}ms | Cost: ${result.cost_usd:.4f}")
    print()


def _print_reference_result(result) -> None:
    """Reference mode output: advisor style with deviation analysis."""
    print(f"\n  VULCA Cultural Analysis (reference mode)")
    print(f"  {'=' * 50}")
    print(f"  Alignment: {result.score:.0%}")
    print(f"  Tradition: {result.tradition}")
    print()
    print(f"  Dimension Analysis:")
    for level in ("L1", "L2", "L3", "L4", "L5"):
        score = result.dimensions.get(level, 0)
        bar = "\u2588" * int(score * 20) + "\u2591" * (20 - int(score * 20))
        deviation = result.deviation_types.get(level, "traditional")
        dev_label = _DEVIATION_LABELS.get(deviation, deviation)
        print(f"    {level} {_DIM_NAMES[level]:<25s} {bar} {score:.0%}  ({dev_label})")

        # Show rationale for divergent dimensions
        if deviation != "traditional":
            rationale = result.rationales.get(level, "")
            if rationale:
                print(f"       Divergence: {rationale}")

        # Show suggestion
        suggestion = result.suggestions.get(level, "")
        if suggestion:
            if deviation == "traditional":
                print(f"       To push further: {suggestion}")
            else:
                print(f"       To align with tradition: {suggestion}")
                print(f"       To lean into departure: consider amplifying the experimental elements")

    # Extra dimensions (tradition-specific)
    if result.extra_scores:
        print(f"\n  Tradition-Specific:")
        for ekey, escore in result.extra_scores.items():
            extra_names = result.raw.get("_extra_names", {})
            ename = extra_names.get(ekey, ekey)
            bar = "\u2588" * int(escore * 20) + "\u2591" * (20 - int(escore * 20))
            mark = "\u2713" if escore >= 0.6 else "\u2717"
            print(f"    {ename:<32s} {bar} {escore:.0%}  {mark}")

    print()
    print(f"  Summary: {result.summary}")
    print(f"\n  Latency: {result.latency_ms}ms | Cost: ${result.cost_usd:.4f}")
    print()


def _cmd_evaluate_fusion(args: argparse.Namespace, skills: list[str] | None) -> None:
    """Fusion mode: evaluate against multiple traditions and compare."""
    import json as json_mod
    from vulca import evaluate

    traditions = [t.strip() for t in args.tradition.split(",") if t.strip()]
    results = []

    for tradition in traditions:
        try:
            result = evaluate(
                args.image,
                intent=args.intent,
                tradition=tradition,
                subject=args.subject,
                skills=skills,
                api_key=args.api_key,
                mock=args.mock,
                mode="reference",
            )
            results.append((tradition, result))
        except ValueError as e:
            print(f"  Warning: {tradition} failed: {e}", file=sys.stderr)

    if not results:
        print("Error: no traditions evaluated successfully", file=sys.stderr)
        sys.exit(1)

    if args.json:
        import dataclasses
        all_data = {t: dataclasses.asdict(r) for t, r in results}
        print(json_mod.dumps(all_data, indent=2, ensure_ascii=False))
        return

    print(f"\n  VULCA Fusion Analysis ({len(results)} traditions)")
    print(f"  {'=' * 60}")
    print()

    # Comparison table header
    trad_labels = [t.replace("_", " ").title()[:15] for t, _ in results]
    header = f"    {'Dimension':<25s}" + "".join(f" {tl:>15s}" for tl in trad_labels)
    print(header)
    print(f"    {'-' * 25}" + "".join(f" {'-' * 15}" for _ in results))

    for level in ("L1", "L2", "L3", "L4", "L5"):
        row = f"    {_DIM_NAMES[level]:<25s}"
        for _, result in results:
            score = result.dimensions.get(level, 0)
            deviation = result.deviation_types.get(level, "traditional")
            marker = "*" if deviation != "traditional" else " "
            row += f" {score:>13.0%}{marker} "
        print(row)

    print()
    print(f"    {'Overall Alignment':<25s}", end="")
    for _, result in results:
        print(f" {result.score:>14.0%} ", end="")
    print()

    # Best tradition analysis
    best_trad, best_result = max(results, key=lambda x: x[1].score)
    print(f"\n  Closest tradition: {best_trad} ({best_result.score:.0%})")

    # Divergence highlights
    print(f"\n  Divergence highlights:")
    for tradition, result in results:
        departures = [
            level for level in ("L1", "L2", "L3", "L4", "L5")
            if result.deviation_types.get(level) != "traditional"
        ]
        if departures:
            dims = ", ".join(f"{d} ({_DIM_NAMES[d]})" for d in departures)
            print(f"    vs {tradition}: departures in {dims}")

    total_cost = sum(r.cost_usd for _, r in results)
    total_latency = sum(r.latency_ms for _, r in results)
    print(f"\n  Latency: {total_latency}ms | Cost: ${total_cost:.4f}")
    print()


# ---------------------------------------------------------------------------
# Create command
# ---------------------------------------------------------------------------

def _cmd_create(args: argparse.Namespace) -> None:
    import json as json_mod
    import os
    from vulca import create

    # Warn if tradition doesn't exist
    if args.tradition:
        from vulca.cultural.loader import get_tradition
        if get_tradition(args.tradition) is None:
            print(f"Warning: tradition '{args.tradition}' not found, using default weights", file=sys.stderr)

    if args.image_provider:
        os.environ["VULCA_IMAGE_PROVIDER"] = args.image_provider
    if hasattr(args, 'image_base_url') and args.image_base_url:
        os.environ["VULCA_IMAGE_BASE_URL"] = args.image_base_url

    weights = _parse_weights(args.weights) if args.weights else None

    if getattr(args, "layered", False):
        import asyncio
        from vulca.pipeline.engine import execute
        from vulca.pipeline.templates import DEFAULT, LAYERED
        from vulca.pipeline.types import PipelineInput

        # v0.13: discouraged tradition warning
        try:
            from vulca.cultural.loader import get_tradition
            _trad = get_tradition(args.tradition or "default")
            _layerability = getattr(_trad, "layerability", "split") if _trad else "split"
        except Exception:
            _layerability = "split"
        if _layerability == "discouraged":
            _msg = (f"Tradition '{args.tradition or 'default'}' does not support "
                    "high-quality layering.\n"
                    "  Result is best-effort and intended for analysis only.")
            if sys.stdin.isatty():
                print(f"\u26a0 {_msg}\n  Continue? [y/N] ", end="")
                if input().strip().lower() != "y":
                    print("Aborted.")
                    return
            else:
                print(f"\u26a0 {_msg}", file=sys.stderr)

        node_params: dict[str, dict] = {}
        if weights:
            node_params["evaluate"] = {"custom_weights": weights}
        if getattr(args, "content_lock", False) or getattr(args, "output_is_artwork_itself", False):
            from vulca.content_lock import ContentLock, extract_content_lock

            artifact_boundary = (
                getattr(args, "output_is_artwork_itself", False)
                or getattr(args, "content_lock", False)
            )
            if getattr(args, "content_lock", False):
                lock = extract_content_lock(
                    args.intent,
                    output_is_artwork_itself=artifact_boundary,
                )
            else:
                lock = ContentLock(
                    original_intent=" ".join(args.intent.strip().split()),
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

        pipeline_input = PipelineInput(
            subject=args.subject or args.intent,
            intent=args.intent,
            tradition=args.tradition or "default",
            provider=args.provider,
            node_params=node_params,
            eval_mode=args.mode,
            layered=True,
            no_cache=getattr(args, "no_cache", False),
            strict=getattr(args, "strict", False),
            max_layers=getattr(args, "max_layers", 8),
        )
        template = LAYERED
        try:
            loop = asyncio.new_event_loop()
            output = loop.run_until_complete(execute(template, pipeline_input))
            loop.close()
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            print(json_mod.dumps(output.to_dict(), indent=2, ensure_ascii=False))
            return

        print(f"\n  VULCA Layered Creation Result")
        print(f"  {'=' * 40}")
        print(f"  Session:   {output.session_id}")
        print(f"  Status:    {output.status}")
        print(f"  Tradition: {output.tradition}")
        print(f"  Rounds:    {output.total_rounds}")
        print(f"  Score:     {output.weighted_total:.0%}")
        print()
        return

    try:
        result = create(
            args.intent,
            tradition=args.tradition,
            subject=args.subject,
            provider=args.provider,
            api_key=args.api_key,
            base_url=args.base_url,
            weights=weights,
            eval_mode=args.mode,
            reference=getattr(args, "reference", "") or "",
            ref_type=getattr(args, "ref_type", "full") or "full",
            colors=getattr(args, "colors", "") or "",
            content_lock=getattr(args, "content_lock", False),
            output_is_artwork_itself=getattr(args, "output_is_artwork_itself", False),
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Save image to file
    import base64 as _b64
    from pathlib import Path as _Path

    image_path = ""
    if result.best_image_b64:
        out_path = args.output if args.output else f"vulca-{result.session_id}.png"
        out_path = str(_Path(out_path).resolve())
        _Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        _Path(out_path).write_bytes(_b64.b64decode(result.best_image_b64))
        image_path = out_path

    if args.json:
        import dataclasses
        data = dataclasses.asdict(result)
        if image_path:
            data["image_path"] = image_path
        print(json_mod.dumps(data, indent=2, ensure_ascii=False))
        return

    print(f"\n  VULCA Creation Result")
    print(f"  {'=' * 40}")
    print(f"  Session:   {result.session_id}")
    print(f"  Mode:      {result.mode} (eval: {result.eval_mode})")
    print(f"  Tradition: {result.tradition}")
    print(f"  Rounds:    {result.total_rounds}")
    if result.best_candidate_id:
        print(f"  Best:      {result.best_candidate_id}")
    if image_path:
        print(f"  Image:     {image_path}")
    if result.summary:
        print(f"  Summary:   {result.summary}")

    if result.suggestions:
        print(f"\n  Suggestions:")
        for level in ("L1", "L2", "L3", "L4", "L5"):
            s = result.suggestions.get(level, "")
            if s:
                print(f"    {level}: {s}")

    if result.recommendations:
        print(f"\n  Recommendations:")
        for r in result.recommendations:
            print(f"    - {r}")

    print(f"\n  Latency: {result.latency_ms}ms | Cost: ${result.cost_usd:.4f}")
    print()


def _cmd_create_hitl(args: argparse.Namespace) -> None:
    """Interactive HITL create: run pipeline, pause, show scores, prompt user."""
    import asyncio
    import json as json_mod
    from vulca.pipeline.engine import execute
    from vulca.pipeline.templates import DEFAULT
    from vulca.pipeline.types import PipelineInput

    weights = _parse_weights(args.weights) if args.weights else None

    node_params: dict[str, dict] = {}
    if weights:
        node_params["evaluate"] = {"custom_weights": weights}

    pipeline_input = PipelineInput(
        subject=args.subject or args.intent,
        intent=args.intent,
        tradition=args.tradition or "default",
        provider=args.provider,
        node_params=node_params,
        eval_mode=args.mode,
        layered=getattr(args, "layered", False),
    )

    if getattr(args, "layered", False):
        from vulca.pipeline.templates import LAYERED
        template = LAYERED
    else:
        template = DEFAULT

    try:
        loop = asyncio.new_event_loop()
        output = loop.run_until_complete(
            execute(template, pipeline_input, interrupt_before={"decide"})
        )
        loop.close()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json_mod.dumps(output.to_dict(), indent=2, ensure_ascii=False))
        return

    # Display L1-L5 scores as bar chart
    print(f"\n  VULCA HITL Review (mode: {args.mode})")
    print(f"  {'=' * 40}")
    print(f"  Session:   {output.session_id}")
    print(f"  Tradition: {output.tradition}")
    print(f"  Status:    {output.status}")
    print()
    print(f"  L1-L5 Scores:")
    scores = output.final_scores
    for level in ("L1", "L2", "L3", "L4", "L5"):
        score = scores.get(level, 0.0)
        bar = "\u2588" * int(score * 20) + "\u2591" * (20 - int(score * 20))
        print(f"    {level} {_DIM_NAMES[level]:<25s} {bar} {score:.0%}")
    print(f"\n  Weighted Total: {output.weighted_total:.0%}")
    print()

    # Interactive prompt
    try:
        choice = input("  [A]ccept / [Q]uit? ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = "q"

    if choice in ("a", "accept"):
        print("  -> Accepted. Session stored.")
        # Fire on_complete to persist
        try:
            from vulca.pipeline.hooks import default_on_complete
            oc_loop = asyncio.new_event_loop()
            oc_loop.run_until_complete(default_on_complete(output))
            oc_loop.close()
        except Exception:
            logging.getLogger("vulca").debug("on_complete hook failed in HITL accept")
    else:
        print("  -> Quit. Session discarded.")
    print()


# ---------------------------------------------------------------------------
# Tradition commands
# ---------------------------------------------------------------------------

def _cmd_traditions() -> None:
    from vulca.cultural.loader import get_all_weight_tables

    weights_all = get_all_weight_tables()
    print(f"\n  Available Traditions ({len(weights_all)}):")
    print(f"  {'=' * 50}")
    dim_names = {"L1": "Visual", "L2": "Technical", "L3": "Cultural", "L4": "Critical", "L5": "Philosophical"}
    for name, weights in sorted(weights_all.items()):
        emphasis = max(weights, key=weights.get)
        print(f"    {name:<25s} emphasis: {dim_names.get(emphasis, emphasis)} ({weights[emphasis]:.0%})")
    print(f"\n  Use a custom tradition: vulca evaluate img.jpg -t ./my_tradition.yaml")
    print(f"  Create a template:      vulca tradition --init my_style > my_tradition.yaml")
    print()


def _cmd_tradition(args: argparse.Namespace) -> None:
    import json as json_mod
    from vulca.cultural.loader import get_tradition_guide

    guide = get_tradition_guide(args.name)
    if guide is None:
        print(f"Error: Unknown tradition '{args.name}'", file=sys.stderr)
        print("Run 'vulca traditions' to see available traditions.")
        sys.exit(1)

    if args.json:
        print(json_mod.dumps(guide, indent=2, ensure_ascii=False))
        return

    print(f"\n  Cultural Guide: {guide['tradition']}")
    print(f"  {'=' * 50}")
    print(f"  Description: {guide['description']}")
    print(f"  Emphasis:    {guide['emphasis']}")
    print()
    print(f"  L1-L5 Weights:")
    for level in ("L1", "L2", "L3", "L4", "L5"):
        w = guide["weights"].get(level, 0)
        bar = "\u2588" * int(w * 20) + "\u2591" * (20 - int(w * 20))
        print(f"    {level} {bar} {w:.0%}")

    if guide.get("evolved_weights"):
        print(f"\n  Evolved Weights (from {guide.get('sessions_count', 0)} sessions):")
        for level in ("L1", "L2", "L3", "L4", "L5"):
            ew = guide["evolved_weights"].get(level, 0)
            bar = "\u2588" * int(ew * 20) + "\u2591" * (20 - int(ew * 20))
            print(f"    {level} {bar} {ew:.0%}")

    if guide.get("terminology"):
        print(f"\n  Terminology ({len(guide['terminology'])} terms):")
        for t in guide["terminology"][:10]:
            term = t.get("term", "")
            trans = t.get("translation", "")
            raw_defn = t.get("definition", "")
            if isinstance(raw_defn, dict):
                defn = raw_defn.get("en", "")[:60]
            else:
                defn = str(raw_defn)[:60]
            if trans:
                print(f"    {term} ({trans}): {defn}")
            else:
                print(f"    {term}: {defn}")

    if guide.get("taboos"):
        print(f"\n  Taboos ({len(guide['taboos'])}):")
        for tb in guide["taboos"][:5]:
            print(f"    - {tb}")

    print()


def _cmd_tradition_init(args: argparse.Namespace) -> None:
    """Generate a custom tradition YAML template."""
    name = args.init
    template = f"""# VULCA Custom Tradition: {name}
# Usage: vulca evaluate painting.jpg -t ./{name}.yaml

name: {name}

display_name:
  en: "{name.replace('_', ' ').title()}"
  zh: ""

# Optional: inherit from a built-in tradition (weights, terminology, taboos)
# parent: chinese_xieyi

# L1-L5 evaluation weights (MUST sum to 1.0)
# L1: Visual Perception | L2: Technical Execution | L3: Cultural Context
# L4: Critical Interpretation | L5: Philosophical Aesthetics
weights:
  L1: 0.20
  L2: 0.20
  L3: 0.20
  L4: 0.20
  L5: 0.20

# Override parent weights (only if 'parent' is set):
# override_weights:
#   L1: 0.30
#   L3: 0.10

# Cultural terminology specific to this tradition
terminology:
  - term: "example_technique"
    term_zh: ""
    definition:
      en: "Description of this technique and its significance."
    category: technique
    l_levels: [L2]

# Cultural taboos to watch for
taboos:
  - rule: "Avoid this specific mistake"
    severity: medium
    l_levels: [L3]
    explanation: "Why this is problematic in this context."

# Remove inherited taboos (only if 'parent' is set):
# taboos_remove:
#   - "Inherited taboo rule text to remove"

pipeline:
  variant: default
"""
    print(template)


# ---------------------------------------------------------------------------
# Evolution command
# ---------------------------------------------------------------------------

def _cmd_evolution(args: argparse.Namespace) -> None:
    import json as json_mod
    from vulca.cultural.loader import get_weights
    from vulca.cultural import TRADITION_WEIGHTS

    original = TRADITION_WEIGHTS.get(args.name)
    if original is None:
        print(f"Error: Unknown tradition '{args.name}'", file=sys.stderr)
        sys.exit(1)

    evolved = get_weights(args.name)

    result = {
        "tradition": args.name,
        "original_weights": original,
        "evolved_weights": evolved,
        "weight_changes": {k: f"{evolved.get(k, 0) - original.get(k, 0):+.3f}" for k in original},
    }

    if args.json:
        print(json_mod.dumps(result, indent=2, ensure_ascii=False))
        return

    print(f"\n  Evolution Status: {args.name}")
    print(f"  {'=' * 50}")
    names = {"L1": "Visual", "L2": "Technical", "L3": "Cultural", "L4": "Critical", "L5": "Philosophical"}
    print(f"  {'Dim':<5} {'Original':>10} {'Evolved':>10} {'Change':>10}")
    print(f"  {'-'*5} {'-'*10} {'-'*10} {'-'*10}")
    for level in ("L1", "L2", "L3", "L4", "L5"):
        o = original.get(level, 0)
        e = evolved.get(level, 0)
        delta = e - o
        sign = "+" if delta >= 0 else ""
        print(f"  {level:<5} {o:>9.1%} {e:>9.1%} {sign}{delta:>8.1%}")

    # Show session count from evolved_context.json
    try:
        from vulca.digestion.local_evolver import LocalEvolver
        evolver = LocalEvolver()
        evolved_data = evolver.load_evolved(args.name)
        if evolved_data:
            count = evolved_data.get("session_count", 0)
            print(f"  Sessions: {count}")
        else:
            # Try loading total from evolved_context.json directly
            from pathlib import Path
            import json as _j
            ctx_path = evolver.data_dir / "evolved_context.json"
            if ctx_path.exists():
                ctx = _j.loads(ctx_path.read_text())
                total = ctx.get("total_sessions", 0)
                tradition_data = ctx.get("traditions", {}).get(args.name, {})
                t_count = tradition_data.get("session_count", 0)
                print(f"  Sessions: {t_count} ({total} total across all traditions)")
    except Exception:
        pass
    print()


# ---------------------------------------------------------------------------
# Studio commands
# ---------------------------------------------------------------------------

def _cmd_studio(args: argparse.Namespace) -> None:
    from vulca.studio.interactive import run_studio

    auto = getattr(args, "auto", False)
    max_rounds = getattr(args, "max_rounds", 3)
    if args.resume:
        from vulca.studio.session import StudioSession
        session = StudioSession.load(args.intent_or_dir)
        print(f"Resuming session {session.session_id}...")
        result = run_studio(
            session.brief.intent,
            project_dir=args.intent_or_dir,
            provider=args.provider,
            concept_count=args.count,
            api_key=args.api_key,
            auto=auto,
            max_rounds=max_rounds,
        )
    else:
        result = run_studio(
            args.intent_or_dir,
            provider=args.provider,
            concept_count=args.count,
            api_key=args.api_key,
            auto=auto,
            max_rounds=max_rounds,
        )
    if result:
        print(f"\nSession {result.get('session_id', '?')}: {result.get('status', 'unknown')}")


def _cmd_brief(args: argparse.Namespace) -> None:
    from pathlib import Path
    from vulca.studio.brief import Brief

    project = Path(args.project_dir)
    brief_file = project / "brief.yaml"

    if args.intent:
        b = Brief.new(args.intent, mood=args.mood)
        filepath = b.save(project)
        print(f"Brief created: {filepath}")
        print(f"  Intent: {b.intent}")
        print(f"  Session: {b.session_id}")
        if b.mood:
            print(f"  Mood: {b.mood}")
    elif brief_file.exists():
        b = Brief.load(project)
        print(f"VULCA Brief -- {b.session_id}")
        print(f"  Intent: {b.intent}")
        if b.mood:
            print(f"  Mood: {b.mood}")
        if b.style_mix:
            styles = ", ".join(s.tradition or s.tag for s in b.style_mix)
            print(f"  Style: {styles}")
        if b.selected_concept:
            print(f"  Concept: {b.selected_concept}")
        if b.generations:
            print(f"  Generations: {len(b.generations)}")
    else:
        print(f"No brief found at {project}. Use --intent to create one.", file=sys.stderr)
        sys.exit(1)


def _cmd_brief_update(args: argparse.Namespace) -> None:
    from pathlib import Path
    from vulca.studio.brief import Brief
    from vulca.studio.nl_update import apply_update, parse_nl_update

    b = Brief.load(Path(args.project_dir))
    result = parse_nl_update(args.instruction, b)
    apply_update(b, result)
    b.save(Path(args.project_dir))
    print(f"Brief updated (rollback to: {result.rollback_to.value})")
    print(f"  Changes: {', '.join(result.field_updates.keys())}")
    print(f"  {result.explanation}")


def _cmd_concept(args: argparse.Namespace) -> None:
    import asyncio
    from pathlib import Path
    from vulca.studio.brief import Brief
    from vulca.studio.phases.concept import ConceptPhase

    b = Brief.load(Path(args.project_dir))
    phase = ConceptPhase()

    if args.select is not None:
        phase.select(b, index=args.select - 1, notes=args.notes)
        b.save(Path(args.project_dir))
        print(f"Selected concept {args.select}: {b.selected_concept}")
    else:
        loop = asyncio.new_event_loop()
        paths = loop.run_until_complete(
            phase.generate_concepts(b, count=args.count, provider=args.provider, project_dir=args.project_dir)
        )
        loop.close()
        b.save(Path(args.project_dir))
        print(f"Generated {len(paths)} concepts:")
        for i, p in enumerate(paths, 1):
            print(f"  {i}. {p}")
        print(f"\nSelect with: vulca concept {args.project_dir} --select N")


# ---------------------------------------------------------------------------
# Sync command
# ---------------------------------------------------------------------------

def _cmd_sync(args: argparse.Namespace) -> None:
    import json as json_mod
    import os
    from pathlib import Path

    api_url = os.environ.get("VULCA_API_URL", "")
    api_key = os.environ.get("VULCA_API_KEY", "")
    if not api_url:
        print("Error: Set VULCA_API_URL environment variable.", file=sys.stderr)
        print("  export VULCA_API_URL='https://your-backend.com'", file=sys.stderr)
        print("  export VULCA_API_KEY='your-key'", file=sys.stderr)
        sys.exit(1)

    data_dir = Path.home() / ".vulca" / "data"

    if not args.pull_only:
        # Push local sessions
        sessions_file = data_dir / "sessions.jsonl"
        synced_file = data_dir / "synced.json"

        synced_ids: set[str] = set()
        if synced_file.exists():
            synced_ids = set(json_mod.loads(synced_file.read_text()))

        to_push = []
        if sessions_file.exists():
            for line in sessions_file.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json_mod.loads(line)
                    sid = entry.get("session_id", "")
                    if sid and sid not in synced_ids:
                        to_push.append(entry)
                        synced_ids.add(sid)
                except json_mod.JSONDecodeError:
                    continue

        if to_push:
            import httpx
            try:
                resp = httpx.post(
                    f"{api_url.rstrip('/')}/api/v1/sync",
                    json={"sessions": to_push},
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=30,
                )
                resp.raise_for_status()
                synced_file.parent.mkdir(parents=True, exist_ok=True)
                synced_file.write_text(json_mod.dumps(sorted(synced_ids)))
                print(f"Pushed {len(to_push)} sessions to {api_url}")
            except Exception as exc:
                print(f"Push failed: {exc}", file=sys.stderr)
                sys.exit(1)
        else:
            print("No new sessions to push.")

    if not args.push_only:
        # Pull evolved context
        import httpx
        try:
            resp = httpx.get(
                f"{api_url.rstrip('/')}/api/v1/evolved-context",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
            resp.raise_for_status()
            evolved_path = data_dir / "evolved_context.json"
            evolved_path.parent.mkdir(parents=True, exist_ok=True)
            evolved_path.write_text(resp.text)
            print(f"Pulled evolved context -> {evolved_path}")
        except Exception as exc:
            print(f"Pull failed: {exc}", file=sys.stderr)
            sys.exit(1)


# ---------------------------------------------------------------------------
# Telemetry command
# ---------------------------------------------------------------------------

def _cmd_telemetry(args: argparse.Namespace) -> None:
    import json as json_mod
    from vulca.telemetry import (
        reset_anonymous_install_id,
        set_telemetry_enabled,
        telemetry_status,
    )

    command = args.telemetry_command or "status"
    if command == "enable":
        set_telemetry_enabled(True)
    elif command == "disable":
        set_telemetry_enabled(False)
    elif command == "reset-id":
        reset_anonymous_install_id()
    elif command != "status":
        print(f"Error: unknown telemetry command {command!r}", file=sys.stderr)
        sys.exit(1)

    status = telemetry_status()
    if args.json:
        print(json_mod.dumps(status, indent=2, ensure_ascii=False))
        return

    print("VULCA Telemetry")
    print(f"  enabled: {str(status['enabled']).lower()}")
    print(f"  source: {status['source']}")
    print(f"  do_not_track: {str(status['do_not_track']).lower()}")
    print(f"  config_path: {status['config_path']}")
    install_id = status["anonymous_install_id"] or "(not created)"
    print(f"  anonymous_install_id: {install_id}")


# ---------------------------------------------------------------------------
# Inpaint command
# ---------------------------------------------------------------------------

def _cmd_inpaint(args: argparse.Namespace) -> None:
    from vulca.inpaint import inpaint as do_inpaint

    if args.select is None:
        select_idx = 0
    elif args.select < 1:
        print("Error: --select must be >= 1 (1-based index)", file=sys.stderr)
        sys.exit(1)
    else:
        select_idx = args.select - 1
    result = do_inpaint(
        args.image,
        region=args.region,
        instruction=args.instruction,
        tradition=args.tradition,
        provider=args.provider,
        count=args.count,
        select=select_idx,
        output=args.output,
        mock=args.mock,
    )
    print(f"\n  VULCA Inpaint Result")
    print(f"  {'='*40}")
    print(f"  Region: {result.bbox}")
    print(f"  Variants: {len(result.variants)}")
    print(f"  Selected: v{result.selected + 1}")
    print(f"  Blended: {result.blended}")
    print(f"  Latency: {result.latency_ms}ms | Cost: ${result.cost_usd:.4f}")


# ---------------------------------------------------------------------------
# Layers command group
# ---------------------------------------------------------------------------

def _cmd_layers(args: argparse.Namespace) -> None:
    import asyncio
    from pathlib import Path

    if args.layers_command == "analyze":
        from vulca.layers.analyze import analyze_layers
        loop = asyncio.new_event_loop()
        layers = loop.run_until_complete(
            analyze_layers(args.image, provider=args.provider)
        )
        loop.close()
        print(f"\n  Identified {len(layers)} layers:")
        for la in layers:
            print(f"    [{la.z_index}] {la.name} ({la.content_type}, {la.blend_mode})")
            print(f"        {la.description}")
            if la.dominant_colors:
                print(f"        colors: {', '.join(la.dominant_colors)}")

    elif args.layers_command == "split":
        from vulca.layers.analyze import analyze_layers
        loop = asyncio.new_event_loop()
        layers = loop.run_until_complete(
            analyze_layers(args.image, provider=args.provider)
        )
        out_dir = args.output or str(Path(args.image).parent / "layers")
        print(f"\n  Splitting {len(layers)} layers ({args.mode} mode) -> {out_dir}")
        if args.mode == "extract":
            from vulca.layers.split import split_extract
            results = split_extract(args.image, layers, output_dir=out_dir)
        elif args.mode == "sam":
            from vulca.layers.sam import sam_split
            results = sam_split(args.image, layers, output_dir=out_dir)
        elif args.mode == "vlm":
            from vulca.layers.split import split_vlm
            results = loop.run_until_complete(
                split_vlm(args.image, layers, output_dir=out_dir,
                          provider=args.provider)
            )
        elif args.mode == "palette":
            from vulca.layers.palette_mask import split_palette
            results = loop.run_until_complete(
                split_palette(args.image, layers, output_dir=out_dir,
                              provider=args.provider)
            )
        elif args.mode == "sam3":
            from vulca.layers.sam3 import sam3_split
            results = sam3_split(args.image, layers, output_dir=out_dir)
        else:
            from vulca.layers.split import split_regenerate
            results = loop.run_until_complete(
                split_regenerate(args.image, layers, output_dir=out_dir,
                                 provider=args.provider, tradition=args.tradition)
            )
        loop.close()
        for r in results:
            print(f"    [{r.info.z_index}] {r.info.name} -> {r.image_path}")
        print(f"    manifest.json -> {Path(out_dir) / 'manifest.json'}")
        if getattr(args, "mode", None) == "palette":
            for artifact_name in (
                "palette_mask.png",
                "palette_mask_quantized.png",
                "decode_report.json",
                "contact_sheet.png",
            ):
                artifact_path = Path(out_dir) / artifact_name
                if artifact_path.exists():
                    print(f"    {artifact_name} -> {artifact_path}")
        from vulca.layers.decompose_cases import (
            append_decompose_case,
            build_decompose_case,
            debug_artifacts_from_output_dir,
            resolve_case_log_path,
            target_hints_from_layer_infos,
        )

        resolved_case_log_path = resolve_case_log_path(
            getattr(args, "case_log", ""),
            out_dir,
        )
        if resolved_case_log_path:
            try:
                manifest_path = str(Path(out_dir) / "manifest.json")
                record = build_decompose_case(
                    source_image=args.image,
                    mode=args.mode,
                    provider=args.provider,
                    model="",
                    tradition=args.tradition,
                    output_dir=out_dir,
                    manifest_path=manifest_path,
                    target_layer_hints=target_hints_from_layer_infos(layers),
                    debug_artifacts=debug_artifacts_from_output_dir(out_dir),
                )
                written_case_log_path = append_decompose_case(
                    resolved_case_log_path,
                    record,
                )
                print(f"    Case log: {record['case_id']} -> {written_case_log_path}")
            except Exception as exc:
                print(f"    Case log error: {exc}")

    elif args.layers_command == "redraw":
        from vulca.layers.manifest import load_manifest
        from vulca.layers.redraw import redraw_layer, redraw_merged
        artwork = load_manifest(args.artwork_dir)
        loop = asyncio.new_event_loop()
        if args.layers and args.merge:
            layer_names = [n.strip() for n in args.layers.split(",")]
            result = loop.run_until_complete(
                redraw_merged(artwork, layer_names=layer_names,
                              instruction=args.instruction, merged_name=args.merged_name,
                              provider=args.provider, tradition=args.tradition,
                              artwork_dir=args.artwork_dir,
                              re_split=getattr(args, 're_split', False))
            )
            if isinstance(result, list):
                print(f"  Merge+redraw+re-split: {len(result)} layers")
                for r in result:
                    print(f"    [{r.info.z_index}] {r.info.name} -> {r.image_path}")
            else:
                print(f"  Merged redraw: {result.info.name} -> {result.image_path}")
        elif args.layer:
            source_layer = next(
                (lr for lr in artwork.layers if lr.info.name == args.layer),
                None,
            )
            result = loop.run_until_complete(
                redraw_layer(artwork, layer_name=args.layer,
                             instruction=args.instruction, provider=args.provider,
                             tradition=args.tradition, artwork_dir=args.artwork_dir)
            )
            print(f"  Redrawn: {result.info.name} -> {result.image_path}")
            from vulca.layers.redraw_cases import (
                append_redraw_case,
                build_redraw_case,
                resolve_case_log_path,
            )
            resolved_case_log_path = resolve_case_log_path(
                getattr(args, "case_log", ""),
                args.artwork_dir,
            )
            if resolved_case_log_path:
                try:
                    if source_layer is None:
                        raise ValueError(f"layer {args.layer!r} not found in artwork")
                    advisory = getattr(result, "redraw_advisory", {}) or {}
                    record = build_redraw_case(
                        artwork_dir=args.artwork_dir,
                        source_image=artwork.source_image,
                        layer_info=source_layer.info,
                        instruction=args.instruction,
                        provider=args.provider,
                        model="",
                        route_requested=str(advisory.get("route_requested", "")),
                        source_layer_path=source_layer.image_path,
                        redrawn_layer_path=result.image_path,
                        redraw_advisory=advisory,
                    )
                    written_case_log_path = append_redraw_case(
                        resolved_case_log_path,
                        record,
                    )
                    print(f"  Case log: {record['case_id']} -> {written_case_log_path}")
                except Exception as exc:
                    print(f"  Case log error: {exc}", file=sys.stderr)
        else:
            print("  Error: specify --layer or --layers with --merge", file=sys.stderr)
            sys.exit(1)
        loop.close()

    elif args.layers_command == "composite":
        from vulca.layers.manifest import load_manifest
        from vulca.layers.composite import composite_layers
        artwork = load_manifest(args.artwork_dir)
        out = args.output or str(Path(args.artwork_dir) / "composite.png")
        import json as _json
        manifest_path = Path(args.artwork_dir) / "manifest.json"
        manifest = _json.loads(manifest_path.read_text())
        width = manifest.get("width", 1024)
        height = manifest.get("height", 1024)
        composite_layers(artwork.layers, width=width, height=height, output_path=out)
        print(f"  Composite: {out}")

    elif args.layers_command == "regenerate":
        from vulca.layers.regenerate import regenerate_from_composite
        from vulca.layers.edit import load_artwork
        artwork = load_artwork(args.artwork_dir)
        loop = asyncio.new_event_loop()
        out = loop.run_until_complete(regenerate_from_composite(
            artwork.composite_path, tradition=args.tradition, provider=args.provider,
        ))
        loop.close()
        print(f"  Regenerated: {out}")

    elif args.layers_command == "evaluate":
        from vulca.layers.edit import load_artwork
        import vulca
        artwork = load_artwork(args.artwork_dir)
        for layer in artwork.layers:
            r = vulca.evaluate(layer.image_path, tradition=args.tradition)
            layer.scores = r.dimensions
            print(f"  [{layer.info.z_index}] {layer.info.name}: {r.score:.0%}")
            for dk, dv in r.dimensions.items():
                print(f"      {dk}: {dv:.0%}")

    elif args.layers_command == "export":
        from vulca.layers.edit import load_artwork
        from vulca.layers.export import export_psd
        from vulca.layers.composite import composite_layers
        artwork = load_artwork(args.artwork_dir)
        if args.format == "psd":
            out = args.output or str(Path(args.artwork_dir) / "layers.psd")
            import json
            manifest_path = Path(args.artwork_dir) / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                width = manifest.get("width", 1024)
                height = manifest.get("height", 1024)
            else:
                width = height = 1024
            export_psd(artwork.layers, width=width, height=height, output_path=out)
            print(f"  Exported PSD: {out}")
        else:
            out = args.output or str(Path(args.artwork_dir) / "composite.png")
            import json
            manifest_path = Path(args.artwork_dir) / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                width = manifest.get("width", 1024)
                height = manifest.get("height", 1024)
            else:
                width = height = 1024
            composite_layers(artwork.layers, width=width, height=height, output_path=out)
            print(f"  Exported PNG: {out}")

    elif args.layers_command == "add":
        from vulca.layers.manifest import load_manifest
        from vulca.layers.ops import add_layer
        artwork = load_manifest(args.artwork_dir)
        result = add_layer(artwork, artwork_dir=args.artwork_dir, name=args.name,
                          description=args.description, z_index=args.z_index,
                          content_type=args.content_type,
                          semantic_path=args.semantic_path)
        print(f"  Added: [{result.info.z_index}] {result.info.name} -> {result.image_path}")

    elif args.layers_command == "remove":
        from vulca.layers.manifest import load_manifest
        from vulca.layers.ops import remove_layer
        artwork = load_manifest(args.artwork_dir)
        remove_layer(artwork, artwork_dir=args.artwork_dir, layer_name=args.layer)
        print(f"  Removed: {args.layer}")

    elif args.layers_command == "reorder":
        from vulca.layers.manifest import load_manifest
        from vulca.layers.ops import reorder_layer
        artwork = load_manifest(args.artwork_dir)
        reorder_layer(artwork, artwork_dir=args.artwork_dir, layer_name=args.layer,
                     new_z_index=args.z_index)
        print(f"  Reordered: {args.layer} -> z_index={args.z_index}")

    elif args.layers_command == "toggle":
        from vulca.layers.manifest import load_manifest
        from vulca.layers.ops import toggle_visibility
        artwork = load_manifest(args.artwork_dir)
        visible = args.visible.lower() in ("true", "1", "yes")
        toggle_visibility(artwork, artwork_dir=args.artwork_dir,
                         layer_name=args.layer, visible=visible)
        print(f"  Toggle: {args.layer} visible={visible}")

    elif args.layers_command == "lock":
        from vulca.layers.manifest import load_manifest
        from vulca.layers.ops import lock_layer
        artwork = load_manifest(args.artwork_dir)
        locked = args.locked.lower() in ("true", "1", "yes")
        lock_layer(artwork, artwork_dir=args.artwork_dir,
                  layer_name=args.layer, locked=locked)
        print(f"  Lock: {args.layer} locked={locked}")

    elif args.layers_command == "merge":
        from vulca.layers.manifest import load_manifest
        from vulca.layers.ops import merge_layers
        artwork = load_manifest(args.artwork_dir)
        layer_names = [n.strip() for n in args.layers.split(",")]
        result = merge_layers(artwork, artwork_dir=args.artwork_dir,
                             layer_names=layer_names, merged_name=args.name)
        print(f"  Merged: {', '.join(layer_names)} -> {result.info.name}")

    elif args.layers_command == "duplicate":
        from vulca.layers.manifest import load_manifest
        from vulca.layers.ops import duplicate_layer
        artwork = load_manifest(args.artwork_dir)
        result = duplicate_layer(artwork, artwork_dir=args.artwork_dir,
                                layer_name=args.layer, new_name=args.name)
        print(f"  Duplicated: {args.layer} -> {result.info.name}")

    elif args.layers_command == "transform":
        from vulca.layers.manifest import load_manifest
        from vulca.layers.ops import transform_layer
        artwork = load_manifest(args.artwork_dir)
        set_opacity = args.opacity if args.opacity >= 0 else None
        transform_layer(artwork, artwork_dir=args.artwork_dir,
                        layer_name=args.layer, dx=args.dx, dy=args.dy,
                        scale=args.scale, rotate=args.rotate,
                        set_opacity=set_opacity)
        layer = next(lr for lr in artwork.layers if lr.info.name == args.layer)
        print(f"  Transformed: {args.layer}")
        print(f"    x={layer.info.x:.1f}% y={layer.info.y:.1f}% "
              f"w={layer.info.width:.1f}% h={layer.info.height:.1f}% "
              f"rot={layer.info.rotation:.1f}° opacity={layer.info.opacity:.2f}")

    elif args.layers_command == "cache":
        import shutil
        if args.cache_cmd == "clear":
            cache_dir = Path(args.artifact_dir) / ".layered_cache"
            shutil.rmtree(cache_dir, ignore_errors=True)
            print(f"  Cleared: {cache_dir}")
        else:
            print(f"Unknown cache command: {args.cache_cmd}", file=sys.stderr)
            sys.exit(1)

    elif args.layers_command == "retry":
        from vulca.layers.retry import retry_layers, UnknownLayerError
        from vulca.providers import get_image_provider
        provider_instance = get_image_provider(args.provider or "mock", api_key="")
        layer_names = [args.layer] if args.layer else None
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(retry_layers(
                args.artifact_dir,
                tradition_name=(args.tradition or None),
                layer_names=layer_names,
                all_failed=bool(args.all_failed),
                provider=provider_instance,
            ))
        except UnknownLayerError as exc:
            print(f"  Error: {exc}", file=sys.stderr)
            loop.close()
            sys.exit(2)
        except ValueError as exc:
            # P0.1: tradition mismatch or missing — surface as a clean
            # operator error, not a stack trace.
            print(f"  Error: {exc}", file=sys.stderr)
            loop.close()
            sys.exit(2)
        loop.close()
        print(f"  Retried: {len(result.layers)} ok, {len(result.failed)} failed")
        for o in result.layers:
            print(f"    [{o.info.z_index}] {o.info.name} -> {o.rgba_path}"
                  f"{' (cached)' if o.cache_hit else ''}")
        for f in result.failed:
            print(f"    [x] {f.role}: {f.reason}", file=sys.stderr)

    else:
        print(f"Unknown layers command: {args.layers_command}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Cases command group
# ---------------------------------------------------------------------------

def _cmd_cases(args: argparse.Namespace) -> None:
    import json as _json

    if args.cases_command == "intake-user":
        from vulca.learning.user_case_intake import write_user_case_intake

        try:
            result = write_user_case_intake(
                input_path=args.input,
                source_id=args.source_id,
                output_dir=args.output_dir or None,
                output_path=args.output_log or None,
                manifest_path=args.manifest_output or None,
                asset_map_path=args.asset_map_output or None,
                write_private_asset_map=bool(args.write_private_asset_map),
            )
        except (ValueError, FileNotFoundError, _json.JSONDecodeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        print(f"  User case log: {result.output_path}")
        print(f"  Records: {result.record_count}")
        print(f"  Source id: {result.source_id}")
        print(f"  Case source manifest: {result.manifest_path}")
        if result.asset_map_path:
            print(f"  Private asset map: {result.asset_map_path}")
        return

    if args.cases_command == "export-dataset":
        from vulca.learning.seed_cases import DEFAULT_SEED_MANIFEST
        from vulca.learning.tiny_dataset import write_tiny_dataset

        try:
            result = write_tiny_dataset(
                repo_root=args.repo_root or Path.cwd(),
                output_path=args.output,
                manifest_path=args.manifest or DEFAULT_SEED_MANIFEST,
                case_log_paths=args.case_log,
                case_source_manifest_path=args.case_source_manifest or None,
                auxiliary_signal_manifest_path=(
                    args.auxiliary_signal_manifest or None
                ),
                source_dependency_manifest_path=(
                    args.source_dependency_manifest or None
                ),
                include_local_seeds=not args.no_local_seeds,
            )
        except (
            ValueError,
            FileNotFoundError,
            subprocess.CalledProcessError,
            _json.JSONDecodeError,
        ) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        print(f"  Tiny dataset: {result.output_path}")
        for case_type in sorted(result.counts_by_case_type):
            print(f"  {case_type}: {result.counts_by_case_type[case_type]}")
        for split in sorted(result.counts_by_split):
            print(f"  {split}: {result.counts_by_split[split]}")
        print(f"  Tiny dataset index: {result.index_path}")
        return

    if args.cases_command == "baseline-report":
        from vulca.learning.seed_report import (
            DEFAULT_BASELINE_POLICIES,
            check_baseline_report,
            parse_policy_int_thresholds,
            parse_policy_thresholds,
            write_local_seed_baseline_report,
        )
        from vulca.learning.seed_cases import DEFAULT_SEED_MANIFEST

        policies = tuple(args.policy) if args.policy else DEFAULT_BASELINE_POLICIES
        try:
            output_path = write_local_seed_baseline_report(
                repo_root=args.repo_root or Path.cwd(),
                output_path=args.output,
                manifest_path=args.manifest or DEFAULT_SEED_MANIFEST,
                policies=policies,
            )
            report = _json.loads(Path(output_path).read_text(encoding="utf-8"))
            violations = check_baseline_report(
                report,
                min_action_accuracy=parse_policy_thresholds(
                    args.min_action_accuracy
                ),
                max_mismatches=parse_policy_int_thresholds(args.max_mismatches),
            )
        except (ValueError, FileNotFoundError, subprocess.CalledProcessError, _json.JSONDecodeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        print(f"  Baseline report: {output_path}")
        for case_type in sorted(report["seed_counts"]):
            print(f"  {case_type}: {report['seed_counts'][case_type]}")
        for policy in policies:
            metrics = report["redraw_router_baselines"][policy]
            print(f"  {policy} action_accuracy: {metrics['action_accuracy']}")
        if violations:
            print("Baseline gate failed:", file=sys.stderr)
            for item in violations:
                if item["metric"] == "action_accuracy":
                    expected = str(item["expected"]).replace(">= ", "")
                    print(
                        f"  {item['policy']} action_accuracy "
                        f"{item['actual']} < {expected}",
                        file=sys.stderr,
                    )
                elif item["metric"] == "mismatch_count":
                    expected = str(item["expected"]).replace("<= ", "")
                    print(
                        f"  {item['policy']} mismatch_count "
                        f"{item['actual']} > {expected}",
                        file=sys.stderr,
                    )
            sys.exit(1)
        return

    if args.cases_command == "seed":
        from vulca.learning.seed_cases import (
            DEFAULT_SEED_MANIFEST,
            write_local_seed_case_logs,
        )

        try:
            result = write_local_seed_case_logs(
                repo_root=args.repo_root or Path.cwd(),
                output_dir=args.output,
                manifest_path=args.manifest or DEFAULT_SEED_MANIFEST,
            )
        except (ValueError, FileNotFoundError, subprocess.CalledProcessError, _json.JSONDecodeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        print(f"  Seed cases: {result.output_dir}")
        for case_type in sorted(result.counts):
            print(f"  {case_type}: {result.counts[case_type]} -> {result.paths[case_type]}")
        print(f"  Seed index: {result.index_path}")
        return

    if args.cases_command != "review":
        print(f"Unknown cases command: {args.cases_command}", file=sys.stderr)
        sys.exit(1)

    from vulca.learning.case_review import parse_human_accept, review_case_log

    review_kwargs = {
        "case_id": args.case_id,
        "output_path": args.output or None,
        "failure_type": args.failure_type,
        "preferred_action": args.preferred_action,
        "reviewer": args.reviewer,
        "reviewed_at": args.reviewed_at,
        "notes": args.notes,
        "sidecar_output_path": args.sidecar_output or None,
    }
    if args.human_accept is not None:
        try:
            review_kwargs["human_accept"] = parse_human_accept(args.human_accept)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    try:
        result = review_case_log(args.input, **review_kwargs)
    except (ValueError, FileNotFoundError, _json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"  Reviewed case: {result.case_id} -> {result.output_path}")
    if result.sidecar_path:
        print(f"  Review sidecar: {result.sidecar_path}")


def _cmd_sessions(args: argparse.Namespace) -> None:
    import json as _json
    from vulca.storage.jsonl import JsonlSessionBackend
    from vulca.stats import compute_session_stats, format_stats_text

    store = JsonlSessionBackend()
    sessions = store.get_all()

    if args.sessions_command == "stats":
        stats = compute_session_stats(sessions, tradition=args.tradition, since=args.since)
        if args.format == "json":
            print(_json.dumps(stats, indent=2, default=str))
        else:
            print(format_stats_text(stats))

    elif args.sessions_command == "list":
        filtered = sessions
        if args.tradition:
            filtered = [s for s in filtered if s.get("tradition") == args.tradition]
        if args.sort == "score":
            filtered.sort(key=lambda s: s.get("weighted_total", 0.0), reverse=True)
        else:
            filtered.sort(key=lambda s: s.get("created_at", 0), reverse=True)
        filtered = filtered[:args.limit]
        print(f"\n  Showing {len(filtered)} of {len(sessions)} sessions:\n")
        for s in filtered:
            sid = s.get("session_id", "?")[:12]
            score = s.get("weighted_total", 0.0)
            trad = s.get("tradition", "?")
            mode = s.get("mode", "?")
            print(f"    {sid}  {score:.2f}  {trad:25s}  {mode}")

    else:
        print(f"Unknown sessions command: {args.sessions_command}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Resume command
# ---------------------------------------------------------------------------

def _cmd_resume(args: argparse.Namespace) -> None:
    import asyncio
    from vulca.pipeline.checkpoint import CheckpointStore
    from vulca.pipeline import execute, DEFAULT
    from vulca.pipeline.types import PipelineInput

    store = CheckpointStore()
    cp = store.load_checkpoint(args.session_id)
    if cp is None:
        print(f"  No checkpoint found for session {args.session_id}", file=sys.stderr)
        sys.exit(1)

    meta = cp["metadata"]
    rounds = cp["rounds"]
    if not rounds:
        print(f"  Checkpoint has no rounds to resume from", file=sys.stderr)
        sys.exit(1)

    from_round = args.from_round or len(rounds)
    target_round = None
    for r in rounds:
        if r["round_num"] == from_round:
            target_round = r
            break
    if target_round is None:
        print(
            f"  Round {from_round} not found in checkpoint "
            f"(available: {[r['round_num'] for r in rounds]})",
            file=sys.stderr,
        )
        sys.exit(1)

    provider = args.provider or meta.get("provider", "mock")
    print(f"\n  Resuming session {args.session_id} from round {from_round}")
    print(f"  Provider: {provider} | Tradition: {meta.get('tradition', 'default')}")
    print(f"  Last score: {target_round.get('weighted_total', 0.0):.3f}")

    pi = PipelineInput(
        subject=meta.get("subject", ""),
        intent=meta.get("intent", ""),
        tradition=meta.get("tradition", "default"),
        provider=provider,
        max_rounds=meta.get("max_rounds", 3),
    )

    ref_b64 = target_round.get("image_b64", "")
    if ref_b64:
        pi.node_params["generate"] = {"reference_image_b64": ref_b64}

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(execute(DEFAULT, pi))
    loop.close()

    print(f"\n  Resumed pipeline completed:")
    print(f"    Rounds: {result.total_rounds}")
    print(f"    Score: {result.weighted_total:.3f}")
    print(f"    Status: {result.status}")


# ---------------------------------------------------------------------------
# Dream command
# ---------------------------------------------------------------------------

def _cmd_dream(args: argparse.Namespace) -> None:
    import json as json_mod
    from vulca.digestion.dream import DreamConsolidator

    dc = DreamConsolidator(data_dir=getattr(args, "data_dir", "") or "")
    force = getattr(args, "force", False)
    as_json = getattr(args, "json", False)

    if not force and not dc.should_run():
        msg = {
            "status": "skipped",
            "reason": "Gate checks not met (< 24h elapsed or < 10 new sessions since last consolidation). Use --force to override.",
        }
        if as_json:
            print(json_mod.dumps(msg, indent=2))
        else:
            print("Dream consolidation skipped: gate checks not met.")
            print("  - Less than 24 hours since last run, or")
            print("  - Fewer than 10 new sessions accumulated.")
            print("  Use --force to bypass gate checks.")
        return

    if not as_json:
        print("Running Dream consolidation (Orient → Gather → Consolidate → Prune)...")

    result = dc.run()

    if as_json:
        print(json_mod.dumps(result, indent=2))
        return

    status = result.get("status", "unknown")
    if status == "completed":
        print(f"\nDream consolidation completed.")
        traditions = result.get("traditions_updated", [])
        print(f"  Traditions updated : {len(traditions)}")
        if traditions:
            for t in traditions:
                print(f"    - {t}")
        print(f"  Sessions analyzed  : {result.get('sessions_analyzed', 0)}")
        print(f"  Insights written   : {result.get('insights_written', 0)}")
        print(f"  History entries pruned: {result.get('pruned_count', 0)}")
    elif status == "failed":
        print(f"Dream consolidation failed: {result.get('error', 'unknown error')}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Dream consolidation status: {status}")


if __name__ == "__main__":
    main()
