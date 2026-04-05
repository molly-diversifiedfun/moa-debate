Run a multi-round debate between AI models to resolve a complex question.

Usage: /moa-debate $ARGUMENTS

Models independently answer, then a forced challenge round finds flaws, then models revise. Auto-exits early on convergence. Live battle commentary shows argument previews and agreement scores.

Adversarial debates use the strongest available models (Opus vs GPT-5.4) from different providers. Output includes key assumptions, conditional analysis ("it depends on..."), and specific de-risking steps.

Steps:
1. Run: `~/github/moa-debate/.venv/bin/moa debate "$ARGUMENTS"`
2. The output will stream live progress (battle card, argument previews, agreement scores)
3. Display the full verdict including all sections
4. If converged early, mention which round
5. Highlight the "How to De-Risk This" section if present — it's the most actionable part

Key flags (pass through if the user specifies):
- `--style adversarial` — angel/devil/judge (strongest models, assumptions + conditionals + de-risking)
- `--persona "name,name"` — debate from specific perspectives
- `--persona <category>` — all personas in a category
- `--rounds N` — revision rounds (default 2)
- `--tier lite|pro|ultra` — model tier for peer debate (adversarial auto-picks strongest)

Adversarial debate output sections:
- **Verdict** — the recommendation
- **Key Assumptions** — what was assumed because the question didn't specify
- **Advocate's / Critic's Strongest Points** — best arguments each side made
- **It Depends On...** — conditional scenarios that change the answer
- **What Changed During Debate** — who conceded what
- **How to De-Risk This** — 3-5 specific actionable steps
- **Bottom Line** — which side won and what to do next

Peer debate output sections:
- **Verdict** — synthesized answer
- **What the Debate Settled** — high-confidence conclusions
- **Remaining Disagreements** — genuine open questions
- **Strongest Arguments** — which model won on which point
- **It Depends On...** / **How to De-Risk This** — always included

When to recommend adversarial vs peer:
- **Adversarial** — binary decisions ("should we X?"), plan review, go/no-go
- **Peer** — open-ended questions ("how should we X?"), technology comparisons

Best for:
- Plan review: `cat plan.md | /moa-debate --style adversarial "Should we execute this?"`
- Architecture: `/moa-debate "Event sourcing vs CRUD?"`
- Go/no-go: `/moa-debate --style adversarial "Should we quit and build this?"`
- Persona debates: `/moa-debate --persona "DHH,Kelsey Hightower" "Do we need K8s?"`
