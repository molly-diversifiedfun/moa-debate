"""Tests for example templates shipped with the package."""

import pytest
from pathlib import Path

from moa.templates import validate_template_file, _load_yaml_template, DecisionTemplate


EXAMPLES_DIR = Path(__file__).parent.parent / "templates" / "examples"
EXPECTED_TEMPLATES = ["startup", "launch", "strategy", "acquire", "pivot", "sunset"]


def test_examples_directory_exists():
    """templates/examples/ should exist and contain YAML files."""
    assert EXAMPLES_DIR.is_dir(), f"Missing: {EXAMPLES_DIR}"
    yamls = list(EXAMPLES_DIR.glob("*.yaml"))
    assert len(yamls) >= 6, f"Expected 6+ templates, found {len(yamls)}"


@pytest.mark.parametrize("name", EXPECTED_TEMPLATES)
def test_example_template_exists(name: str):
    """Each expected template file should exist."""
    path = EXAMPLES_DIR / f"{name}.yaml"
    assert path.exists(), f"Missing template: {path}"


@pytest.mark.parametrize("name", EXPECTED_TEMPLATES)
def test_example_template_validates(name: str):
    """Each example template should pass validation."""
    path = EXAMPLES_DIR / f"{name}.yaml"
    ok, errors = validate_template_file(path)
    assert ok, f"{name}.yaml failed validation: {errors}"


@pytest.mark.parametrize("name", EXPECTED_TEMPLATES)
def test_example_template_loads(name: str):
    """Each example template should load into a DecisionTemplate."""
    path = EXAMPLES_DIR / f"{name}.yaml"
    template = _load_yaml_template(path)
    assert template is not None, f"{name}.yaml failed to load"
    assert isinstance(template, DecisionTemplate)
    assert template.name == name


@pytest.mark.parametrize("name", EXPECTED_TEMPLATES)
def test_example_template_has_required_content(name: str):
    """Each template should have non-empty required fields."""
    path = EXAMPLES_DIR / f"{name}.yaml"
    template = _load_yaml_template(path)
    assert template.name, "name is empty"
    assert template.description, "description is empty"
    assert len(template.keywords) >= 3, f"Too few keywords: {len(template.keywords)}"
    assert len(template.debater_context) >= 50, "debater_context too short"
    assert len(template.judge_addendum) >= 200, "judge_addendum too short"


@pytest.mark.parametrize("name", EXPECTED_TEMPLATES)
def test_example_template_has_research_queries(name: str):
    """Each template should include research queries."""
    path = EXAMPLES_DIR / f"{name}.yaml"
    template = _load_yaml_template(path)
    assert len(template.research_queries) >= 1, "No research queries"


def test_no_duplicate_template_names():
    """All example templates should have unique names."""
    names = []
    for path in EXAMPLES_DIR.glob("*.yaml"):
        template = _load_yaml_template(path)
        if template:
            names.append(template.name)
    assert len(names) == len(set(names)), f"Duplicate names: {names}"


def test_no_overlap_with_builtin_names():
    """Example templates should not override built-in templates."""
    from moa.templates import TEMPLATES
    builtin_names = {t.name for t in TEMPLATES}
    for path in EXAMPLES_DIR.glob("*.yaml"):
        template = _load_yaml_template(path)
        if template:
            assert template.name not in builtin_names, \
                f"{template.name} conflicts with built-in template"
