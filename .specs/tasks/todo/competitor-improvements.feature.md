# Spec: 8 Competitor-Inspired Improvements

**Date:** 2026-04-04
**Sources:** duh, togethercomputer/MoA, Open Code Review, Multi-Agents-Debate, LLM-Blender
**Status:** Ready for implementation

## Overview

8 improvements stolen from competitor repos, grouped into 4 shippable phases. Each phase is independent — ship, test, then move to the next.

---

## Phase 1: Debate Upgrades (trivial — prompts + flow changes)

Three improvements to `run_debate()` that only touch prompts and the debate loop. No new flags needed for #2 and #3 — they improve default behavior. Ship together.

### Improvement #2: Forced Challenge Round (from duh)

**What:** Add a "Challenge" step between Round 0 (independent) and Round 1+ (revision). Models are explicitly prompted to find flaws, not just revise.

**Where:** `engine.py:run_debate()` line 834, between Round 0 and the revision loop.

**Flow change:**
```
Current:  Round 0 (independent) → Round 1-N (revise) → Judge
New:      Round 0 (independent) → Challenge (find flaws) → Round 1-N (revise) → Judge
```

**New prompt in prompts.py:**
```python
DEBATE_CHALLENGE_SYSTEM = """You are reviewing other models' responses to a question. \
Your job is to find FLAWS — errors, weak reasoning, missing considerations, unsupported claims.

Rules:
- You MUST identify at least one flaw per response. Do not agree with everything.
- Be specific: quote the exact claim you're challenging and explain why it's wrong or weak.
- If a response is genuinely excellent, challenge the scope or assumptions instead.
- Do NOT rewrite your own answer. Only critique others.

Other models' responses:
{other_responses}"""
```

**Code change (~20 lines):** After Round 0, run challenge round using `DEBATE_CHALLENGE_SYSTEM`. Store challenges. In Round 1+, include challenges in the revision prompt so models address the critiques.

**Backward compatible:** Yes — improves default debate quality, no flag needed.

### Improvement #3: Convergence-Based Early Exit (from duh)

**What:** Check `compute_agreement()` between debate rounds. If agreement > 0.7, exit early.

**Where:** `engine.py:run_debate()` line 860, end of each round loop.

**Code change (~10 lines):**
```python
# After updating current_positions in each round:
round_proposals = list(current_positions.values())
agreement = compute_agreement(round_proposals)
if agreement["score"] > 0.7:
    # Models converged — no point continuing
    break
```

**Return value addition:** `"converged_at_round": round_num` or `None`.

**Backward compatible:** Yes — saves money by default, no flag needed.

### Improvement #7: Angel/Devil/Judge Pattern (from Multi-Agents-Debate)

**What:** Alternative debate style where models get adversarial roles instead of being peers.

**Where:** `engine.py:run_debate()` — new parameter `debate_style="peer"` (default) or `"adversarial"`.

**CLI flag:** `moa debate --style adversarial "question"`

**New prompts:**
```python
DEBATE_ANGEL_SYSTEM = """You are the ADVOCATE. Your job is to build the strongest \
possible case FOR the proposition. Find supporting evidence, anticipate objections, \
and construct a compelling argument.

The question: {query}
The opposing position: {devil_response}"""

DEBATE_DEVIL_SYSTEM = """You are the CRITIC. Your job is to build the strongest \
possible case AGAINST the proposition. Find weaknesses, counter-evidence, hidden \
risks, and unstated assumptions.

The question: {query}
The advocating position: {angel_response}"""
```

**Flow:**
```
Round 0: Angel proposes (FOR), Devil proposes (AGAINST) — using 2 different models
Round 1-N: Angel sees Devil's critique → revises. Devil sees Angel's case → revises.
           Check convergence between rounds.
Final: Judge (Opus) synthesizes both positions into a balanced answer.
```

**Code change (~40 lines):** Separate branch in `run_debate()` when `debate_style="adversarial"`. Uses 2 models (not all available) + judge.

---

## Phase 2: Smarter Agreement Detection (medium — classifier + ranking)

Two improvements to how moa-debate measures model agreement. These affect adaptive routing (when research triggers) and response quality.

### Improvement #1: Domain-Capped Confidence (from duh)

**What:** The current agreement threshold is flat 35%. Domain-cap it so strategic/judgment questions trigger research more readily.

**Where:** `engine.py:run_adaptive()` line 512, the `compute_agreement()` call and consensus check.

**Domain caps:**
```python
DOMAIN_CONFIDENCE_CAPS = {
    "FACTUAL": 0.45,      # High bar — models should agree on facts
    "TECHNICAL": 0.40,    # Moderate — some implementation opinions OK
    "CREATIVE": 0.30,     # Low bar — diversity is expected
    "JUDGMENT": 0.25,     # Very low — genuine opinion splits normal
    "STRATEGIC": 0.20,    # Lowest — complex decisions always diverge
}
```

**Implementation:** Extend the existing classifier prompt to also output domain:
```python
# Current: {"tier": "SIMPLE" | "STANDARD" | "COMPLEX"}
# New:     {"tier": "SIMPLE", "domain": "FACTUAL"}
```

