"""Tests for the slim pipeline engine, node protocol, and templates."""

from __future__ import annotations

import base64
import asyncio

import pytest

from vulca.pipeline.node import NodeContext, PipelineNode
from vulca.pipeline.nodes import DecideNode, EvaluateNode, GenerateNode
from vulca.pipeline.engine import execute, _resolve_nodes, _topo_order
from vulca.pipeline.templates import DEFAULT, FAST, CRITIQUE_ONLY, TEMPLATES
from vulca.pipeline.types import (
    PipelineDefinition,
    PipelineInput,
    PipelineOutput,
    RoundSnapshot,
    RunStatus,
)


# ── NodeContext ──────────────────────────────────────────────────────

class TestNodeContext:
    def test_defaults(self):
        ctx = NodeContext()
        assert ctx.subject == ""
        assert ctx.tradition == "default"
        assert ctx.provider == "mock"
        assert ctx.round_num == 0
        assert ctx.max_rounds == 3
        assert ctx.data == {}

    def test_set_get(self):
        ctx = NodeContext()
        ctx.set("image_b64", "abc123")
        assert ctx.get("image_b64") == "abc123"
        assert ctx.get("missing") is None
        assert ctx.get("missing", 42) == 42

    def test_fields(self):
        ctx = NodeContext(
            subject="test",
            intent="paint a cat",
            tradition="chinese_xieyi",
            provider="nb2",
        )
        assert ctx.subject == "test"
        assert ctx.intent == "paint a cat"
        assert ctx.tradition == "chinese_xieyi"
        assert ctx.provider == "nb2"


# ── PipelineNode ABC ────────────────────────────────────────────────

class TestPipelineNode:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            PipelineNode()  # type: ignore

    def test_subclass(self):
        class MyNode(PipelineNode):
            name = "my_node"
            async def run(self, ctx):
                return {"result": 42}

        node = MyNode()
        assert node.name == "my_node"


# ── GenerateNode ────────────────────────────────────────────────────

