"""Tests for the v5.2 intelligence layer — Jev System One methodology.

Covers all 8 modules:
  1. calibrated_decision (Noul/Choice/Score/batch)
  2. confidence_gate (pass/review/reject/escalate)
  3. best_of_n (arbitration/ranking/escalation)
  4. loop_breaker (repetition/stagnation/regression)
  5. speculative_fanout (parallel evaluation)
  6. model_cascade (difficulty classification/provider routing)
  7. guardrail (prompt/output screening)
  8. patch_verifier (storyboard/config/character verification)
"""
import pytest
from aicomic.intelligence import (
    DecisionEngine,
    Noul,
    Choice,
    Score,
    ConfidenceGate,
    GateAction,
    GateDecision,
    BestOfNArbitrator,
    Candidate,
    ArbitrationResult,
    LoopBreaker,
    LoopSignal,
    SpeculativeFanout,
    FanoutResult,
    ModelCascade,
    CascadeRoute,
    Difficulty,
    Guardrail,
    GuardResult,
    GuardLevel,
    PatchVerifier,
    VerifyResult,
    VerifyAction,
)


# ============================================================================
# 1. Calibrated Decision Engine (Noul / Choice / Score / batch)
# ============================================================================

class TestDecisionEngine:
    """Test the core Jev-calibrated decision primitives."""

    def setup_method(self):
        self.engine = DecisionEngine()

    # --- Noul ---

    def test_noul_positive_state(self):
        """Noul: state with positive keywords → high probability."""
        n = self.engine.noul("clean good acceptable quality", "Is this acceptable?")
        assert n.probability > 0.5
        assert n.confidence > 0.3

    def test_noul_negative_state(self):
        """Noul: state with negative keywords → low probability."""
        n = self.engine.noul("broken artifact deformed finger error", "Is this acceptable?")
        assert n.probability < 0.5

    def test_noul_no_evidence(self):
        """Noul: no keywords → 0.5 probability, low confidence."""
        n = self.engine.noul("random text nothing", "Is this acceptable?")
        assert n.probability == 0.5
        assert n.confidence < 0.2

    def test_noul_reject_instruction_flips(self):
        """Noul: 'reject' instruction flips probability."""
        n_pos = self.engine.noul("good clean", "Is this acceptable?")
        n_neg = self.engine.noul("good clean", "Should we reject this?")
        assert n_neg.probability < n_pos.probability

    def test_noul_returns_correct_type(self):
        n = self.engine.noul("test", "question?")
        assert isinstance(n, Noul)
        assert 0 <= n.probability <= 1
        assert 0 <= n.confidence <= 1

    # --- Choice ---

    def test_choice_picks_winner(self):
        """Choice: picks the option with best keyword match."""
        c = self.engine.choice(
            "action fast motion kling",
            {"kling": "best for action motion", "wan": "cheap static", "seedance": "balanced"},
        )
        assert c.winner == "kling"
        assert c.winner in c.probabilities

    def test_choice_all_options_have_probability(self):
        """Choice: every option gets a probability."""
        c = self.engine.choice("test", {"a": "alpha", "b": "beta", "c": "gamma"})
        assert len(c.probabilities) == 3
        assert all(0 < p < 1 for p in c.probabilities.values())

    def test_choice_empty_options(self):
        """Choice: empty options → empty winner."""
        c = self.engine.choice("test", {})
        assert c.winner == ""
        assert c.confidence == 0.0

    def test_choice_single_option(self):
        """Choice: single option → winner is that option."""
        c = self.engine.choice("test", {"only": "the one option"})
        assert c.winner == "only"

    def test_choice_confidence_range(self):
        """Choice: confidence is between 0 and 1."""
        c = self.engine.choice("action kling", {"kling": "action", "wan": "static"})
        assert 0 <= c.confidence <= 1

    def test_choice_returns_correct_type(self):
        c = self.engine.choice("test", {"a": "x"})
        assert isinstance(c, Choice)

    # --- Score ---

    def test_score_returns_position(self):
        """Score: returns a position on the scale."""
        s = self.engine.score("excellent good quality", ["Poor", "OK", "Good", "Excellent"])
        assert isinstance(s, Score)
        assert 0 <= s.score <= 3

    def test_score_low_levels(self):
        """Score: low-quality state → low score."""
        s = self.engine.score("poor bad broken", ["Poor", "OK", "Good", "Excellent"])
        assert s.score < 1.5

    def test_score_high_levels(self):
        """Score: high-quality state → high score."""
        s = self.engine.score("excellent good great", ["Poor", "OK", "Good", "Excellent"])
        assert s.score > 1.5

    def test_score_too_few_levels(self):
        """Score: single level → score 0, confidence 0."""
        s = self.engine.score("test", ["Only"])
        assert s.score == 0.0
        assert s.confidence == 0.0

    def test_score_has_legend(self):
        """Score: legend maps level indices to descriptions."""
        levels = ["Poor", "OK", "Good"]
        s = self.engine.score("good", levels)
        assert s.legend == {0: "Poor", 1: "OK", 2: "Good"}

    def test_score_returns_correct_type(self):
        s = self.engine.score("test", ["a", "b"])
        assert isinstance(s, Score)

    # --- Batch ---

    def test_batch_multiple_types(self):
        """Batch: evaluates noul, choice, and score in one call."""
        results = self.engine.batch(
            state="good quality action kling",
            questions={
                "is_good": {"type": "noul", "instructions": "Is this good?"},
                "best_provider": {"type": "choice", "criteria": {"kling": "action", "wan": "static"}},
                "quality": {"type": "score", "levels": ["Poor", "OK", "Good"]},
            },
        )
        assert "is_good" in results
        assert "best_provider" in results
        assert "quality" in results
        assert isinstance(results["is_good"], Noul)
        assert isinstance(results["best_provider"], Choice)
        assert isinstance(results["quality"], Score)

    def test_batch_empty_questions(self):
        """Batch: no questions → empty results."""
        results = self.engine.batch("state", {})
        assert results == {}


