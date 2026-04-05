Ask a question using the multi-model ensemble (adaptive routing with research).

Usage: /moa $ARGUMENTS

Runs your question through multiple AI models in parallel, synthesizes their responses, auto-searches the web when models disagree (Firecrawl + DuckDuckGo fallback), and uses domain-aware confidence thresholds. Circuit breakers auto-skip broken models. Strategic and judgment questions automatically get "It Depends On..." conditionals and "How to De-Risk This" action steps.

Steps:
1. Run: `~/github/moa-debate/.venv/bin/moa ask "$ARGUMENTS"`
2. Display the full response including cost and latency
3. If 🔍 RESEARCHED — mention models disagreed and web search was used
4. If ⚠️ SPLIT — note the agreement score and domain
5. If the output has "It Depends On..." or "How to De-Risk This" sections, highlight them

Key flags (pass through if the user specifies):
- `--research deep` — multi-hop web search (~30-60s, grounded in real docs)
- `--research off` — disable auto-search on disagreement
- `--persona "name,name"` — specific perspectives (e.g. "DHH,Shreya Doshi")
- `--persona <category>` — all personas in a category: code, product, content, architecture, builder
- `--layers 2` — verification pass: proposers check the synthesis for errors
- `--tier lite|pro|ultra` — manual tier selection
- `--context <path>` — inject project files as context
- `--debug` — show the full prompt sent to models

When to use which flag:
- Architecture/strategy decisions → no flag needed, auto-detects STRATEGIC domain
- Niche tooling questions → no flag needed, auto-researches on disagreement
- Need grounded docs → `--research deep`
- Want a specific philosophy → `--persona "name"`
- Piping a file for review → `cat file.md | moa ask "..."`
- High-stakes accuracy → `--layers 2`

Persona categories:
- code: Martin Fowler, Kent Beck, Rich Hickey, Sandi Metz
- architecture: Kelsey Hightower, Martin Kleppmann, DHH
- product: Shreya Doshi, Marty Cagan, April Dunford
- content: David Ogilvy, Ann Handley
- builder: Pieter Levels, Daniel Vassallo

Examples:
- `/moa Should I use microservices or a monolith?` — adaptive, gets conditionals + de-risking
- `/moa --persona product Is this feature worth building?` — product personas
- `/moa --research deep How do I configure LiteLLM failover?` — deep research with citations
- `/moa --persona "DHH" Do we need Kubernetes?` — specific persona
- `cat plan.md | /moa "Is this plan solid? What am I missing?"` — plan review
- `/moa --debug --persona builder "Should I quit my job for this?"` — see full prompt
