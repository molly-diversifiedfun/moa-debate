Run a multi-round debate between AI models to resolve a complex question.

Usage: /moa-debate $ARGUMENTS

Models independently answer, then a forced challenge round finds flaws, then models revise. Auto-exits early on convergence. Live battle commentary shows argument previews and agreement scores.

Adversarial debates use the strongest healthy models (Opus vs GPT-5.4) from different providers, with circuit breakers auto-skipping broken models. Both sides get real web sources and cite evidence. The judge verifies claims against research.

Steps:
1. Run: `~/github/moa-debate/.venv/bin/moa debate "$ARGUMENTS"`
2. The output will stream live progress (battle card, argument previews, agreement scores)
3. Display the full verdict including all sections
4. If converged early, mention which round
5. Highlight the "How to De-Risk This" section if present — it's the most actionable part

Key flags (pass through if the user specifies):
- `--style adversarial` — angel/devil/judge (strongest models, assumptions + conditionals + de-risking)
- `--template hire|build|invest` — domain-specific decision framing (auto-detected if not specified)
- `--persona "name,name"` — debate from specific perspectives
- `--persona <category>` — all personas in a category
- `--rounds N` — revision rounds (default 2, auto-extends up to +2 if positions still shifting)
- `--tier lite|pro|ultra` — model tier for peer debate (adversarial auto-picks strongest healthy models)

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

Features:
- **Research-grounded** — both sides get web sources (Firecrawl + DuckDuckGo fallback), cite evidence, judge verifies claims
- **Circuit breakers** — auto-skips models with recent failures, picks next-strongest
- **Decision templates** — `--template hire` adds domain-specific judge criteria (e.g., Schmidt & Hunter research for hiring)
- **Auto-extension** — if positions are still shifting after N rounds, extends up to 2 more
- **Convergence detection** — early exit when agreement exceeds 70%
- **Debate transcripts** — saved to `~/.moa/debates/` for later review

When to recommend adversarial vs peer:
- **Adversarial** — binary decisions ("should we X?"), plan review, go/no-go
- **Peer** — open-ended questions ("how should we X?"), technology comparisons

Best for:
- Hiring: `/moa-debate --style adversarial --template hire "Should we hire a senior engineer or two juniors?"`
- Build/buy: `/moa-debate --style adversarial --template build "Build auth in-house or use Auth0?"`
- Investment: `/moa-debate --style adversarial --template invest "Should we invest in this startup?"`
- Plan review: `cat plan.md | /moa-debate --style adversarial "Should we execute this?"`
- Architecture: `/moa-debate "Event sourcing vs CRUD?"`
- Go/no-go: `/moa-debate --style adversarial "Should we quit and build this?"`
- Persona debates: `/moa-debate --persona "DHH,Kelsey Hightower" "Do we need K8s?"`

Related commands:
- `moa health` — check model circuit breaker status
- `moa templates` — list available decision templates