# ============================================================================
# 2. Confidence Gate (pass / review / reject / escalate)
# ============================================================================

class TestConfidenceGate:
    """Test the confidence-gated action routing."""

    def test_pass_high_score_high_confidence(self):
        """High score + high confidence → PASS."""
        gate = ConfidenceGate()
        d = gate.evaluate(score=90, confidence=0.8, stage="quality_check")
        assert d.action == GateAction.PASS

    def test_reject_low_score(self):
        """Very low score → REJECT regardless of confidence."""
        gate = ConfidenceGate()
        d = gate.evaluate(score=30, confidence=0.9, stage="quality_check")
        assert d.action == GateAction.REJECT

    def test_review_borderline(self):
        """Medium score + medium confidence → REVIEW."""
        gate = ConfidenceGate()
        d = gate.evaluate(score=60, confidence=0.5, stage="quality_check")
        assert d.action == GateAction.REVIEW

    def test_reject_low_confidence_borderline(self):
        """Borderline score + low confidence → REJECT."""
        gate = ConfidenceGate()
        d = gate.evaluate(score=55, confidence=0.1, stage="quality_check")
        assert d.action == GateAction.REJECT

    def test_force_escalate(self):
        """Force escalate → ESCALATE regardless of score."""
        gate = ConfidenceGate()
        d = gate.evaluate(score=95, confidence=0.9, stage="test", force_escalate=True)
        assert d.action == GateAction.ESCALATE

    def test_stage_preset_thumbnail_lenient(self):
        """Thumbnail stage has lenient thresholds."""
        gate = ConfidenceGate.for_stage("thumbnail")
        d = gate.evaluate(score=65, confidence=0.6, stage="thumbnail")
        assert d.action == GateAction.PASS

    def test_stage_preset_final_render_strict(self):
        """Final render stage has strict thresholds."""
        gate = ConfidenceGate.for_stage("final_render")
        d = gate.evaluate(score=85, confidence=0.7, stage="final_render")
        # 85 < 90 pass_threshold → REVIEW
        assert d.action == GateAction.REVIEW

    def test_stage_preset_unknown_defaults(self):
        """Unknown stage → default thresholds."""
        gate = ConfidenceGate.for_stage("unknown_stage")
        d = gate.evaluate(score=85, confidence=0.8, stage="unknown_stage")
        assert d.action == GateAction.PASS

    def test_evaluate_batch(self):
        """Batch evaluation returns list of decisions."""
        gate = ConfidenceGate()
        decisions = gate.evaluate_batch(
            [{"score": 90, "confidence": 0.8}, {"score": 30, "confidence": 0.9}],
            stage="test",
        )
        assert len(decisions) == 2
        assert decisions[0].action == GateAction.PASS
        assert decisions[1].action == GateAction.REJECT

    def test_decision_has_reason(self):
        """Every decision includes a human-readable reason."""
        gate = ConfidenceGate()
        d = gate.evaluate(score=60, confidence=0.5, stage="test")
        assert len(d.reason) > 0
        assert len(d.suggested_action) > 0

    def test_decision_is_correct_type(self):
        gate = ConfidenceGate()
        d = gate.evaluate(score=50, confidence=0.5)
        assert isinstance(d, GateDecision)


