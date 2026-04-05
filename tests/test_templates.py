"""Tests for custom YAML template loading and validation."""

import pytest
from pathlib import Path
from unittest.mock import patch

from moa.templates import (
    DecisionTemplate, _load_yaml_template, load_custom_templates,
    get_template, detect_template, list_templates, validate_template_file,
    TEMPLATES, _all_templates,
)


# ── Built-in templates ────────────────────────────────────────────────────────

def test_builtin_templates_exist():
    """Should have 3 built-in templates: hire, build, invest."""
    names = [t.name for t in TEMPLATES]
    assert "hire" in names
    assert "build" in names
    assert "invest" in names


def test_builtin_templates_have_required_fields():
    """Every built-in template should have all required fields populated."""
    for t in TEMPLATES:
        assert t.name
        assert t.description
        assert t.keywords
        assert t.debater_context
        assert t.judge_addendum
        assert t.research_queries


# ── YAML loading ──────────────────────────────────────────────────────────────

def test_load_yaml_template_valid(tmp_path):
    """Should load a valid YAML template."""
    yaml_file = tmp_path / "launch.yaml"
    yaml_file.write_text("""
name: launch
description: Product launch timing
keywords:
  - launch
  - ship
debater_context: This is a launch decision.
judge_addendum: Evaluate readiness and timing.
research_queries:
  - product launch timing
""")
    t = _load_yaml_template(yaml_file)
    assert t is not None
    assert t.name == "launch"
    assert t.description == "Product launch timing"
    assert "launch" in t.keywords
    assert "ship" in t.keywords
    assert "launch decision" in t.debater_context
    assert len(t.research_queries) == 1


def test_load_yaml_template_minimal(tmp_path):
    """Should load a template with only required fields."""
    yaml_file = tmp_path / "minimal.yaml"
    yaml_file.write_text("""
name: minimal
debater_context: Context here.
judge_addendum: Judge criteria here.
""")
    t = _load_yaml_template(yaml_file)
    assert t is not None
    assert t.name == "minimal"
    assert t.keywords == []
    assert t.research_queries == []
    assert t.description == ""


def test_load_yaml_template_missing_required(tmp_path):
    """Should return None if required fields are missing."""
    yaml_file = tmp_path / "bad.yaml"
    yaml_file.write_text("""
name: bad
description: Missing debater_context and judge_addendum
""")
    t = _load_yaml_template(yaml_file)
    assert t is None


def test_load_yaml_template_invalid_yaml(tmp_path):
    """Should return None for invalid YAML."""
    yaml_file = tmp_path / "broken.yaml"
    yaml_file.write_text("{{{{not yaml}}}}")
    t = _load_yaml_template(yaml_file)
    assert t is None


def test_load_yaml_template_nonexistent():
    """Should return None for nonexistent file."""
    t = _load_yaml_template(Path("/nonexistent/template.yaml"))
    assert t is None


# ── Custom template loading ───────────────────────────────────────────────────

def test_load_custom_templates_from_dir(tmp_path):
    """Should load all .yaml and .yml files from templates dir."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "a.yaml").write_text("name: alpha\ndebater_context: x\njudge_addendum: y\n")
    (templates_dir / "b.yml").write_text("name: beta\ndebater_context: x\njudge_addendum: y\n")
    (templates_dir / "not-yaml.txt").write_text("ignore me")

    with patch("moa.config.MOA_HOME", tmp_path):
        result = load_custom_templates()
        assert len(result) == 2
        names = {t.name for t in result}
        assert "alpha" in names
        assert "beta" in names


def test_load_custom_templates_empty_when_no_dir():
    """Should return empty list when templates dir doesn't exist."""
    with patch("moa.config.MOA_HOME", Path("/nonexistent/moa")):
        result = load_custom_templates()
        assert result == []


# ── Template override ─────────────────────────────────────────────────────────

def test_custom_template_overrides_builtin(tmp_path):
    """Custom template with same name as built-in should take priority."""
    custom = DecisionTemplate(
        name="hire",
        description="Custom hire template",
        keywords=["hire"],
        debater_context="Custom context",
        judge_addendum="Custom judge",
        research_queries=[],
    )
    with patch("moa.templates.load_custom_templates", return_value=[custom]):
        t = get_template("hire")
        assert t.description == "Custom hire template"


def test_all_templates_merges_correctly():
    """_all_templates should include custom + non-overridden built-ins."""
    custom = DecisionTemplate(
        name="hire",
        description="Custom hire",
        keywords=["hire"],
        debater_context="x",
        judge_addendum="y",
        research_queries=[],
    )
    with patch("moa.templates.load_custom_templates", return_value=[custom]):
        all_t = _all_templates()
        names = [t.name for t in all_t]
        # Custom hire should be there
        assert "hire" in names
        # Built-in build and invest should still be there
        assert "build" in names
        assert "invest" in names
        # Only one hire (custom, not built-in)
        assert names.count("hire") == 1
        # The hire template should be the custom one
        hire = next(t for t in all_t if t.name == "hire")
        assert hire.description == "Custom hire"


# ── detect_template with custom templates ─────────────────────────────────────

def test_detect_template_finds_custom():
    """detect_template should match custom template keywords."""
    custom = DecisionTemplate(
        name="launch",
        description="Launch timing",
        keywords=["launch", "ship", "release"],
        debater_context="x",
        judge_addendum="y",
        research_queries=[],
    )
    with patch("moa.templates.load_custom_templates", return_value=[custom]):
        t = detect_template("Should we launch the product?")
        assert t is not None
        assert t.name == "launch"


# ── Validation ────────────────────────────────────────────────────────────────

def test_validate_valid_template(tmp_path):
    """validate_template_file should pass for a complete template."""
    f = tmp_path / "good.yaml"
    f.write_text("name: test\ndebater_context: x\njudge_addendum: y\nkeywords:\n  - test\n")
    ok, errors = validate_template_file(f)
    assert ok is True
    assert len(errors) == 0


def test_validate_missing_fields(tmp_path):
    """validate_template_file should report missing required fields."""
    f = tmp_path / "bad.yaml"
    f.write_text("name: test\n")
    ok, errors = validate_template_file(f)
    assert ok is False
    assert any("Missing" in e for e in errors)


def test_validate_unknown_fields(tmp_path):
    """validate_template_file should warn about unknown fields."""
    f = tmp_path / "extra.yaml"
    f.write_text("name: test\ndebater_context: x\njudge_addendum: y\nfoo: bar\n")
    ok, errors = validate_template_file(f)
    assert ok is True  # unknown fields are warnings, not errors
    assert any("Unknown" in e for e in errors)


def test_validate_invalid_yaml(tmp_path):
    """validate_template_file should fail on invalid YAML."""
    f = tmp_path / "broken.yaml"
    f.write_text("{{{{not yaml}}}}")
    ok, errors = validate_template_file(f)
    assert ok is False
    assert any("Invalid YAML" in e for e in errors)


def test_validate_bad_keywords_type(tmp_path):
    """validate_template_file should flag non-list keywords."""
    f = tmp_path / "bad_kw.yaml"
    f.write_text("name: test\ndebater_context: x\njudge_addendum: y\nkeywords: not-a-list\n")
    ok, errors = validate_template_file(f)
    assert any("list" in e for e in errors)
