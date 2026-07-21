"""Public data types for VULCA evaluation results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillResult:
    """Result from a single skill evaluation (brand, audience, trend, etc.)."""

    skill: str
    score: float
    summary: str
    details: dict = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Complete evaluation result returned by ``vulca.evaluate()``."""

    score: float
    """Weighted total score (0-1)."""

    tradition: str
    """Cultural tradition used for evaluation."""

    dimensions: dict[str, float]
    """L1-L5 dimension scores."""

    rationales: dict[str, str]
    """L1-L5 dimension rationales (explanations)."""

    summary: str
    """Human-readable evaluation summary."""

    risk_level: str
    """Risk level: 'low', 'medium', or 'high'."""

    risk_flags: list[str]
    """List of cultural risk flags (if any)."""

    recommendations: list[str]
    """Actionable recommendations for improvement."""

    suggestions: dict[str, str] = field(default_factory=dict)
    """Per-dimension actionable suggestions from VLM (L1→suggestion text)."""

    deviation_types: dict[str, str] = field(default_factory=dict)
    """Per-dimension deviation classification: traditional|intentional_departure|experimental."""

    observations: dict[str, str] = field(default_factory=dict)
    """Per-dimension visual observations from VLM (factual, not evaluative)."""

    reference_techniques: dict[str, str] = field(default_factory=dict)
    """Per-dimension most relevant traditional technique name."""

    extra_scores: dict[str, float] = field(default_factory=dict)
    """Tradition-specific extra dimension scores (E1-E3)."""

    extra_rationales: dict[str, str] = field(default_factory=dict)
    """Tradition-specific extra dimension rationales."""

    extra_suggestions: dict[str, str] = field(default_factory=dict)
    """Tradition-specific extra dimension suggestions."""

    extra_observations: dict[str, str] = field(default_factory=dict)
    """Tradition-specific extra dimension observations."""

    eval_mode: str = "strict"
    """Evaluation mode: 'strict' (judge), 'reference' (advisor), or 'fusion' (multi-tradition)."""

    skills: dict[str, SkillResult] = field(default_factory=dict)
    """Results from extra skills (brand, audience, trend)."""

    intent_confidence: float = 0.0
    """Confidence of intent detection (0-1)."""

    latency_ms: int = 0
    """Total evaluation latency in milliseconds."""

    cost_usd: float = 0.0
    """Estimated API cost in USD."""

    raw: dict = field(default_factory=dict)
    """Raw response data for advanced usage."""

    @property
    def L1(self) -> float:
        """Visual Perception score."""
        return self.dimensions.get("L1", 0.0)

    @property
    def L2(self) -> float:
        """Technical Execution score."""
        return self.dimensions.get("L2", 0.0)

    @property
    def L3(self) -> float:
        """Cultural Context score."""
        return self.dimensions.get("L3", 0.0)

    @property
    def L4(self) -> float:
        """Critical Interpretation score."""
        return self.dimensions.get("L4", 0.0)

    @property
    def L5(self) -> float:
        """Philosophical Aesthetics score."""
        return self.dimensions.get("L5", 0.0)

    def __repr__(self) -> str:
        dims = " ".join(f"L{i}={self.dimensions.get(f'L{i}', 0):.2f}" for i in range(1, 6))
        return f"EvalResult(score={self.score:.2f}, tradition={self.tradition!r}, {dims})"


@dataclass
class CreateResult:
    """Result from a creation session via ``vulca.create()``."""

    session_id: str
    """Unique session identifier."""

    mode: str = "create"
    """Session mode: 'create' or 'evaluate'."""

    status: str = "completed"
    """Run status: 'completed' or 'waiting_human'."""

    interrupted_at: str = ""
    """Node name where pipeline was interrupted (HITL), empty if completed."""

    tradition: str = "default"
    """Cultural tradition used."""

    scores: dict[str, float] = field(default_factory=dict)
    """Dimension scores (if available)."""

    weighted_total: float = 0.0
    """Weighted total score."""

    best_candidate_id: str = ""
    """ID of the best generated candidate."""

    best_image_url: str = ""
    """URL of the best generated image."""

    best_image_b64: str = ""
    """Base64-encoded image data of the best candidate (if available)."""

    total_rounds: int = 0
    """Number of pipeline rounds completed."""

    rounds: list[dict] = field(default_factory=list)
    """Per-round snapshot data."""

    summary: str = ""
    """Human-readable summary."""

    recommendations: list[str] = field(default_factory=list)
    """Actionable recommendations."""

    risk_flags: list[str] = field(default_factory=list)
    """Risk and gate flags from evaluation, e.g. content_fidelity_failed."""

    content_fidelity_gate: dict = field(default_factory=dict)
    """Content-lock/artifact-boundary audit fields used by the final score gate."""

    evaluation_source: str = ""
    """Scoring source for the final candidate, e.g. vlm, mock, or mock_fallback."""

    evaluation_error: str = ""
    """Non-empty when scoring fell back after a VLM or parser error."""

    suggestions: dict[str, str] = field(default_factory=dict)
    """Per-dimension actionable suggestions (L1→suggestion text)."""

    deviation_types: dict[str, str] = field(default_factory=dict)
    """Per-dimension deviation classification."""

    eval_mode: str = "strict"
    """Evaluation mode used: strict|reference|fusion."""

    latency_ms: int = 0
    """Total latency in milliseconds."""

    cost_usd: float = 0.0
    """Estimated API cost in USD."""


    raw: dict = field(default_factory=dict)
    """Raw response data."""

    def __repr__(self) -> str:
        return (
            f"CreateResult(session_id={self.session_id!r}, mode={self.mode!r}, "
            f"status={self.status!r}, rounds={self.total_rounds}, tradition={self.tradition!r})"
        )


@dataclass
class InpaintResult:
    """Result from an inpainting operation."""

    bbox: dict
    """Bounding box as percentages: {"x": int, "y": int, "w": int, "h": int}."""

    variants: list[str]
    """Paths to variant images."""

    selected: int
    """Index of selected variant (0-based)."""

    blended: str
    """Path to final blended image."""

    original: str
    """Path to original image."""

    instruction: str
    """User's repaint instruction."""

    tradition: str
    """Tradition used for style consistency."""

    latency_ms: int = 0
    cost_usd: float = 0.0