Then in `run_adaptive()`:
```python
threshold = DOMAIN_CONFIDENCE_CAPS.get(domain, 0.35)
consensus = agreement["score"] > threshold
```

**Code change:** ~15 lines in engine.py, ~5 lines in prompts.py (extend classifier prompt).

### Improvement #8: Pairwise Ranking (from LLM-Blender)

**What:** Use a cheap model (Haiku/Flash) to do pairwise quality comparison of proposals, instead of only Jaccard word overlap.

**Where:** New function in `engine.py`, called after `compute_agreement()`.

**Why better than Jaccard:** Jaccard measures word overlap. Two responses can use different words but say the same thing (low Jaccard, high agreement). Or use the same words but reach opposite conclusions (high Jaccard, low agreement). Pairwise ranking catches both.

**Implementation:**
```python
async def pairwise_rank(proposals: List[str], model_names: List[str]) -> Dict:
    """Use a cheap model to rank proposals by quality via pairwise comparison."""
    model = CLASSIFIER_MODEL if CLASSIFIER_MODEL.available else CLAUDE_HAIKU

    # Compare each pair
    pairs = []
    for i in range(len(proposals)):
        for j in range(i + 1, len(proposals)):
            pairs.append((i, j))

    # For 3 proposals, that's 3 comparisons. For 5, it's 10.
    # Cap at 6 pairs to control cost.
    results = []
    for i, j in pairs[:6]:
        result = await call_model(model, [
            {"role": "system", "content": PAIRWISE_RANK_PROMPT},
            {"role": "user", "content": f"Response A ({model_names[i]}):\n{proposals[i][:2000]}\n\n"
                                         f"Response B ({model_names[j]}):\n{proposals[j][:2000]}"},
        ], temperature=0.0, max_tokens=100, timeout=10)
        # Parse: {"winner": "A"|"B"|"TIE", "reason": "..."}
        results.append(parse_ranking(result, i, j))

    # Aggregate: Elo-style or simple win count
    return {"rankings": compute_rankings(results), "agreement_signal": ...}
```

**New prompt:**
```python
PAIRWISE_RANK_PROMPT = """Compare these two responses to the same question. \
Which is more accurate, complete, and well-reasoned?

Respond with ONLY a JSON object:
{"winner": "A" or "B" or "TIE", "reason": "one sentence"}"""
```

**Integration:** Run pairwise ranking in parallel with Jaccard. Use pairwise signal to:
1. Pick the best proposal when agreement is high (instead of longest)
2. Add confidence signal for research triggering

**Code change:** ~50 lines new function, ~10 lines integration in `run_adaptive()`.

**Cost:** 3-6 Haiku calls (~$0.003-0.006) per adaptive query with 3+ proposals. Only runs on STANDARD/COMPLEX, not SIMPLE.

---

## Phase 3: Code Review Upgrades (medium — prompts + second round)

Two improvements to `run_expert_review()`.

### Improvement #5: Reviewer Discourse Round (from Open Code Review)

**What:** After specialist reviewers produce findings independently, run a second round where each reviewer sees ALL other findings and can react with structured discourse moves.

**Where:** `engine.py:run_expert_review()` line 728, after initial review tasks complete.

**Discourse prompt:**
```python
REVIEWER_DISCOURSE_SYSTEM = """You are the {role} reviewer. You've already reviewed \
this code. Now other specialists have shared their findings.

React to their findings using these moves:
- AGREE: "I confirm [finding] — here's additional evidence: ..."
- CHALLENGE: "I disagree with [finding] because ..."
- CONNECT: "[My finding X] is related to [their finding Y] because ..."
- SURFACE: "Reading their findings made me realize I missed: ..."

Only use moves that add value. Don't react to every finding.

Your original findings:
{own_findings}

Other reviewers' findings:
{other_findings}"""
```

**Flow change:**
```
Current:  4 reviewers (parallel) → Synthesizer
New:      4 reviewers (parallel) → Discourse round (parallel) → Synthesizer
```

**Code change:** ~30 lines — second round of model calls with discourse prompt, append discourse to findings before synthesis.

**CLI flag:** `moa review --discourse` (opt-in, since it doubles review cost). Default: off.

### Improvement #6: Famous Engineer Personas (from Open Code Review)

**What:** Alternative reviewer set using famous engineer personas with distinct philosophies.

**Where:** `models.py` — new `PERSONA_ROLES` list. `cli.py` — `--personas` flag.

