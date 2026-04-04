# MOA Validation Suite

Real queries that test every feature. Run manually, judge results. Each test has a **what to look for** section so you know if it's working.

## How to Run

```bash
source .venv/bin/activate
# Run all tests in order (~$2-3 total, ~15 min)
# Or cherry-pick individual tests
```

---

## 1. Baseline: Does Multi-Model Beat Single Model?

The fundamental question. Same query, single model vs ensemble.

### 1a. Single model (control)
```bash
moa ask --tier flash "What are the tradeoffs of using SQLite in production?"
```

### 1b. Multi-model ensemble
```bash
moa ask "What are the tradeoffs of using SQLite in production?"
```

**What to look for:**
- Does the ensemble catch tradeoffs the single model missed?
- Is the answer more balanced (pros AND cons)?
- Does the "Key Points of Agreement" section surface high-confidence conclusions?
- Does "Unique Contributions" show each model adding something different?

---

## 2. Domain-Capped Confidence

Test that strategic questions trigger lower agreement thresholds than factual ones.

### 2a. Factual query (should show HIGH confidence)
```bash
moa ask "What HTTP status code means 'resource not found'?"
```

### 2b. Strategic query (should show lower threshold, possibly trigger research)
```bash
moa ask "Should a 3-person startup use Supabase or Firebase for their backend?"
```

**What to look for:**
- 2a: Domain shows FACTUAL, threshold 45%, confidence bar HIGH
- 2b: Domain shows STRATEGIC or JUDGMENT, threshold 20-25%
- 2b might trigger research if models disagree (blue 🔍 badge)
- Footer shows domain classification for both

---

## 3. Research-Augmented Routing

Test that niche questions trigger web search and produce grounded answers.

### 3a. Niche tooling question (should auto-research)
```bash
moa ask "How do I configure Turborepo remote caching with a self-hosted server?"
```

### 3b. Deep research (manual)
```bash
moa ask --research deep "What are the current rate limits and pricing for the Firecrawl API?"
```

### 3c. Research off (control)
```bash
moa ask --research off "How do I configure Turborepo remote caching with a self-hosted server?"
```

**What to look for:**
- 3a: 🔍 RESEARCHED badge if models disagreed, sources in output
- 3b: Research steps shown ("Searched N sources..."), source citations in answer, ~30-60s
- 3c: No research badge — compare answer quality to 3a
- Does the researched answer cite specific docs/URLs?
- Does the non-researched answer contain vague or incorrect specifics?

---

## 4. Pairwise Ranking

Test that the best proposal wins, not just the longest.

```bash
moa ask --proposals "Explain the difference between concurrency and parallelism"
```

**What to look for:**
- `--proposals` flag shows individual model responses
- Footer shows `👑 Best: [model]` — is it actually the best response, or just the longest?
- If the shortest response is the clearest, does pairwise ranking pick it?

---

## 5. Debate: Challenge Round + Convergence

### 5a. Topic where models should converge
```bash
moa debate "Is TypeScript worth the overhead for a solo developer's side project?"
```

### 5b. Topic where models should NOT converge
```bash
moa debate "Is OOP or functional programming better for large codebases?"
```

**What to look for:**
- 5a: Should converge early (green "converged at round 1/2"), challenge round finds minor flaws
- 5b: Should run all rounds, show "Remaining Disagreements" in verdict
- Both: "What the Debate Settled" shows what all models agreed on after debate
- Both: "Strongest Arguments" attributes good points to specific models
- Cost savings: does 5a cost less than 5b? (fewer rounds = fewer API calls)

---

## 6. Adversarial Debate

```bash
moa debate --style adversarial "Should we build a mobile app or stay web-only for our MVP?"
```

**What to look for:**
- Advocate builds genuine case FOR mobile app
- Critic finds real weaknesses, not strawmen
- "What Changed During Debate" shows actual concessions
- "Bottom Line" gives a clear recommendation with reasoning
- Different from peer debate — more structured, two clear sides

---

## 7. Personas: Code Review

### 7a. Default specialists
```bash
echo 'function processUser(data) {
  const user = JSON.parse(data);
  const query = `SELECT * FROM users WHERE id = ${user.id}`;
  eval(user.callback);
  return fetch("http://api.internal/admin", {
    headers: { "Authorization": user.token }
  });
}' | moa review --raw
```

### 7b. Famous engineer personas
```bash
echo 'function processUser(data) {
  const user = JSON.parse(data);
  const query = `SELECT * FROM users WHERE id = ${user.id}`;
  eval(user.callback);
  return fetch("http://api.internal/admin", {
    headers: { "Authorization": user.token }
  });
}' | moa review --personas
```

