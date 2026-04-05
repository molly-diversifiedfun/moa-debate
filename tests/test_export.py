"""Tests for debate transcript export (HTML and markdown)."""

from moa.export import export_html, export_markdown, _escape, _md_to_html_basic
from moa.models import QueryCost


def _make_result(**overrides):
    """Create a minimal debate result dict for testing."""
    base = {
        "query": "Should we build auth in-house?",
        "response": "## TL;DR\nUse Auth0.\n\n## Confidence: 7/10\nModerate confidence.",
        "rounds": [
            {"angel": "Auth gives control.", "devil": "Auth is solved."},
            {"angel": "Concedes maintenance.", "devil": "Lock-in is real."},
        ],
        "model_status": {},
        "cost": QueryCost(tier="adversarial-pro", estimated_cost_usd=0.34),
        "latency_ms": 45000,
        "converged_at": None,
        "debate_style": "adversarial",
        "research_grounded": True,
        "research_sources": ["https://auth0.com/pricing", "https://example.com/comparison"],
        "research_context": "",
        "angel_model": "claude-opus",
        "devil_model": "gpt-5",
        "template": "build",
    }
    base.update(overrides)
    return base


# ── HTML export ──────────────────────────────────────────────────────────────

def test_export_html_returns_string():
    """export_html should return a non-empty HTML string."""
    result = _make_result()
    html = export_html(result)
    assert isinstance(html, str)
    assert len(html) > 500


def test_export_html_contains_doctype():
    """HTML export should be a complete document."""
    html = export_html(_make_result())
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html


def test_export_html_contains_query():
    """HTML should include the debate question."""
    html = export_html(_make_result())
    assert "auth in-house" in html


def test_export_html_contains_models():
    """HTML should show which models debated."""
    html = export_html(_make_result())
    assert "claude-opus" in html
    assert "gpt-5" in html


def test_export_html_contains_verdict():
    """HTML should include the verdict."""
    html = export_html(_make_result())
    assert "Use Auth0" in html


def test_export_html_contains_sources():
    """HTML should list research sources as links."""
    html = export_html(_make_result())
    assert "auth0.com/pricing" in html
    assert "href=" in html


def test_export_html_contains_rounds():
    """HTML should include round content."""
    html = export_html(_make_result())
    assert "Opening Arguments" in html
    assert "Auth gives control" in html
    assert "Auth is solved" in html


def test_export_html_has_collapsible_rounds():
    """HTML should have round-header elements for collapsibility."""
    html = export_html(_make_result())
    assert "round-header" in html
    assert "collapsed" in html  # later rounds should be collapsed


def test_export_html_shows_badges():
    """HTML should show style and template badges."""
    html = export_html(_make_result())
    assert "Adversarial" in html
    assert "build" in html


def test_export_html_converged_badge():
    """HTML should show convergence badge when converged."""
    html = export_html(_make_result(converged_at=2))
    assert "Converged" in html


def test_export_html_no_sources():
    """HTML should handle no sources gracefully."""
    html = export_html(_make_result(research_sources=[]))
    assert "Sources" not in html


def test_export_html_peer_style():
    """HTML should handle peer debate style."""
    result = _make_result(
        debate_style="peer",
        rounds=[{"model-a": "Response A", "model-b": "Response B"}],
    )
    html = export_html(result)
    assert "Peer" in html


# ── Markdown export ──────────────────────────────────────────────────────────

def test_export_markdown_returns_string():
    """export_markdown should return a non-empty string."""
    md = export_markdown(_make_result())
    assert isinstance(md, str)
    assert len(md) > 100


def test_export_markdown_contains_query():
    """Markdown should start with the question."""
    md = export_markdown(_make_result())
    assert "auth in-house" in md


def test_export_markdown_contains_models():
    """Markdown should show which models debated."""
    md = export_markdown(_make_result())
    assert "claude-opus" in md
    assert "gpt-5" in md


def test_export_markdown_contains_verdict():
    """Markdown should include the verdict."""
    md = export_markdown(_make_result())
    assert "Use Auth0" in md


def test_export_markdown_contains_sources():
    """Markdown should list sources."""
    md = export_markdown(_make_result())
    assert "auth0.com/pricing" in md


def test_export_markdown_contains_rounds():
    """Markdown should include opening arguments."""
    md = export_markdown(_make_result())
    assert "Opening Arguments" in md
    assert "Auth gives control" in md


def test_export_markdown_shows_template():
    """Markdown should show template name."""
    md = export_markdown(_make_result())
    assert "build" in md


# ── Helper tests ─────────────────────────────────────────────────────────────

def test_escape_html_entities():
    """_escape should handle HTML entities."""
    assert _escape("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"


def test_md_to_html_headers():
    """_md_to_html_basic should convert headers."""
    result = _md_to_html_basic("## TL;DR\nSome text")
    assert "<h3>" in result
    assert "TL;DR" in result


def test_md_to_html_bold():
    """_md_to_html_basic should convert bold text."""
    result = _md_to_html_basic("This is **important** text")
    assert "<strong>important</strong>" in result


def test_md_to_html_decision_tree():
    """_md_to_html_basic should preserve decision tree formatting."""
    tree = "├── Do you have >10K users?\n│   ├── YES → Build custom\n│   └── NO → Use Auth0"
    result = _md_to_html_basic(tree)
    assert "├──" in result
    assert "<code>" in result
