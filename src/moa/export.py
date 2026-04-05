"""Export debate transcripts as shareable HTML or clean markdown."""

import datetime
import html
from pathlib import Path
from typing import Dict, Any, Optional


def _escape(text: str) -> str:
    """HTML-escape text."""
    return html.escape(text)


def _md_to_html_basic(text: str) -> str:
    """Minimal markdown-to-HTML: headers, bold, lists, code blocks, paragraphs."""
    import re
    lines = text.split("\n")
    result = []
    in_code = False
    in_list = False

    for line in lines:
        # Code blocks
        if line.strip().startswith("```"):
            if in_code:
                result.append("</pre>")
                in_code = False
            else:
                result.append("<pre>")
                in_code = True
            continue
        if in_code:
            result.append(_escape(line))
            continue

        # Close list if needed
        if in_list and not line.strip().startswith(("- ", "* ", "1.", "2.", "3.", "4.", "5.")):
            result.append("</ul>")
            in_list = False

        stripped = line.strip()
        if not stripped:
            result.append("")
            continue

        # Headers
        if stripped.startswith("### "):
            result.append(f"<h4>{_escape(stripped[4:])}</h4>")
        elif stripped.startswith("## "):
            result.append(f"<h3>{_escape(stripped[3:])}</h3>")
        elif stripped.startswith("# "):
            result.append(f"<h2>{_escape(stripped[2:])}</h2>")
        # Decision tree (preserve formatting)
        elif any(c in stripped for c in ("├──", "└──", "│")):
            result.append(f"<code>{_escape(line)}</code><br>")
        # List items
        elif stripped.startswith(("- ", "* ")):
            if not in_list:
                result.append("<ul>")
                in_list = True
            content = stripped[2:]
            # Bold
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            result.append(f"<li>{content}</li>")
        # Bold in regular text
        else:
            content = _escape(stripped)
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            result.append(f"<p>{content}</p>")

    if in_list:
        result.append("</ul>")
    if in_code:
        result.append("</pre>")

    return "\n".join(result)