class TestGenerateNode:
    @pytest.mark.asyncio
    async def test_mock_generate(self):
        node = GenerateNode()
        ctx = NodeContext(subject="test artwork", provider="mock")
        result = await node.run(ctx)

        assert "image_b64" in result
        assert "image_mime" in result
        assert "candidate_id" in result
        assert result["image_mime"] in ("image/png", "image/svg+xml")
        assert len(result["image_b64"]) > 0
        assert len(result["candidate_id"]) == 12

    @pytest.mark.asyncio
    async def test_mock_deterministic(self):
        node = GenerateNode()
        ctx1 = NodeContext(subject="test", provider="mock", round_num=1)
        ctx2 = NodeContext(subject="test", provider="mock", round_num=1)
        r1 = await node.run(ctx1)
        r2 = await node.run(ctx2)
        assert r1["candidate_id"] == r2["candidate_id"]

    @pytest.mark.asyncio
    async def test_mock_different_rounds(self):
        node = GenerateNode()
        ctx1 = NodeContext(subject="test", provider="mock", round_num=1)
        ctx2 = NodeContext(subject="test", provider="mock", round_num=2)
        r1 = await node.run(ctx1)
        r2 = await node.run(ctx2)
        assert r1["candidate_id"] != r2["candidate_id"]

    def test_mock_generate_suppresses_sample_id_text(self):
        node = GenerateNode()
        ctx = NodeContext(subject="track1_0301", intent="draw branching lines")

        result = node._mock_generate(ctx)
        svg = base64.b64decode(result["image_b64"]).decode()

        assert "track1_0301" not in svg

    def test_generate_node_puts_content_lock_before_cultural_guidance(self):
        from vulca.content_lock import extract_content_lock
        from vulca.providers.base import ImageResult

        class CapturingProvider:
            def __init__(self):
                self.prompts = []

            async def generate(self, prompt, **kwargs):
                self.prompts.append(prompt)
                self.kwargs = kwargs
                return ImageResult(
                    image_b64="iVBORw0KGgo=",
                    mime="image/png",
                    metadata={"candidate_id": "captured"},
                )

        intent = (
            "Ink and wash painting of delicate bamboo and orchid grasses beside "
            "vertical Chinese calligraphy and red seals on aged paper."
        )
        provider = CapturingProvider()
        lock = extract_content_lock(intent)
        output = asyncio.run(
            execute(
                FAST,
                PipelineInput(
                    subject="track1_0002",
                    intent=intent,
                    tradition="chinese_xieyi",
                    provider="gemini",
                    image_provider=provider,
                    max_rounds=1,
                    node_params={"generate": {"content_lock": lock.to_dict()}},
                ),
            )
        )

        assert output.status == "completed"
        prompt = provider.prompts[0]
        assert prompt.index("NON-NEGOTIABLE CONTENT REQUIREMENTS") < prompt.index(intent)
        assert "Do not replace these subjects with mountains" in prompt

    def test_generate_node_does_not_send_sample_id_as_provider_subject_with_content_lock(self):
        from vulca.content_lock import extract_content_lock
        from vulca.providers.base import ImageResult

        class CapturingProvider:
            async def generate(self, prompt, **kwargs):
                self.prompt = prompt
                self.kwargs = kwargs
                return ImageResult(
                    image_b64="iVBORw0KGgo=",
                    mime="image/png",
                    metadata={"candidate_id": "captured"},
                )

        intent = (
            "Abstract hand-drawn branching lines fill a rectangular frame on graph "
            "paper in monochrome pencil style."
        )
        provider = CapturingProvider()
        lock = extract_content_lock(intent)
        output = asyncio.run(
            execute(
                FAST,
                PipelineInput(
                    subject="track1_0301",
                    intent=intent,
                    tradition="default",
                    provider="gemini",
                    image_provider=provider,
                    max_rounds=1,
                    node_params={"generate": {"content_lock": lock.to_dict()}},
                ),
            )
        )

        assert output.status == "completed"
        assert provider.kwargs["subject"] == ""
        assert "track1_0301" not in provider.prompt

    def test_generate_node_puts_artifact_boundary_before_content_requirements(self):
        from vulca.content_lock import extract_content_lock
        from vulca.providers.base import ImageResult

        class CapturingProvider:
            async def generate(self, prompt, **kwargs):
                self.prompt = prompt
                return ImageResult(
                    image_b64="iVBORw0KGgo=",
                    mime="image/png",
                    metadata={"candidate_id": "captured"},
                )

        intent = "Socialist Realism propaganda poster with workers and red banners."
        provider = CapturingProvider()
        lock = extract_content_lock(intent)
        output = asyncio.run(
            execute(
                FAST,
                PipelineInput(
                    subject="track1_0151",
                    intent=intent,
                    tradition="default",
                    provider="gemini",
                    image_provider=provider,
                    max_rounds=1,
                    node_params={"generate": {"content_lock": lock.to_dict()}},
                ),
            )
        )

        assert output.status == "completed"
        assert provider.prompt.index("ARTIFACT BOUNDARY REQUIREMENT") < provider.prompt.index(
            "NON-NEGOTIABLE CONTENT REQUIREMENTS"
        )
        assert "flat, front-facing propaganda poster artwork" in provider.prompt

    def test_generate_node_puts_relation_semantics_before_user_intent(self):
        from vulca.content_lock import extract_content_lock
        from vulca.providers.base import ImageResult

        class CapturingProvider:
            async def generate(self, prompt, **kwargs):
                self.prompt = prompt
                return ImageResult(
                    image_b64="iVBORw0KGgo=",
                    mime="image/png",
                    metadata={"candidate_id": "captured"},
                )

        intent = (
            "Wartime illustration of mounted soldiers beside fleeing civilians, "
            "burning village ruins, and aircraft overhead."
        )
        provider = CapturingProvider()
        lock = extract_content_lock(intent)
        output = asyncio.run(
            execute(
                FAST,
                PipelineInput(
                    subject="track1_0747",
                    intent=intent,
                    tradition="default",
                    provider="gemini",
                    image_provider=provider,
                    max_rounds=1,
                    node_params={"generate": {"content_lock": lock.to_dict()}},
                ),
            )
        )

        assert output.status == "completed"
        assert provider.prompt.index("RELATION SEMANTICS REQUIREMENTS") < provider.prompt.index(
            "USER INTENT TO PRESERVE VERBATIM"
        )
        assert "soldiers chasing civilians" in provider.prompt


# ── EvaluateNode ────────────────────────────────────────────────────