### 7c. Specific persona
```bash
echo 'class UserService {
  constructor(db, cache, logger, mailer, validator, config, metrics) {
    this.db = db; this.cache = cache; this.logger = logger;
    this.mailer = mailer; this.validator = validator;
    this.config = config; this.metrics = metrics;
  }
  processUser(id) {
    const user = this.db.find(id);
    this.validator.validate(user);
    this.cache.set(id, user);
    this.logger.info("processed");
    this.metrics.increment("users.processed");
    this.mailer.send(user.email, "Welcome");
    return user;
  }
}' | moa review --persona "Sandi Metz"
```

**What to look for:**
- 7a: Security reviewer catches SQL injection + eval(). Architecture reviewer catches coupling. Performance reviewer flags unvalidated fetch.
- 7b: Fowler identifies code smells. Beck asks "where are the tests?" Hickey says "this is complecting concerns." Metz says "7 constructor params violates the rules."
- 7c: Sandi Metz specifically calls out >4 params, class doing too many things, suggests extraction
- Do personas produce genuinely different reviews from specialists?

---

## 8. Personas: Product + Strategy

### 8a. Product decision
```bash
moa ask --persona product "We have 500 free users and 3 paying customers. Should we build the feature our paying customers are asking for, or the one that would convert free users?"
```

### 8b. Builder decision
```bash
moa ask --persona builder "I want to build a SaaS tool for freelancers to track their invoices. What's the fastest path to first revenue?"
```

### 8c. Specific persona comparison
```bash
moa ask --persona "Pieter Levels" "I want to build a SaaS tool for freelancers to track their invoices. What's the fastest path to first revenue?"
```

Then:
```bash
moa ask --persona "Daniel Vassallo" "I want to build a SaaS tool for freelancers to track their invoices. What's the fastest path to first revenue?"
```

**What to look for:**
- 8a: Doshi talks leverage, Cagan talks discovery vs delivery, Dunford talks positioning
- 8b: Multiple builder perspectives synthesized
- 8c: Levels says "ship in a weekend, no database." Vassallo says "sell before you build, test with a landing page." Are they genuinely different?

---

## 9. Discourse Round

```bash
git diff HEAD~1 | moa review --discourse
```

(Or create a file with deliberate issues and pipe it)

**What to look for:**
- Initial findings from 4 specialists
- Discourse reactions: AGREE, CHALLENGE, CONNECT, SURFACE
- Do reviewers actually disagree with each other? (CHALLENGE)
- Do they surface new issues after seeing others' findings? (SURFACE)
- Does CONNECT find cross-cutting concerns?

---

## 10. Multi-Layer Aggregation

### 10a. Single layer (default)
```bash
moa ask --tier pro "Design a rate limiting strategy for a multi-tenant API that handles both per-user and per-tenant limits"
```

### 10b. Two layers (verification pass)
```bash
moa ask --tier pro --layers 2 "Design a rate limiting strategy for a multi-tenant API that handles both per-user and per-tenant limits"
```

**What to look for:**
- Does layer 2 catch errors in layer 1's synthesis?
- Is the 2-layer answer more accurate or just longer?
- Cost difference: ~2x for 2 layers — is the quality improvement worth it?
- Model status shows L2 verification step

---

## 11. Content Personas

```bash
moa ask --persona "David Ogilvy" "Write a headline for a landing page selling an AI-powered invoice tool for freelancers"
```

Then:
```bash
moa ask --persona "Ann Handley" "Write a headline for a landing page selling an AI-powered invoice tool for freelancers"
```

**What to look for:**
- Ogilvy: specific, benefit-driven, possibly long-form ("How to [benefit] without [pain]")
- Handley: conversational, clear, jargon-free
- Are they genuinely different styles or generic AI copy?

---

## 12. Stress Test: Everything Combined

```bash
moa debate --style adversarial --persona "DHH,Kelsey Hightower" --rounds 3 \
  "Should a growing startup migrate from a Rails monolith to Kubernetes microservices?"
```

**What to look for:**
- DHH-flavored Advocate argues AGAINST migration (stay monolith)
- Hightower-flavored Critic argues FOR (but questions if K8s is needed)
- Wait — this might flip! DHH should be the CRITIC of Kubernetes
- Does the persona injection actually influence the angel/devil roles?
- 3 rounds with convergence check — do they converge or stay split?
- Full structured output: Verdict, Advocate's Points, Critic's Points, What Changed, Bottom Line

---

## 13. Error Handling + Edge Cases

### 13a. No API keys available
```bash
OPENAI_API_KEY="" ANTHROPIC_API_KEY="" GEMINI_API_KEY="" moa ask "test"
```