# ── HTML template ─────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Debate: {title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 800px; margin: 0 auto; padding: 2rem 1rem; color: #1a1a1a;
         line-height: 1.6; background: #fafafa; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; }}
  h2 {{ font-size: 1.3rem; margin: 1.5rem 0 0.5rem; border-bottom: 1px solid #ddd; padding-bottom: 0.25rem; }}
  h3 {{ font-size: 1.1rem; margin: 1rem 0 0.5rem; }}
  h4 {{ font-size: 1rem; margin: 0.75rem 0 0.25rem; color: #555; }}
  p {{ margin: 0.5rem 0; }}
  pre {{ background: #f0f0f0; padding: 1rem; border-radius: 6px; overflow-x: auto;
         font-size: 0.85rem; margin: 0.5rem 0; white-space: pre-wrap; }}
  code {{ background: #f0f0f0; padding: 0 0.3rem; border-radius: 3px; font-size: 0.85rem; }}
  ul {{ margin: 0.5rem 0 0.5rem 1.5rem; }}
  li {{ margin: 0.25rem 0; }}
  strong {{ color: #111; }}
  .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  .meta span {{ margin-right: 1.5rem; }}
  .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px;
            font-size: 0.8rem; font-weight: 600; }}
  .badge-adversarial {{ background: #fee2e2; color: #991b1b; }}
  .badge-peer {{ background: #dbeafe; color: #1e40af; }}
  .badge-template {{ background: #fef3c7; color: #92400e; }}
  .badge-converged {{ background: #d1fae5; color: #065f46; }}
  .round {{ border: 1px solid #e5e7eb; border-radius: 8px; margin: 1rem 0; overflow: hidden; }}
  .round-header {{ background: #f9fafb; padding: 0.75rem 1rem; cursor: pointer;
                   display: flex; justify-content: space-between; align-items: center;
                   border-bottom: 1px solid #e5e7eb; }}
  .round-header:hover {{ background: #f3f4f6; }}
  .round-body {{ padding: 1rem; }}
  .round-body.collapsed {{ display: none; }}
  .advocate {{ border-left: 3px solid #3b82f6; padding-left: 1rem; margin: 0.5rem 0; }}
  .critic {{ border-left: 3px solid #ef4444; padding-left: 1rem; margin: 0.5rem 0; }}
  .verdict {{ background: #fffbeb; border: 2px solid #f59e0b; border-radius: 8px;
              padding: 1.5rem; margin: 1.5rem 0; }}
  .sources {{ background: #eff6ff; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
  .sources a {{ color: #2563eb; text-decoration: none; }}
  .sources a:hover {{ text-decoration: underline; }}
  .agreement {{ display: inline-block; font-family: monospace; }}
  .footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #ddd;
             color: #999; font-size: 0.8rem; }}
  .arrow {{ transition: transform 0.2s; display: inline-block; }}
  .arrow.open {{ transform: rotate(90deg); }}
</style>
</head>
<body>
<h1>{title_icon} {title_escaped}</h1>
<div class="meta">
  <span>{date}</span>
  <span class="{style_badge_class}">{style_label}</span>
  {template_badge}
  {converged_badge}
</div>
<div class="meta">
  <span>Models: {angel_model} vs {devil_model}</span>
  <span>Cost: ${cost:.4f}</span>
  <span>Latency: {latency}s</span>
  <span>Rounds: {total_rounds}</span>
</div>

{sources_html}

{rounds_html}

<div class="verdict">
<h2>Verdict</h2>
{verdict_html}
</div>

<div class="footer">
  Generated by <a href="https://github.com/molly-diversifiedfun/moa-debate">moa-debate</a> &middot; {date}
</div>

<script>
document.querySelectorAll('.round-header').forEach(h => {{
  h.addEventListener('click', () => {{
    const body = h.nextElementSibling;
    const arrow = h.querySelector('.arrow');
    body.classList.toggle('collapsed');
    arrow.classList.toggle('open');
  }});
}});
</script>
</body>
</html>"""


def export_html(result: Dict[str, Any]) -> str:
    """Export a debate result dict as a self-contained HTML string."""
    query = result.get("query", "Debate")
    style = result.get("debate_style", "peer")
    template = result.get("template")
    angel = result.get("angel_model", "Model A")
    devil = result.get("devil_model", "Model B")
    cost = result.get("cost")
    cost_usd = cost.estimated_cost_usd if cost else 0.0
    latency_s = round(result.get("latency_ms", 0) / 1000, 1)
    all_rounds = result.get("rounds", [])
    total_rounds = max(len(all_rounds) - 1, 0)
    converged_at = result.get("converged_at")
    sources = result.get("research_sources", [])
    verdict = result.get("response", "")

    # Badges
    style_badge_class = f"badge badge-{style}"
    style_label = style.title()
    template_badge = f'<span class="badge badge-template">{template}</span>' if template else ""
    converged_badge = f'<span class="badge badge-converged">Converged R{converged_at}</span>' if converged_at else ""
    title_icon = "⚔️" if style == "adversarial" else "💬"

    # Sources
    sources_html = ""
    if sources:
        links = "\n".join(f'<li><a href="{_escape(url)}">{_escape(url)}</a></li>' for url in sources)
        sources_html = f'<div class="sources"><h3>Sources ({len(sources)} cited)</h3><ul>{links}</ul></div>'

    # Rounds
    rounds_parts = []
    for i, round_data in enumerate(all_rounds):
        if not isinstance(round_data, dict):
            continue
        label = "Opening Arguments" if i == 0 else f"Round {i}"
        collapsed = ' collapsed' if i > 0 else ''
        arrow_cls = 'arrow open' if i == 0 else 'arrow'

        body = ""
        if "angel" in round_data:
            body = (
                f'<div class="advocate"><h4>Advocate ({_escape(angel)})</h4>'
                f'{_md_to_html_basic(round_data["angel"])}</div>'
                f'<div class="critic"><h4>Critic ({_escape(devil)})</h4>'
                f'{_md_to_html_basic(round_data["devil"])}</div>'
            )
        else:
            for model_name, response in round_data.items():
                short = model_name.split("/")[-1] if "/" in model_name else model_name
                body += f'<div><h4>{_escape(short)}</h4>{_md_to_html_basic(response)}</div>'

        rounds_parts.append(
            f'<div class="round">'
            f'<div class="round-header"><span>{label}</span><span class="{arrow_cls}">▶</span></div>'
            f'<div class="round-body{collapsed}">{body}</div>'
            f'</div>'
        )
    rounds_html = "\n".join(rounds_parts)

    # Verdict
    verdict_html = _md_to_html_basic(verdict)

    return _HTML_TEMPLATE.format(
        title=query,
        title_escaped=_escape(query),
        title_icon=title_icon,
        date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        style_badge_class=style_badge_class,
        style_label=style_label,
        template_badge=template_badge,
        converged_badge=converged_badge,
        angel_model=_escape(angel),
        devil_model=_escape(devil),
        cost=cost_usd,
        latency=latency_s,
        total_rounds=total_rounds,
        sources_html=sources_html,
        rounds_html=rounds_html,
        verdict_html=verdict_html,
    )


def export_markdown(result: Dict[str, Any]) -> str:
    """Export a debate result dict as clean markdown."""
    query = result.get("query", "Debate")
    style = result.get("debate_style", "peer")
    template = result.get("template")
    angel = result.get("angel_model", "Model A")
    devil = result.get("devil_model", "Model B")
    cost = result.get("cost")
    cost_usd = cost.estimated_cost_usd if cost else 0.0
    latency_s = round(result.get("latency_ms", 0) / 1000, 1)
    all_rounds = result.get("rounds", [])
    total_rounds = max(len(all_rounds) - 1, 0)
    converged_at = result.get("converged_at")
    sources = result.get("research_sources", [])
    verdict = result.get("response", "")

    lines = [
        f"# Debate: {query}",
        "",
        f"**Style:** {style} | **Models:** {angel} vs {devil} | **Rounds:** {total_rounds} | **Cost:** ${cost_usd:.4f} | **Latency:** {latency_s}s",
    ]
    if template:
        lines.append(f"**Template:** {template}")
    if converged_at:
        lines.append(f"**Converged:** Round {converged_at}")

    if sources:
        lines.extend(["", "## Sources"])
        for i, url in enumerate(sources):
            lines.append(f"{i+1}. {url}")

    for i, round_data in enumerate(all_rounds):
        if not isinstance(round_data, dict):
            continue
        lines.append("")
        lines.append(f"## {'Opening Arguments' if i == 0 else f'Round {i}'}")
        if "angel" in round_data:
            lines.extend(["", f"### Advocate ({angel})", "", round_data["angel"]])
            lines.extend(["", f"### Critic ({devil})", "", round_data["devil"]])
        else:
            for model_name, response in round_data.items():
                short = model_name.split("/")[-1] if "/" in model_name else model_name
                lines.extend(["", f"### {short}", "", response])

    lines.extend(["", "---", "", "## Verdict", "", verdict])
    return "\n".join(lines)