class TestEvaluateNode:
    @pytest.mark.asyncio
    async def test_mock_scores(self):
        node = EvaluateNode()
        ctx = NodeContext(
            subject="test", provider="mock", tradition="default", round_num=1
        )
        result = await node.run(ctx)

        assert "scores" in result
        assert "weighted_total" in result
        scores = result["scores"]
        for level in ("L1", "L2", "L3", "L4", "L5"):
            assert level in scores
            assert 0.0 <= scores[level] <= 1.0

        assert result["weighted_total"] > 0.0

    @pytest.mark.asyncio
    async def test_scores_increase_with_rounds(self):
        node = EvaluateNode()
        ctx1 = NodeContext(provider="mock", round_num=1)
        ctx2 = NodeContext(provider="mock", round_num=3)
        r1 = await node.run(ctx1)
        r2 = await node.run(ctx2)
        assert r2["weighted_total"] > r1["weighted_total"]

    @pytest.mark.asyncio
    async def test_tradition_weights_applied(self):
        node = EvaluateNode()
        ctx_xieyi = NodeContext(
            provider="mock", tradition="chinese_xieyi", round_num=1
        )
        ctx_default = NodeContext(
            provider="mock", tradition="default", round_num=1
        )
        r_xieyi = await node.run(ctx_xieyi)
        r_default = await node.run(ctx_default)
        # Different traditions → different weighted totals
        assert r_xieyi["weighted_total"] != r_default["weighted_total"]


# ── DecideNode ──────────────────────────────────────────────────────