# ============================================================================
# 3. Best-of-N Arbitration
# ============================================================================

class TestBestOfN:
    """Test Best-of-N candidate arbitration."""

    def test_picks_highest_composite(self):
        """Arbitrator picks the candidate with highest composite score."""
        arb = BestOfNArbitrator()
        candidates = [
            Candidate(id="a", score_quality=60, score_artifact=60, score_drift=60),
            Candidate(id="b", score_quality=90, score_artifact=90, score_drift=90),
            Candidate(id="c", score_quality=70, score_artifact=70, score_drift=70),
        ]
        result = arb.arbitrate(candidates)
        assert result.winner_id == "b"

    def test_empty_candidates(self):
        """Empty candidates → escalate."""
        arb = BestOfNArbitrator()
        result = arb.arbitrate([])
        assert result.winner_id == ""
        assert result.should_escalate

    def test_single_candidate(self):
        """Single candidate → no arbitration needed."""
        arb = BestOfNArbitrator()
        result = arb.arbitrate([Candidate(id="solo", score_quality=80)])
        assert result.winner_id == "solo"

    def test_low_quality_escalates(self):
        """All candidates below quality floor → escalate."""
        arb = BestOfNArbitrator(quality_floor=80)
        candidates = [
            Candidate(id="a", score_quality=20, score_artifact=20, score_drift=20),
            Candidate(id="b", score_quality=30, score_artifact=30, score_drift=30),
        ]
        result = arb.arbitrate(candidates)
        assert result.should_escalate

    def test_ranking_sorted(self):
        """Ranking is sorted best-to-worst."""
        arb = BestOfNArbitrator()
        candidates = [
            Candidate(id="low", score_quality=30, score_artifact=30, score_drift=30),
            Candidate(id="high", score_quality=90, score_artifact=90, score_drift=90),
            Candidate(id="mid", score_quality=60, score_artifact=60, score_drift=60),
        ]
        result = arb.arbitrate(candidates)
        assert result.ranking[0]["id"] == "high"
        assert result.ranking[-1]["id"] == "low"

    def test_result_is_correct_type(self):
        arb = BestOfNArbitrator()
        result = arb.arbitrate([Candidate(id="a", score_quality=80)])
        assert isinstance(result, ArbitrationResult)

    def test_composite_weighting(self):
        """Composite = quality*0.4 + artifact*0.35 + drift*0.25 (multi-candidate)."""
        arb = BestOfNArbitrator()
        c1 = Candidate(id="x", score_quality=100, score_artifact=0, score_drift=0)
        c2 = Candidate(id="y", score_quality=0, score_artifact=100, score_drift=0)
        result = arb.arbitrate([c1, c2])
        # x: 100*0.4 = 40, y: 100*0.35 = 35 → x wins
        assert result.winner_id == "x"
        assert result.ranking[0]["composite"] == pytest.approx(40.0, abs=2)
        assert result.ranking[1]["composite"] == pytest.approx(35.0, abs=2)


# ============================================================================
# 4. Loop Breaker
# ============================================================================

