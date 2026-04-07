"""End-to-end tests for moa-debate.

Organized in tiers by cost and speed:

  Tier 1 (free, always runs):   CLI smoke tests via Typer's CliRunner.
                                  No model calls. Validates argparse, error paths,
                                  file I/O, and typer wiring.

  Tier 2 (~$0.001, opt-in):     Live single-model smoke tests against flash tier.
                                  Set MOA_E2E_LIVE=1 and GEMINI_API_KEY to run.

  Tier 3 (~$0.05-0.50, opt-in): Live multi-model tests (debate, compare, review).
                                  Set MOA_E2E_EXPENSIVE=1 plus needed API keys to run.

Run:
  pytest tests/test_e2e.py                                     # Tier 1 only
  MOA_E2E_LIVE=1 pytest tests/test_e2e.py                      # Tier 1 + 2
  MOA_E2E_EXPENSIVE=1 MOA_E2E_LIVE=1 pytest tests/test_e2e.py  # all tiers
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from moa.cli import app


# ══════════════════════════════════════════════════════════════════════════════
#  Skip markers
# ══════════════════════════════════════════════════════════════════════════════

SKIP_LIVE = pytest.mark.skipif(
    not os.environ.get("MOA_E2E_LIVE"),
    reason="Set MOA_E2E_LIVE=1 to run live model tests",
)

SKIP_EXPENSIVE = pytest.mark.skipif(
    not os.environ.get("MOA_E2E_EXPENSIVE"),
    reason="Set MOA_E2E_EXPENSIVE=1 to run expensive live tests (~$0.50+ per run)",
)

SKIP_RUBRIC = pytest.mark.skipif(
    not os.environ.get("MOA_E2E_RUBRIC"),
    reason="Set MOA_E2E_RUBRIC=1 to run LLM-as-judge rubric tests (~$0.02 per run)",
)


@pytest.fixture
def runner() -> CliRunner:
    """Typer CliRunner — invokes the CLI in-process."""
    return CliRunner(mix_stderr=False)


# ══════════════════════════════════════════════════════════════════════════════
#  TIER 1 — CLI smoke tests (no API calls, free, always runs)
# ══════════════════════════════════════════════════════════════════════════════

class TestT1HelpAndDiscovery:
    """Tier 1: Help output and command discovery."""

    def test_root_help_shows_commands(self, runner: CliRunner):
        """moa --help should list all commands including new ones."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "ask" in result.stdout
        assert "debate" in result.stdout
        assert "compare" in result.stdout
        assert "templates" in result.stdout
        assert "outcome" in result.stdout

    def test_compare_help(self, runner: CliRunner):
        """moa compare --help should show options."""
        result = runner.invoke(app, ["compare", "--help"])
        assert result.exit_code == 0
        assert "--single" in result.stdout
        assert "--ensemble" in result.stdout

    def test_debate_help(self, runner: CliRunner):
        """moa debate --help should show style and template flags."""
        result = runner.invoke(app, ["debate", "--help"])
        assert result.exit_code == 0
        assert "--style" in result.stdout
        assert "--template" in result.stdout

    def test_templates_help_shows_install_flag(self, runner: CliRunner):
        """moa templates --help should show --install-examples."""
        result = runner.invoke(app, ["templates", "--help"])
        assert result.exit_code == 0
        assert "--install-examples" in result.stdout