**Personas:**
```python
PERSONA_ROLES = [
    ReviewerRole(
        name="Martin Fowler",
        system_prompt="You review code as Martin Fowler would. Focus on: refactoring opportunities, "
        "code smells, design patterns, readability. Ask: 'Is this code telling a clear story?' "
        "Quote Refactoring (2018) and Patterns of Enterprise Application Architecture.",
        model=CLAUDE_SONNET, fallback=GPT_4_1,
    ),
    ReviewerRole(
        name="Kent Beck",
        system_prompt="You review code as Kent Beck would. Focus on: test coverage, TDD violations, "
        "simplicity (YAGNI/KISS), XP principles. Ask: 'What's the simplest thing that could work?' "
        "and 'Where are the missing tests?' Quote Test-Driven Development By Example.",
        model=GPT_4_1, fallback=CLAUDE_SONNET,
    ),
    ReviewerRole(
        name="Rich Hickey",
        system_prompt="You review code as Rich Hickey would. Focus on: accidental complexity, "
        "mutable state, complecting concerns, value vs place semantics. Ask: 'Is this simple or "
        "just easy?' Prefer data over objects, immutability over mutation, composition over inheritance.",
        model=GEMINI_PRO, fallback=CLAUDE_SONNET,
    ),
    ReviewerRole(
        name="Sandi Metz",
        system_prompt="You review code as Sandi Metz would. Focus on: single responsibility, "
        "dependency injection, duck typing, object composition. Apply the rules: classes <100 lines, "
        "methods <5 lines, ≤4 params, controllers instantiate one object. Quote POODR.",
        model=CLAUDE_SONNET, fallback=GPT_4_1,
    ),
]
```

**CLI:** `moa review --staged --personas` uses PERSONA_ROLES instead of REVIEWER_ROLES.

**Code change:** ~20 lines in models.py (persona definitions), ~5 lines in cli.py (flag), ~5 lines in engine.py (accept role list param).

---

## Phase 4: Multi-Layer Aggregation (medium — optional second pass)

### Improvement #4: Multi-Layer MoA (from togethercomputer/MoA)

**What:** After synthesis, optionally re-run proposers on the synthesis to verify/improve it, then re-aggregate.

**Where:** `engine.py:run_moa()` and `engine.py:run_adaptive()`.

**CLI flag:** `moa ask --layers 2 "question"` (default: 1, max: 3).

**Flow:**
```
Layer 1 (existing): Proposers → Aggregator → Synthesis
Layer 2 (new):      Proposers see Synthesis → critique/improve → Re-aggregate
```

**Layer 2 prompt:**
```python
MOA_LAYER2_SYSTEM = """A previous synthesis of multiple model responses is shown below. \
Your job is to evaluate it critically:

1. Is it factually accurate?
2. Did it miss important points from the original responses?
3. Did it introduce errors not present in any original response?
4. Is it well-structured and clear?

If the synthesis is good, say so briefly. If it has issues, provide a corrected version.

Previous synthesis:
{synthesis}

Original responses:
{proposals}"""
```

**Code change:** ~30 lines — wrap aggregation in a loop, pass previous synthesis to proposers in subsequent layers.

**When to use:** Complex queries where aggregator might introduce errors. The MoA paper showed 2 layers is optimal; 3 layers shows diminishing returns.

---

## Implementation Order

```
Phase 1: Debate Upgrades           ~70 lines   (trivial — prompts + loop changes)
  ├── #2 Forced Challenge Round
  ├── #3 Convergence Early Exit
  └── #7 Angel/Devil/Judge (new --style flag)

Phase 2: Smarter Agreement         ~80 lines   (medium — classifier + ranking)
  ├── #1 Domain-Capped Confidence
  └── #8 Pairwise Ranking

Phase 3: Code Review Upgrades      ~60 lines   (medium — prompts + second round)
  ├── #5 Reviewer Discourse (--discourse flag)
  └── #6 Famous Personas (--personas flag)

Phase 4: Multi-Layer MoA           ~30 lines   (medium — optional pass)
  └── #4 Multi-Layer Aggregation (--layers flag)
```

**Total:** ~240 lines of new code across 4 files.

**Dependencies:** None between phases. Ship in any order. Phase 1 recommended first (easiest, biggest debate quality improvement).

## New CLI Flags Summary

| Flag | Command | Default | Description |
|------|---------|---------|-------------|
| `--style` | `moa debate` | `peer` | `peer` or `adversarial` (angel/devil/judge) |
| `--discourse` | `moa review` | off | Enable reviewer discourse round |
| `--personas` | `moa review` | off | Use famous engineer personas instead of specialists |
| `--layers` | `moa ask` | 1 | Number of MoA aggregation layers (1-3) |

## Files Changed Per Phase

| Phase | engine.py | prompts.py | models.py | cli.py | tests |
|-------|-----------|-----------|-----------|--------|-------|
| 1 | +70 | +30 | — | +5 | +40 |
| 2 | +75 | +15 | — | +5 | +30 |
| 3 | +35 | +20 | +25 | +10 | +30 |
| 4 | +30 | +10 | — | +5 | +20 |

## Acceptance Criteria

- [ ] All improvements backward-compatible (existing behavior unchanged without new flags)
- [ ] Each phase shippable independently with tests
- [ ] Debate: challenge round fires before revision, convergence exits early, adversarial mode works
- [ ] Agreement: domain classification affects research trigger threshold, pairwise ranking picks best proposal
- [ ] Review: discourse round produces AGREE/CHALLENGE/CONNECT/SURFACE reactions, personas produce distinct review styles
- [ ] Multi-layer: 2-layer MoA re-runs proposers on synthesis and re-aggregates
- [ ] All existing tests still pass after each phase