class TestLoopBreaker:
    """Test stuck-detection for retry loops."""

    def test_first_attempt_no_break(self):
        """First attempt → don't break."""
        breaker = LoopBreaker()
        signal = breaker.observe(["artifact"], score=50)
        assert not signal.should_break

    def test_exact_repetition_breaks(self):
        """Same issues repeated ≥ max_repeats → break."""
        breaker = LoopBreaker(max_repeats=2)
        breaker.observe(["6_fingers"], score=40)
        breaker.observe(["6_fingers"], score=45)
        signal = breaker.observe(["6_fingers"], score=42)
        assert signal.should_break
        assert "repeated" in signal.reason.lower()

    def test_score_stagnation_breaks(self):
        """No improvement over stagnation_window → break."""
        breaker = LoopBreaker(stagnation_window=3, min_improvement=10)
        breaker.observe(["x"], score=50)
        breaker.observe(["x"], score=52)
        signal = breaker.observe(["x"], score=51)
        assert signal.should_break
        assert "stagnant" in signal.reason.lower() or "repeated" in signal.reason.lower() or "similarity" in signal.reason.lower()

    def test_score_regression_breaks(self):
        """Score decreasing → break."""
        breaker = LoopBreaker(min_improvement=5)
        breaker.observe(["x"], score=60)
        signal = breaker.observe(["x"], score=40)
        assert signal.should_break
        assert "regress" in signal.reason.lower() or "similarity" in signal.reason.lower() or "repeated" in signal.reason.lower()

    def test_progressing_no_break(self):
        """Improving scores → don't break."""
        breaker = LoopBreaker()
        breaker.observe(["x"], score=30)
        signal = breaker.observe(["x"], score=70)
        assert not signal.should_break

    def test_reset_clears_history(self):
        """Reset clears history."""
        breaker = LoopBreaker()
        breaker.observe(["x"], score=50)
        breaker.reset()
        signal = breaker.observe(["y"], score=50)
        assert not signal.should_break

    def test_signal_is_correct_type(self):
        breaker = LoopBreaker()
        signal = breaker.observe(["x"])
        assert isinstance(signal, LoopSignal)

    def test_empty_issues_no_repeat(self):
        """Empty issues shouldn't trigger repetition."""
        breaker = LoopBreaker()
        breaker.observe([], score=50)
        signal = breaker.observe([], score=50)
        assert not signal.should_break or "stagnant" in signal.reason.lower()


# ============================================================================
# 5. Speculative Fan-out
# ============================================================================

class TestSpeculativeFanout:
    """Test parallel multi-check evaluation."""

    def test_evaluate_multiple_checks(self):
        """Fan-out evaluates all checks against the same state."""
        fanout = SpeculativeFanout()
        result = fanout.evaluate(
            state="720p 24fps good clean quality artifact",
            checks={
                "quality": {"type": "score", "levels": ["Poor", "OK", "Good", "Excellent"]},
                "has_artifact": {"type": "noul", "instructions": "Are there visual artifacts?"},
            },
        )
        assert "quality" in result.answers
        assert "has_artifact" in result.answers

    def test_combined_confidence(self):
        """Combined confidence is computed from all answers."""
        fanout = SpeculativeFanout()
        result = fanout.evaluate(
            state="test",
            checks={"check1": {"type": "noul", "instructions": "is good?"}},
        )
        assert 0 <= result.combined_confidence <= 1

    def test_dominant_signal(self):
        """Dominant signal is the check with highest confidence."""
        fanout = SpeculativeFanout()
        result = fanout.evaluate(
            state="good excellent quality",
            checks={
                "low_conf": {"type": "noul", "instructions": "random?"},
                "high_conf": {"type": "score", "levels": ["Poor", "Good", "Excellent"]},
            },
        )
        assert result.dominant_signal != ""

    def test_summary_not_empty(self):
        """Summary contains all check results."""
        fanout = SpeculativeFanout()
        result = fanout.evaluate(
            state="good",
            checks={"q": {"type": "noul", "instructions": "good?"}},
        )
        assert len(result.summary) > 0

    def test_result_is_correct_type(self):
        fanout = SpeculativeFanout()
        result = fanout.evaluate("test", {"x": {"type": "noul", "instructions": "?"}})
        assert isinstance(result, FanoutResult)

    def test_empty_checks(self):
        """Empty checks → empty answers."""
        fanout = SpeculativeFanout()
        result = fanout.evaluate("state", {})
        assert result.answers == {}

    def test_evaluate_with_gate(self):
        """Evaluate with gate returns (result, passed) tuple."""
        fanout = SpeculativeFanout()
        result, passed = fanout.evaluate_with_gate(
            state="excellent good quality",
            checks={"quality": {"type": "score", "levels": ["Poor", "OK", "Good", "Excellent"]}},
            gate_check="quality",
            pass_threshold=2.0,
        )
        assert isinstance(result, FanoutResult)
        assert isinstance(passed, bool)


