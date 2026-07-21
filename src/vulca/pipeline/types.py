"""Pipeline subsystem types -- input/output, state, definitions, events."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Phase 0 multi-layer foundation: ceiling lifted from 8 → 20 to support
# hierarchical semantic decomposition (face parts, per-person layers).
MAX_LAYERS = 20


class RunStatus(str, Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"


class EventType(str, Enum):
    """Pipeline event types for streaming progress."""

    STAGE_STARTED = "stage_started"
    STAGE_PROGRESS = "stage_progress"
    STAGE_COMPLETED = "stage_completed"
    DECISION_MADE = "decision_made"
    HUMAN_REQUIRED = "human_required"
    HUMAN_RECEIVED = "human_received"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"
    SESSION_DIGEST = "session_digest"
    SUBSTAGE_STARTED = "substage_started"
    SUBSTAGE_COMPLETED = "substage_completed"


@dataclass
class PipelineEvent:
    """A single event emitted during pipeline execution."""

    event_type: EventType
    stage: str = ""
    round_num: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "stage": self.stage,
            "round_num": self.round_num,
            "payload": self.payload,
            "timestamp_ms": self.timestamp_ms,
        }


@dataclass
class RoundSnapshot:
    """Snapshot of a single pipeline round."""

    round_num: int
    candidates_generated: int = 0
    best_candidate_id: str = ""
    weighted_total: float = 0.0
    dimension_scores: dict[str, float] = field(default_factory=dict)
    decision: str = ""
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_num": self.round_num,
            "candidates_generated": self.candidates_generated,
            "best_candidate_id": self.best_candidate_id,
            "weighted_total": self.weighted_total,
            "dimension_scores": self.dimension_scores,
            "decision": self.decision,
            "latency_ms": self.latency_ms,
        }


@dataclass
class PipelineInput:
    """Input to a VULCA creation/evaluation pipeline."""

    subject: str
    intent: str = ""
    tradition: str = "default"
    provider: str = "nb2"
    api_key: str = ""
    max_rounds: int = 3
    max_cost_usd: float = 2.0
    template: str = "default"
    node_params: dict[str, dict] = field(default_factory=dict)
    eval_mode: str = "strict"
    """Evaluation mode: strict|reference|fusion."""
    # Custom ImageProvider instance (not serialized; overrides provider lookup)
    image_provider: Any = field(default=None, repr=False)
    layered: bool = False             # Use LAYERED template for structured creation
    no_cache: bool = False            # v0.13: disable layered sidecar cache
    strict: bool = False              # v0.13: any failed layer fails the run
    max_layers: int = 8               # v0.13: cap planned layer count (1..MAX_LAYERS)
    output_dir: str = ""              # v0.13: write composite+manifest here (LAYERED)

    def __post_init__(self) -> None:
        if not 1 <= self.max_layers <= MAX_LAYERS:
            raise ValueError(
                f"max_layers must be in 1..{MAX_LAYERS}, got {self.max_layers}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "intent": self.intent,
            "tradition": self.tradition,
            "provider": self.provider,
            "max_rounds": self.max_rounds,
            "max_cost_usd": self.max_cost_usd,
            "template": self.template,
        }


@dataclass
class PipelineOutput:
    """Output from a completed pipeline run."""

    session_id: str
    status: str = "completed"
    tradition: str = "default"
    best_candidate_id: str = ""
    best_image_url: str = ""
    final_scores: dict[str, float] = field(default_factory=dict)
    weighted_total: float = 0.0
    rounds: list[RoundSnapshot] = field(default_factory=list)
    events: list[PipelineEvent] = field(default_factory=list)
    total_rounds: int = 0
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    content_fidelity_gate: dict[str, Any] = field(default_factory=dict)
    evaluation_source: str = ""
    evaluation_error: str = ""
    interrupted_at: str = ""
    summary: str = ""
    # Preserved for HITL resume — original user inputs
    original_intent: str = ""
    original_provider: str = ""
    # v0.13 P0.1 #4: LAYERED non-strict runs surface a partial flag here so
    # callers don't have to re-read manifest.json to know the artifact is
    # partially degraded.
    layered_partial: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "tradition": self.tradition,
            "best_candidate_id": self.best_candidate_id,
            "best_image_url": self.best_image_url,
            "final_scores": self.final_scores,
            "weighted_total": self.weighted_total,
            "rounds": [r.to_dict() for r in self.rounds],
            "total_rounds": self.total_rounds,
            "total_latency_ms": self.total_latency_ms,
            "total_cost_usd": self.total_cost_usd,
            "risk_flags": self.risk_flags,
            "recommendations": self.recommendations,
            "content_fidelity_gate": self.content_fidelity_gate,
            "evaluation_source": self.evaluation_source,
            "evaluation_error": self.evaluation_error,
            "interrupted_at": self.interrupted_at,
            "summary": self.summary,
            "original_intent": self.original_intent,
            "original_provider": self.original_provider,
            "layered_partial": self.layered_partial,
        }


@dataclass(frozen=True)
class PipelineDefinition:
    """Immutable definition of a pipeline topology.

    This is a first-class evolvable object -- pipelines can be created,
    modified, and evolved by the system or by users.
    """

    name: str
    display_name: str = ""
    description: str = ""
    entry_point: str = "scout"
    nodes: tuple[str, ...] = ("scout", "draft", "critic", "queen")
    edges: tuple[tuple[str, str], ...] = (
        ("scout", "draft"),
        ("draft", "critic"),
        ("critic", "queen"),
    )
    enable_loop: bool = True
    interrupt_before: tuple[str, ...] = ()
    node_specs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "entry_point": self.entry_point,
            "nodes": list(self.nodes),
            "edges": [list(e) for e in self.edges],
            "enable_loop": self.enable_loop,
        }