class TestDecideNode:
    @pytest.mark.asyncio
    async def test_accept(self):
        node = DecideNode(accept_threshold=0.7)
        ctx = NodeContext(max_rounds=3, round_num=1)
        ctx.set("weighted_total", 0.85)
        result = await node.run(ctx)
        assert result["decision"] == "accept"

    @pytest.mark.asyncio
    async def test_rerun(self):
        node = DecideNode(accept_threshold=0.7)
        ctx = NodeContext(max_rounds=3, round_num=1)
        ctx.set("weighted_total", 0.5)
        result = await node.run(ctx)
        assert result["decision"] == "rerun"

    @pytest.mark.asyncio
    async def test_stop_at_max_rounds(self):
        node = DecideNode(accept_threshold=0.7)
        ctx = NodeContext(max_rounds=3, round_num=3)
        ctx.set("weighted_total", 0.5)
        result = await node.run(ctx)
        assert result["decision"] == "stop"

    @pytest.mark.asyncio
    async def test_custom_threshold(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as td:
            os.environ["VULCA_EVOLVED_DATA_DIR"] = td  # isolate from real evolution data
            try:
                node = DecideNode(accept_threshold=0.3)
                ctx = NodeContext(max_rounds=3, round_num=1)
                ctx.set("weighted_total", 0.35)
                result = await node.run(ctx)
                assert result["decision"] == "accept"
            finally:
                os.environ.pop("VULCA_EVOLVED_DATA_DIR", None)


# ── Templates ───────────────────────────────────────────────────────

class TestTemplates:
    def test_default_template(self):
        assert DEFAULT.name == "default"
        assert "generate" in DEFAULT.nodes
        assert "evaluate" in DEFAULT.nodes
        assert "decide" in DEFAULT.nodes
        assert DEFAULT.entry_point == "generate"
        assert DEFAULT.enable_loop is True

    def test_fast_template(self):
        assert FAST.name == "fast"
        assert FAST.enable_loop is False
        assert FAST.node_specs["decide"]["accept_threshold"] == 0.0

    def test_critique_only_template(self):
        assert CRITIQUE_ONLY.name == "critique_only"
        assert CRITIQUE_ONLY.entry_point == "evaluate"
        assert "generate" not in CRITIQUE_ONLY.nodes

    def test_templates_dict(self):
        assert {"default", "fast", "critique_only"}.issubset(set(TEMPLATES))

    def test_all_templates_are_frozen(self):
        for name, tmpl in TEMPLATES.items():
            with pytest.raises(AttributeError):
                tmpl.name = "changed"  # type: ignore


# ── Engine internals ────────────────────────────────────────────────

class TestEngineInternals:
    def test_resolve_nodes(self):
        nodes = _resolve_nodes(DEFAULT)
        assert set(nodes) == {"generate", "evaluate", "decide"}
        assert isinstance(nodes["generate"], GenerateNode)
        assert isinstance(nodes["evaluate"], EvaluateNode)
        assert isinstance(nodes["decide"], DecideNode)

    def test_resolve_legacy_names(self):
        legacy = PipelineDefinition(
            name="legacy",
            nodes=("scout", "draft", "critic", "queen"),
            edges=(("scout", "draft"), ("draft", "critic"), ("critic", "queen")),
            entry_point="scout",
        )
        nodes = _resolve_nodes(legacy)
        assert set(nodes) == {"scout", "draft", "critic", "queen"}

    def test_topo_order(self):
        order = _topo_order(DEFAULT)
        # generate must come before evaluate, evaluate before decide
        gen_idx = order.index("generate")
        eval_idx = order.index("evaluate")
        dec_idx = order.index("decide")
        assert gen_idx < eval_idx < dec_idx

    def test_unknown_node_raises(self):
        bad = PipelineDefinition(
            name="bad", nodes=("nonexistent",), edges=(), entry_point="nonexistent"
        )
        with pytest.raises(ValueError, match="Unknown node"):
            _resolve_nodes(bad)


# ── Full pipeline execution ─────────────────────────────────────────

class TestExecute:
    @pytest.mark.asyncio
    async def test_mock_pipeline_completes(self):
        pi = PipelineInput(subject="test artwork", provider="mock")
        result = await execute(DEFAULT, pi)

        assert isinstance(result, PipelineOutput)
        assert result.status in ("completed", "failed")
        assert result.total_rounds >= 1
        assert result.session_id
        assert len(result.rounds) >= 1
        assert len(result.events) > 0

    @pytest.mark.asyncio
    async def test_mock_pipeline_has_scores(self):
        pi = PipelineInput(subject="ink wash mountain", provider="mock")
        result = await execute(DEFAULT, pi)

        assert result.weighted_total > 0.0
        assert result.final_scores
        for level in ("L1", "L2", "L3", "L4", "L5"):
            assert level in result.final_scores

    @pytest.mark.asyncio
    async def test_fast_pipeline_single_round(self):
        pi = PipelineInput(subject="test", provider="mock", max_rounds=5)
        result = await execute(FAST, pi)
        # FAST has accept_threshold=0.0, so always accepts on first round
        assert result.total_rounds == 1

    @pytest.mark.asyncio
    async def test_rerun_loop(self):
        # High threshold forces rerun → stop at max_rounds
        high_threshold = PipelineDefinition(
            name="strict",
            entry_point="generate",
            nodes=("generate", "evaluate", "decide"),
            edges=(("generate", "evaluate"), ("evaluate", "decide")),
            enable_loop=True,
            node_specs={"decide": {"accept_threshold": 0.99}},
        )
        pi = PipelineInput(subject="test", provider="mock", max_rounds=3)
        result = await execute(high_threshold, pi)
        assert result.total_rounds == 3

    @pytest.mark.asyncio
    async def test_round2_receives_previous_image(self):
        """Round 2+ must get previous round's image as reference_image_b64."""
        captured_refs = []
        original_run = GenerateNode.run

        async def spy_run(self_node, ctx):
            captured_refs.append(ctx.get("reference_image_b64") or "")
            return await original_run(self_node, ctx)

        GenerateNode.run = spy_run
        try:
            high_threshold = PipelineDefinition(
                name="strict",
                entry_point="generate",
                nodes=("generate", "evaluate", "decide"),
                edges=(("generate", "evaluate"), ("evaluate", "decide")),
                enable_loop=True,
                node_specs={"decide": {"accept_threshold": 0.99}},
            )
            pi = PipelineInput(subject="test", provider="mock", max_rounds=3)
            result = await execute(high_threshold, pi)
            assert result.total_rounds == 3
            # Round 1: no reference (empty string)
            assert captured_refs[0] == ""
            # Round 2+: must have previous round's generated image
            assert captured_refs[1] != "", "Round 2 should receive Round 1's image as reference"
            assert captured_refs[2] != "", "Round 3 should receive Round 2's image as reference"
        finally:
            GenerateNode.run = original_run

    @pytest.mark.asyncio
    async def test_tradition_propagated(self):
        pi = PipelineInput(
            subject="test", provider="mock", tradition="chinese_xieyi"
        )
        result = await execute(DEFAULT, pi)
        assert result.tradition == "chinese_xieyi"

    @pytest.mark.asyncio
    async def test_output_to_dict(self):
        pi = PipelineInput(subject="test", provider="mock")
        result = await execute(DEFAULT, pi)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "session_id" in d
        assert "rounds" in d
        assert isinstance(d["rounds"], list)

    @pytest.mark.asyncio
    async def test_critique_only(self):
        pi = PipelineInput(subject="test", provider="mock")
        result = await execute(CRITIQUE_ONLY, pi)
        assert result.total_rounds == 1
        assert result.weighted_total > 0


# ── on_complete hook ────────────────────────────────────────────────

class TestOnComplete:
    @pytest.mark.asyncio
    async def test_on_complete_called(self):
        """on_complete hook is called after successful pipeline."""
        called = []

        async def hook(output):
            called.append(output.session_id)

        pi = PipelineInput(subject="test", provider="mock")
        await execute(DEFAULT, pi, on_complete=hook)
        assert len(called) == 1
        assert called[0]  # non-empty session_id

    @pytest.mark.asyncio
    async def test_on_complete_not_called_on_failure(self):
        """on_complete hook is NOT called when pipeline fails."""
        called = []

        async def hook(output):
            called.append(output.session_id)

        # Create a definition with an unknown node to force failure
        bad = PipelineDefinition(
            name="force_fail",
            entry_point="generate",
            nodes=("generate", "evaluate", "decide"),
            edges=(("generate", "evaluate"), ("evaluate", "decide")),
        )
        # Monkey-patch a node to raise
        from vulca.pipeline.nodes import GenerateNode
        original_run = GenerateNode.run

        async def _failing_run(self, ctx):
            raise RuntimeError("forced failure")

        GenerateNode.run = _failing_run
        try:
            pi = PipelineInput(subject="test", provider="mock")
            result = await execute(bad, pi, on_complete=hook)
            assert result.status == "failed"
            assert len(called) == 0
        finally:
            GenerateNode.run = original_run

    @pytest.mark.asyncio
    async def test_on_complete_error_is_non_fatal(self):
        """on_complete hook errors are logged but don't crash pipeline."""
        async def bad_hook(output):
            raise ValueError("hook exploded")

        pi = PipelineInput(subject="test", provider="mock")
        result = await execute(DEFAULT, pi, on_complete=bad_hook)
        assert result.status in ("completed",)
        assert result.total_rounds >= 1

    @pytest.mark.asyncio
    async def test_sync_on_complete_works(self):
        """A synchronous on_complete function also works."""
        called = []

        def sync_hook(output):
            called.append(output.session_id)

        pi = PipelineInput(subject="test", provider="mock")
        await execute(DEFAULT, pi, on_complete=sync_hook)
        assert len(called) == 1


# ── interrupt_before (HITL) ────────────────────────────────────────

class TestInterruptBefore:
    @pytest.mark.asyncio
    async def test_interrupt_before_evaluate(self):
        """Pipeline pauses before 'evaluate' node."""
        pi = PipelineInput(subject="test", provider="mock")
        result = await execute(DEFAULT, pi, interrupt_before={"evaluate"})
        assert result.status == "waiting_human"
        assert result.interrupted_at == "evaluate"
        assert result.total_rounds == 0  # no rounds completed yet

    @pytest.mark.asyncio
    async def test_interrupt_emits_human_required_event(self):
        """HUMAN_REQUIRED event is emitted when interrupting."""
        events_captured = []

        def capture(event):
            events_captured.append(event)

        pi = PipelineInput(subject="test", provider="mock")
        result = await execute(
            DEFAULT, pi,
            event_callback=capture,
            interrupt_before={"decide"},
        )
        assert result.status == "waiting_human"
        event_types = [e.event_type.value for e in events_captured]
        assert "human_required" in event_types

    @pytest.mark.asyncio
    async def test_no_interrupt_without_matching_nodes(self):
        """Pipeline runs normally if interrupt_before doesn't match any node."""
        pi = PipelineInput(subject="test", provider="mock")
        result = await execute(DEFAULT, pi, interrupt_before={"nonexistent_node"})
        assert result.status in ("completed",)
        assert result.interrupted_at == ""


# ── custom_weights via node_params ─────────────────────────────────

class TestCustomWeights:
    @pytest.mark.asyncio
    async def test_custom_weights_affect_total(self):
        """Passing custom_weights via node_params changes weighted_total."""
        pi_default = PipelineInput(subject="test", provider="mock")
        result_default = await execute(DEFAULT, pi_default)

        pi_custom = PipelineInput(
            subject="test", provider="mock",
            node_params={"evaluate": {"custom_weights": {
                "L1": 1.0, "L2": 0.0, "L3": 0.0, "L4": 0.0, "L5": 0.0,
            }}},
        )
        result_custom = await execute(DEFAULT, pi_custom)

        # Different weights → different weighted_total
        assert result_default.weighted_total != result_custom.weighted_total


# ── create() local mode ─────────────────────────────────────────────

class TestCreateLocal:
    @pytest.mark.asyncio
    async def test_acreate_local(self):
        from vulca.create import acreate

        result = await acreate("test artwork", provider="mock", mode="local")
        assert result.session_id
        assert result.mode == "create"
        assert result.total_rounds >= 1
        assert result.weighted_total > 0

    @pytest.mark.asyncio
    async def test_acreate_auto_mock(self):
        """auto mode should use local engine for mock provider."""
        from vulca.create import acreate

        result = await acreate("test", provider="mock", mode="auto")
        assert result.session_id
        assert result.total_rounds >= 1

    def test_create_sync_local(self):
        from vulca.create import create

        result = create("test artwork", provider="mock", mode="local")
        assert result.session_id
        assert result.total_rounds >= 1