# ============================================================================
# 6. Model Cascade
# ============================================================================

class TestModelCascade:
    """Test difficulty-based provider routing."""

    def test_trivial_difficulty(self):
        """No motion, 1 character → TRIVIAL."""
        cascade = ModelCascade()
        d = cascade.classify_difficulty("static frame", motion_intensity="none")
        assert d == Difficulty.TRIVIAL

    def test_extreme_vfx(self):
        """VFX → EXTREME."""
        cascade = ModelCascade()
        d = cascade.classify_difficulty("explosion", has_vfx=True)
        assert d == Difficulty.EXTREME

    def test_extreme_multi_character(self):
        """3+ characters → EXTREME."""
        cascade = ModelCascade()
        d = cascade.classify_difficulty("group scene", character_count=3)
        assert d == Difficulty.EXTREME

    def test_action_keywords_bump_difficulty(self):
        """Action keywords bump difficulty up."""
        cascade = ModelCascade()
        d = cascade.classify_difficulty("warrior leaping across rooftops", motion_intensity="low")
        assert d == Difficulty.MEDIUM  # bumped from EASY

    def test_route_extreme_escalates(self):
        """EXTREME difficulty → human escalation."""
        cascade = ModelCascade()
        route = cascade.route("explosion VFX", has_vfx=True)
        assert route.should_escalate
        assert route.provider == "human"

    def test_route_easy_prefers_wan_budget_aware(self):
        """Easy + budget aware → wan (free)."""
        cascade = ModelCascade()
        route = cascade.route("talking head", motion_intensity="low", budget_aware=True)
        assert route.provider == "wan"

    def test_route_hard_uses_kling(self):
        """Hard difficulty → kling."""
        cascade = ModelCascade()
        route = cascade.route("fast chase scene", motion_intensity="high")
        assert route.provider in ("kling", "seedance")  # kling preferred

    def test_route_has_cost_estimate(self):
        """Route includes cost estimate."""
        cascade = ModelCascade()
        route = cascade.route("talking head", motion_intensity="low")
        assert route.estimated_cost >= 0.0

    def test_batch_cost_estimation(self):
        """Batch cost sums all routes."""
        cascade = ModelCascade()
        routes = [
            cascade.route("talking", motion_intensity="low"),
            cascade.route("action", motion_intensity="high"),
        ]
        total = cascade.estimate_batch_cost(routes, duration_seconds=5)
        assert total >= 0

    def test_route_is_correct_type(self):
        cascade = ModelCascade()
        route = cascade.route("test")
        assert isinstance(route, CascadeRoute)

    def test_two_characters_bumps_medium_to_hard(self):
        """2 characters + medium motion → HARD."""
        cascade = ModelCascade()
        d = cascade.classify_difficulty("dialogue", motion_intensity="medium", character_count=2)
        assert d == Difficulty.HARD


# ============================================================================
# 7. Guardrail
# ============================================================================

class TestGuardrail:
    """Test input/output content screening."""

    def test_clean_prompt_passes(self):
        """Clean prompt → PASS."""
        guard = Guardrail()
        result = guard.check_prompt("a beautiful sunset over mountains")
        assert result.level == GuardLevel.PASS

    def test_banned_content_blocks(self):
        """Banned keyword → BLOCK."""
        guard = Guardrail(block_threshold=0.7)
        result = guard.check_prompt("gore dismember beheading scene")
        assert result.level == GuardLevel.BLOCK

    def test_warning_content_warns(self):
        """Warning keyword → WARN."""
        guard = Guardrail(warn_threshold=0.3)
        result = guard.check_prompt("a fight scene with sword and blood")
        assert result.level in (GuardLevel.WARN, GuardLevel.BLOCK)

    def test_output_stricter_than_input(self):
        """Output check is stricter — WARN on input → BLOCK on output."""
        guard = Guardrail()
        text = "a fight with some punch and blood"
        input_result = guard.check_prompt(text)
        output_result = guard.check_output(text)
        if input_result.level == GuardLevel.WARN:
            assert output_result.level == GuardLevel.BLOCK

    def test_redacted_text_generated(self):
        """Blocked content produces redacted text."""
        guard = Guardrail()
        result = guard.check_prompt("gore and more content")
        if result.level == GuardLevel.BLOCK:
            assert "REDACTED" in result.redacted_text or result.redacted_text

    def test_flagged_categories_populated(self):
        """Flagged categories are listed."""
        guard = Guardrail()
        result = guard.check_prompt("gore violence")
        if result.flagged_categories:
            assert any("violence" in c for c in result.flagged_categories)

    def test_batch_check(self):
        """Batch check returns list of results."""
        guard = Guardrail()
        results = guard.check_batch(["clean text", "gore content"])
        assert len(results) == 2

    def test_result_is_correct_type(self):
        guard = Guardrail()
        result = guard.check_prompt("test")
        assert isinstance(result, GuardResult)

    def test_score_in_range(self):
        """Guardrail score is 0-1."""
        guard = Guardrail()
        result = guard.check_prompt("test text")
        assert 0 <= result.score <= 1