class TestT1TemplatesCommand:
    """Tier 1: templates command behaviors that don't need live models."""

    def test_templates_list_includes_builtins(self, runner: CliRunner):
        """moa templates should list built-in templates."""
        result = runner.invoke(app, ["templates"])
        assert result.exit_code == 0
        # Built-ins
        assert "hire" in result.stdout
        assert "build" in result.stdout
        assert "invest" in result.stdout

    def test_templates_validate_missing_file(self, runner: CliRunner):
        """moa templates validate on a nonexistent file should fail cleanly."""
        result = runner.invoke(app, ["templates", "/tmp/nonexistent-template-xyz.yaml"])
        # Should not raise — should report error in output
        assert "Invalid" in result.stdout or "Cannot read" in result.stdout or result.exit_code != 0

    def test_templates_validate_bad_yaml(self, runner: CliRunner, tmp_path: Path):
        """moa templates validate on bad YAML should report errors."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("not: valid: yaml: at all: [unclosed")
        result = runner.invoke(app, ["templates", str(bad_file)])
        assert "Invalid" in result.stdout or "❌" in result.stdout

    def test_templates_validate_missing_fields(self, runner: CliRunner, tmp_path: Path):
        """moa templates validate should detect missing required fields."""
        incomplete = tmp_path / "incomplete.yaml"
        incomplete.write_text("name: test\n")
        result = runner.invoke(app, ["templates", str(incomplete)])
        assert "Missing required" in result.stdout or "Invalid" in result.stdout

    def test_templates_validate_good_yaml(self, runner: CliRunner, tmp_path: Path):
        """moa templates validate on a valid YAML should succeed."""
        good = tmp_path / "good.yaml"
        good.write_text(
            "name: test-e2e\n"
            "description: test template\n"
            "keywords: [test, e2e]\n"
            "debater_context: This is a test decision with context.\n"
            "judge_addendum: Evaluate on these criteria:\\n- Test criterion\n"
        )
        result = runner.invoke(app, ["templates", str(good)])
        assert "Valid" in result.stdout or "✅" in result.stdout

    def test_templates_validates_all_example_files(self, runner: CliRunner):
        """Every shipped example template should pass validation via CLI."""
        examples_dir = Path(__file__).parent.parent / "templates" / "examples"
        for yaml_file in examples_dir.glob("*.yaml"):
            result = runner.invoke(app, ["templates", str(yaml_file)])
            assert "Valid" in result.stdout or "✅" in result.stdout, \
                f"{yaml_file.name} failed CLI validation: {result.stdout}"

    def test_templates_install_examples_to_tmpdir(
        self, runner: CliRunner, tmp_path: Path, monkeypatch
    ):
        """moa templates --install-examples should copy example files."""
        fake_home = tmp_path / "fake_moa_home"
        monkeypatch.setattr("moa.cli.MOA_HOME", fake_home)
        # ensure_moa_home() in cli.py uses config.MOA_HOME, patch both
        monkeypatch.setattr("moa.config.MOA_HOME", fake_home)

        result = runner.invoke(app, ["templates", "--install-examples"])
        assert result.exit_code == 0
        target = fake_home / "templates"
        assert target.exists()
        installed = list(target.glob("*.yaml"))
        assert len(installed) >= 6, f"Expected 6+ templates, found {len(installed)}"

    def test_templates_install_examples_idempotent(
        self, runner: CliRunner, tmp_path: Path, monkeypatch
    ):
        """Running install-examples twice should not error or duplicate."""
        fake_home = tmp_path / "fake_moa_home"
        monkeypatch.setattr("moa.cli.MOA_HOME", fake_home)
        monkeypatch.setattr("moa.config.MOA_HOME", fake_home)

        runner.invoke(app, ["templates", "--install-examples"])
        result = runner.invoke(app, ["templates", "--install-examples"])
        assert result.exit_code == 0
        assert "skip" in result.stdout.lower() or "already" in result.stdout.lower()


class TestT1CompareErrorPaths:
    """Tier 1: moa compare error handling without touching the network."""

    def test_compare_unknown_model(self, runner: CliRunner):
        """moa compare --single unknown-model should exit with error."""
        result = runner.invoke(
            app, ["compare", "--single", "fake-xyz-model-name", "test query"]
        )
        assert result.exit_code != 0
        assert "Unknown model" in result.stdout or "not available" in result.stdout

    def test_compare_ambiguous_model(self, runner: CliRunner):
        """Ambiguous partial match should fail with helpful message."""
        # "claude" matches multiple models
        result = runner.invoke(
            app, ["compare", "--single", "claude", "test query"]
        )
        # Either ambiguous or it picks exactly one — we just want no crash
        assert result.exit_code in (0, 1)
        if result.exit_code != 0:
            assert "Ambiguous" in result.stdout or "Unknown" in result.stdout or "not available" in result.stdout


class TestT1DebateErrorPaths:
    """Tier 1: moa debate error handling."""

    def test_debate_unknown_template(self, runner: CliRunner):
        """moa debate --template nonexistent should parse args without crashing.

        Mocks run_debate so the CLI never touches live models. Validates that
        the --template flag is wired correctly through argparse.
        """
        from unittest.mock import patch, AsyncMock
        from moa.models import QueryCost

        stub = {
            "response": "stub verdict",
            "rounds": [{"model-a": "x"}],
            "model_status": {"model-a": "ok"},
            "cost": QueryCost(tier="debate-lite"),
            "latency_ms": 100,
            "converged_at": None,
            "debate_style": "peer",
        }

        with patch("moa.cli.run_debate", new_callable=AsyncMock, return_value=stub):
            result = runner.invoke(
                app, ["debate", "--rounds", "1", "--template", "nonexistent-xyz", "test q"]
            )
            # Should not crash — stub verdict should render
            assert result.exit_code == 0
            assert "stub verdict" in result.stdout


class TestT1StatusAndHealth:
    """Tier 1: status/health commands should render without errors."""

    def test_status_command(self, runner: CliRunner):
        """moa status should list models and tiers."""
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0

    def test_health_command(self, runner: CliRunner):
        """moa health should render even when no health file exists."""
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0


# ══════════════════════════════════════════════════════════════════════════════
#  TIER 2 — Live single-model smoke tests (~$0.001 each, flash tier only)
# ══════════════════════════════════════════════════════════════════════════════

@SKIP_LIVE
class TestT2LiveFlash:
    """Tier 2: actually hit flash-tier models. Costs ~$0.001 per test."""

    @pytest.mark.asyncio
    async def test_live_call_model_flash(self):
        """call_model should return a response from Gemini Flash."""
        if not os.environ.get("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set")

        from moa.orchestrator import call_model
        from moa.models import GEMINI_FLASH

        result = await call_model(
            GEMINI_FLASH,
            [{"role": "user", "content": "Reply with just the number: 2+2="}],
            timeout=30,
        )
        assert result is not None
        assert result["content"]
        assert "4" in result["content"]
        assert result["input_tokens"] > 0
        assert result["output_tokens"] > 0
        assert result["cost_usd"] >= 0

    @pytest.mark.asyncio
    async def test_live_run_moa_flash(self):
        """run_moa with flash tier should return a response."""
        if not os.environ.get("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set")

        from moa.adaptive import run_moa

        result = await run_moa("What color is the sky? Answer in 3 words.", tier_name="flash")
        assert result["response"]
        assert "cost" in result
        assert result["cost"].estimated_cost_usd >= 0

    def test_live_cli_ask_flash(self, runner: CliRunner):
        """moa ask --tier flash should return a response via CLI."""
        if not os.environ.get("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set")

        result = runner.invoke(
            app, ["ask", "--tier", "flash", "What is 1+1? Reply with just the number."]
        )
        assert result.exit_code == 0
        assert "2" in result.stdout

    def test_live_verify_command(self, runner: CliRunner):
        """moa verify should ping available models."""
        result = runner.invoke(app, ["verify"])
        assert result.exit_code == 0
        # Should show at least one "OK" if keys are set
        assert "OK" in result.stdout or "passed" in result.stdout


# ══════════════════════════════════════════════════════════════════════════════
#  TIER 3 — Live multi-model tests (~$0.05-0.50 each)
# ══════════════════════════════════════════════════════════════════════════════

@SKIP_EXPENSIVE
class TestT3LiveDebate:
    """Tier 3: full debate + compare against real models. Costs ~$0.05-0.50 each.

    Each test asserts both pipeline correctness AND response quality via
    `quality_checks.assert_*_quality()` — structural format, pipeline invariants,
    and query-relevance checks. See tests/quality_checks.py.
    """

    @pytest.mark.asyncio
    async def test_live_peer_debate_pipeline(self):
        """Peer debate should converge and produce a quality verdict."""
        from moa.debate import run_peer_pipeline
        from tests.quality_checks import assert_peer_quality

        query = "Should I use tabs or spaces for Python indentation?"
        events = []
        result = await run_peer_pipeline(
            query, rounds_count=1, tier_name="lite", on_progress=events.append,
        )
        assert result["debate_style"] == "peer"
        assert len(result["rounds"]) >= 1

        # Quality checks: format, cost, evolution, diversity, relevance
        assert_peer_quality(result, original_query=query, tier="lite")

        # Typed events must have been emitted (peer pipeline contract)
        from moa.events import DebateEvent
        assert any(isinstance(e, DebateEvent) for e in events), \
            "peer pipeline did not emit any typed DebateEvent objects"

    @pytest.mark.asyncio
    async def test_live_adversarial_debate_with_template(self):
        """Adversarial debate with hire template should produce a structured verdict."""
        from moa.debate import run_adversarial_pipeline
        from tests.quality_checks import assert_adversarial_quality

        query = "Should we hire a senior backend engineer or two juniors for our 5-person team?"
        result = await run_adversarial_pipeline(
            query, rounds_count=1, tier_name="lite", template_name="hire",
        )
        assert result["debate_style"] == "adversarial"
        assert result["template"] == "hire"

        # Full structural + invariant checks (format, decision tree, confidence,
        # both sides, query relevance, cost, evolution, provider diversity)
        confidence = assert_adversarial_quality(result, original_query=query, tier="lite")
        assert 1 <= confidence <= 10

        # Template fidelity: judge output should reference hire-template criteria
        verdict_lower = result["response"].lower()
        hire_terms = ["ramp", "cost", "hire", "senior", "junior", "team"]
        matches = sum(1 for t in hire_terms if t in verdict_lower)
        assert matches >= 3, (
            f"verdict only references {matches}/{len(hire_terms)} hire-template terms "
            f"— template context may not be reaching the judge"
        )

    @pytest.mark.asyncio
    async def test_live_compare(self):
        """run_compare should produce side-by-side results with real models."""
        from moa.adaptive import run_compare
        from moa.models import GEMINI_FLASH
        from tests.quality_checks import assert_nonempty

        query = "What is the capital of France? Answer in one word."
        result = await run_compare(
            query, single_model=GEMINI_FLASH, ensemble_tier="lite",
        )

        # Both sides populated
        assert_nonempty(result["single_response"], "single_response")
        assert_nonempty(result["ensemble_response"], "ensemble_response")

        # Correctness: both should name Paris
        assert "paris" in result["single_response"].lower(), "single model got factual answer wrong"
        assert "paris" in result["ensemble_response"].lower(), "ensemble got factual answer wrong"

        # Agreement is symmetric and in [0, 1]
        assert 0 <= result["agreement_score"] <= 1

        # Ranking returns valid source
        assert result["best_source"] in ("single", "ensemble")

        # Cost tracking: single should be cheap, ensemble pays per proposer + aggregator
        assert result["single_cost_usd"] >= 0
        assert result["ensemble_cost_usd"] > 0, "ensemble cost should be >0 after running"
        # Ensemble should cost more than single-flash in the typical case
        assert result["ensemble_cost_usd"] >= result["single_cost_usd"]

    def test_live_cli_compare(self, runner: CliRunner):
        """moa compare CLI should render panels without error."""
        result = runner.invoke(
            app, ["compare", "--ensemble", "flash", "What is 2+2? Answer with just the number."]
        )
        assert result.exit_code == 0
        assert "Comparison Summary" in result.stdout or "Agreement" in result.stdout

    @pytest.mark.asyncio
    async def test_live_debate_html_export(self, tmp_path: Path):
        """Debate result should export to valid HTML."""
        from moa.debate import run_peer_pipeline
        from moa.export import export_html

        result = await run_peer_pipeline(
            "Is Python better than JavaScript?",
            rounds_count=1,
            tier_name="lite",
        )
        result["query"] = "Is Python better than JavaScript?"
        html = export_html(result)
        assert "<html" in html.lower()
        assert "</html>" in html.lower()
        assert result["response"] in html or len(html) > 500

    def test_live_cli_debate_peer(self, runner: CliRunner):
        """moa debate peer style should run end-to-end."""
        result = runner.invoke(
            app, ["debate", "--rounds", "1", "--tier", "lite", "Tabs or spaces?"]
        )
        assert result.exit_code == 0
        assert result.stdout  # Should have produced output


# ══════════════════════════════════════════════════════════════════════════════
#  TIER 3.5 — LLM-as-judge rubric scoring (~$0.02 per run)
# ══════════════════════════════════════════════════════════════════════════════

@SKIP_RUBRIC
class TestT35RubricQuality:
    """Tier 3.5: semantic quality scoring via cheap LLM judge.

    Runs a full debate, then asks Gemini Flash / Haiku to score the verdict
    1-5 on answers_question / considers_tradeoffs / actionable / specific.
    Gate: MOA_E2E_RUBRIC=1. Cost: ~$0.10 per full class run.

    Flaky: LLM judges are ~5% noisy. A single failure is not conclusive.
    """

    @pytest.mark.asyncio
    async def test_rubric_adversarial_hire_debate(self):
        """Adversarial hire-template verdict should pass the rubric."""
        from moa.debate import run_adversarial_pipeline
        from tests.quality_checks import (
            score_verdict_with_rubric, assert_rubric_scores_pass,
        )

        query = (
            "Should we hire a senior backend engineer for $180K "
            "or two juniors at $90K each for our 5-person startup?"
        )
        result = await run_adversarial_pipeline(
            query, rounds_count=1, tier_name="lite", template_name="hire",
        )
        scores = await score_verdict_with_rubric(query, result["response"])
        assert_rubric_scores_pass(scores, min_score=3)

    @pytest.mark.asyncio
    async def test_rubric_peer_debate(self):
        """Peer debate verdict should pass the rubric."""
        from moa.debate import run_peer_pipeline
        from tests.quality_checks import (
            score_verdict_with_rubric, assert_rubric_scores_pass,
        )

        query = "Should a small team use PostgreSQL or MongoDB for a new SaaS product?"
        result = await run_peer_pipeline(
            query, rounds_count=1, tier_name="lite",
        )
        scores = await score_verdict_with_rubric(query, result["response"])
        assert_rubric_scores_pass(scores, min_score=3)


# ══════════════════════════════════════════════════════════════════════════════
#  TIER 4 — Smoke test equivalence (reference to existing `moa test` command)
# ══════════════════════════════════════════════════════════════════════════════

@SKIP_EXPENSIVE
class TestT4MoaTestCommand:
    """Tier 4: the existing `moa test` command as a full-stack smoke test."""

    def test_moa_test_smoke_suite(self, runner: CliRunner):
        """moa test (default smoke suite) should run without crashing."""
        result = runner.invoke(app, ["test"])
        # Even if some tests fail due to rate limits, command should exit cleanly
        assert result.exit_code == 0
        assert "passed" in result.stdout.lower() or "failed" in result.stdout.lower()