### 13b. Budget exceeded
```bash
# Run after heavy usage day, or temporarily set MAX_DAILY_SPEND_USD=0.001 in config.py
moa ask "test budget"
```

### 13c. Empty query
```bash
moa ask ""
```

### 13d. Very long query (context window test)
```bash
python3 -c "print('x ' * 5000)" | moa ask "Summarize this"
```

**What to look for:**
- 13a: Clear error message, not a crash
- 13b: Budget exceeded message with current spend
- 13c: Handled gracefully
- 13d: Doesn't crash, truncates or handles appropriately

---

## 14-17: MOA-Designed Tests (the system tested itself)

We asked MOA to design its own validation tests. These 4 test categories we missed:

### 14. Factual Accuracy Under Uncertainty

```bash
moa ask "What was the exact population of Lagos, Nigeria in 2019, and what methodology was used to calculate it?"
```

**What to look for:**
- Do models hallucinate different "exact" numbers?
- Does disagreement on numbers trigger research?
- Does the answer acknowledge conflicting data sources?
- Compare: `moa ask --research off` same query — does it hallucinate a single confident number?

### 15. Mathematical Reasoning Chain

```bash
moa debate "A cylindrical tank is being filled at 3 L/min while draining at a rate proportional to the square root of current volume. If the proportionality constant is 0.1 L^0.5/min and the tank starts empty, what's the equilibrium volume?"
```

**What to look for:**
- Does the challenge round catch calculation errors?
- Do models converge on the correct answer (900 L)?
- Does debate actually improve math vs single model?
- Compare: `moa ask --tier flash` same query — is the debate answer more reliable?

### 16. Domain Expertise Boundary (Hallucination Detection)

```bash
moa ask "Design a pulse sequence for a 7-Tesla MRI to optimize T2* contrast in the substantia nigra while minimizing susceptibility artifacts."
```

**What to look for:**
- Does MOA correctly identify this as ultra-niche (TECHNICAL domain)?
- Do models confidently hallucinate specific parameters, or acknowledge limits?
- Does agreement score reflect uncertainty (should be LOW)?
- Does research trigger? Are search results helpful or irrelevant?
- **Key question:** Does multi-model make hallucination worse (correlated confidence) or better (disagreement exposes it)?

### 17. Logical Consistency Across Related Queries

Run these 3 queries back-to-back:

```bash
moa ask "Is it ethical to eat meat?"
moa ask "Should lab-grown meat replace traditional meat?"
moa ask "Is hunting more ethical than factory farming?"
```

**What to look for:**
- Are the answers logically consistent with each other?
- Does the first answer's reasoning hold up when applied to the follow-ups?
- Does MOA contradict itself across queries? (This tests whether synthesis introduces logical drift)

---

## Scoring Rubric

After running all tests, score each:

| Test | Feature Validated | Pass Criteria |
|------|------------------|---------------|
| 1 | Multi-model value | Ensemble answer is more complete than single model |
| 2 | Domain confidence | Correct domain classification and threshold |
| 3 | Research routing | Niche question gets researched, generic doesn't |
| 4 | Pairwise ranking | Best response selected, not longest |
| 5 | Debate convergence | Converges on easy topic, runs full on hard topic |
| 6 | Adversarial debate | Genuine advocacy + genuine critique, clear verdict |
| 7 | Code review personas | Different perspectives, not generic feedback |
| 8 | Product personas | Distinct advice per persona |
| 9 | Discourse | Reviewers meaningfully react to each other |
| 10 | Multi-layer | Layer 2 catches or improves layer 1 |
| 11 | Content personas | Distinct styles, not generic |
| 12 | Full stack | All features work together |
| 13 | Error handling | No crashes on edge cases |
| 14 | Factual accuracy | Catches conflicting numbers, triggers research |
| 15 | Math reasoning | Debate catches calculation errors |
| 16 | Expertise boundary | Correctly identifies knowledge limits vs hallucinating |
| 17 | Cross-query consistency | No logical contradictions across related queries |

## Quick Smoke Test (~$0.50, 3 min)

If you just want to verify everything works:

```bash
# 1. Basic ask (adaptive routing + confidence)
moa ask "What's the best way to handle errors in async JavaScript?"

# 2. Persona ask
moa ask --persona "DHH" "Do I need a microservice for this?"

# 3. Research
moa ask --research deep "Firecrawl API search endpoint parameters"

# 4. Debate
moa debate "Tabs vs spaces?"

# 5. Code review
echo 'eval(userInput)' | moa review

# 6. Adversarial
moa debate --style adversarial "Should I use a NoSQL database?"
```