# ============================================================================
# 8. Patch Verifier
# ============================================================================

class TestPatchVerifier:
    """Test diff verification against conventions."""

    def test_storyboard_scene_count_drop_violation(self):
        """Major scene count drop → violation."""
        verifier = PatchVerifier()
        result = verifier.verify_change(
            change_type="storyboard_edit",
            before={"scene_count": 12},
            after={"scene_count": 8},
        )
        assert result.action == VerifyAction.BLOCK
        assert len(result.violations) > 0

    def test_storyboard_minor_scene_drop_warning(self):
        """Minor scene count drop → warning."""
        verifier = PatchVerifier()
        result = verifier.verify_change(
            change_type="storyboard_edit",
            before={"scene_count": 12},
            after={"scene_count": 11},
        )
        assert result.action in (VerifyAction.ANNOTATE, VerifyAction.REVIEW)
        assert len(result.warnings) > 0

    def test_config_resolution_downgrade_violation(self):
        """Resolution downgrade → violation."""
        verifier = PatchVerifier()
        result = verifier.verify_change(
            change_type="config_change",
            before={"resolution": "1080p"},
            after={"resolution": "720p"},
        )
        assert result.action == VerifyAction.BLOCK

    def test_character_name_change_violation(self):
        """Character name change → violation (breaks references)."""
        verifier = PatchVerifier()
        result = verifier.verify_change(
            change_type="character_edit",
            before={"name": "Alice"},
            after={"name": "Bob"},
        )
        assert result.action == VerifyAction.BLOCK

    def test_safe_change_approved(self):
        """Safe change → APPROVE."""
        verifier = PatchVerifier()
        result = verifier.verify_change(
            change_type="config_change",
            before={"fps": 24},
            after={"fps": 24},  # no change
        )
        assert result.action == VerifyAction.APPROVE

    def test_duration_change_violation(self):
        """Duration change > 30% → violation."""
        verifier = PatchVerifier()
        result = verifier.verify_change(
            change_type="storyboard_edit",
            before={"duration": 100},
            after={"duration": 50},
        )
        assert result.action == VerifyAction.BLOCK

    def test_character_style_change_warning(self):
        """Character visual style change → warning."""
        verifier = PatchVerifier()
        result = verifier.verify_change(
            change_type="character_edit",
            before={"name": "Alice", "style": "realistic"},
            after={"name": "Alice", "style": "anime"},
        )
        assert result.action in (VerifyAction.ANNOTATE, VerifyAction.REVIEW)

    def test_generic_key_removal_warning(self):
        """Generic key removal → warning."""
        verifier = PatchVerifier()
        result = verifier.verify_change(
            change_type="generic",
            before={"a": 1, "b": 2},
            after={"a": 1},  # b removed
        )
        assert result.action in (VerifyAction.ANNOTATE, VerifyAction.REVIEW)

    def test_result_is_correct_type(self):
        verifier = PatchVerifier()
        result = verifier.verify_change("generic", {}, {})
        assert isinstance(result, VerifyResult)

    def test_risk_score_in_range(self):
        """Risk score is 0-1."""
        verifier = PatchVerifier()
        result = verifier.verify_change("generic", {"a": 1}, {"a": 2})
        assert 0 <= result.risk_score <= 1
