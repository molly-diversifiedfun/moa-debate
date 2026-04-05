# MoA Use Cases — Complete Reference

Every way `moa` fits into your workflow, with the right command for each situation.

---

## 1. Daily Development

### 1a. Quick Questions
**When:** Factoid, syntax lookup, "how do I…?"
**Mode:** `moa ask` (auto-classifies as SIMPLE → 1-2 fast models, no aggregation)

```bash
moa ask "What's the difference between useEffect and useLayoutEffect?"
moa ask "How do I create a temporary table in PostgreSQL?"
```

**What happens:** Haiku or Flash answers directly. ~$0.001, 1-3s.

---

### 1b. Design Decisions
**When:** "Should I use X or Y?" — architecture, framework choice, trade-off analysis
**Mode:** `moa ask` (auto-classifies as COMPLEX → 3-4 frontier models + synthesis)

```bash
moa ask "Should I use microservices or a monolith for a 3-person startup?"
moa ask "Redis vs Memcached for session storage with 50K DAU?"
```

**What happens:** Multiple models propose independently → domain-capped agreement detection → pairwise ranking picks the best response → synthesizer produces structured output with agreement/disagreement/attribution. ~$0.15, 15-30s.

---

### 1c. Design Decisions with Personas
**When:** You want specific perspectives, not generic AI advice
**Mode:** `moa ask --persona`

```bash
# Product strategy
moa ask --persona product "Is this feature worth building for 3 paying customers?"
moa ask --persona "Shreya Doshi" "Is this high-leverage work or just busy work?"

# Architecture
moa ask --persona "DHH" "Do we need Kubernetes for this?"
moa ask --persona architecture "Serverless vs containers for a 5-person team?"

# Builder/solopreneur
moa ask --persona builder "Fastest path to first revenue for an invoice tool?"
moa ask --persona "Pieter Levels" "Can I ship this without a database?"
```

**Persona categories:** code, architecture, product, content, builder

---

### 1d. Niche Tooling Questions (Research-Augmented)
**When:** Specific library/API/framework questions where models may have training gaps
**Mode:** `moa ask` (auto-researches on disagreement) or `--research deep`

```bash
# Auto: models disagree → web search → re-ask with docs
moa ask "How do I configure Turborepo remote caching with a self-hosted server?"

# Manual deep research: 2-3 rounds of web search → single frontier model
moa ask --research deep "What are the current rate limits for the Firecrawl API?"
```

**What happens:** On auto, if models disagree the system derives search queries, fetches docs via Firecrawl, and re-asks with context. Deep research runs multi-hop search and synthesizes with Opus. ~$0.15-0.30, 30-60s.

---

## 2. Contentious Decisions (Debate)

### 2a. Peer Debate
**When:** You want models to argue it out and challenge each other
**Mode:** `moa debate`

```bash
moa debate "Monorepo vs polyrepo for 4 brands?"
moa debate --rounds 3 "GraphQL gateway vs REST with BFF pattern?"
```

**What happens:** Models independently answer → forced challenge round (find flaws) → revision rounds → convergence check (exit early if >70% agreement) → judge synthesizes. Output shows: Verdict, What the Debate Settled, Remaining Disagreements, Strongest Arguments.

---

### 2b. Adversarial Debate (Angel vs Devil)
**When:** You want one side to argue FOR and one AGAINST
**Mode:** `moa debate --style adversarial`

```bash
moa debate --style adversarial "Should we rewrite the backend in Rust?"
moa debate --style adversarial "Should I quit my job to build this full-time?"
```

**What happens:** Angel argues FOR, Devil argues AGAINST, over multiple rounds. Judge synthesizes both perspectives. Output shows: Verdict, Advocate's Strongest Points, Critic's Strongest Points, What Changed During Debate, Bottom Line.

---

### 2c. Persona Debates
**When:** You want specific thinkers to debate each other
**Mode:** `moa debate --persona`

```bash
moa debate --persona "DHH,Kelsey Hightower" "Do we need Kubernetes?"
moa debate --persona product "Build vs buy for analytics?"
moa debate --style adversarial --persona builder "Build an audience first or the product first?"
```

---

## 3. Code Review

### 3a. Expert Panel (Default)
**When:** Pre-merge review of code changes
**Mode:** `moa review`

```bash
moa review --staged
moa review path/to/changes.diff
git diff main..feature | moa review
```

**4 specialist reviewers:** Security (GPT-4.1), Architecture (Sonnet), Performance (Gemini 2.5 Pro), Correctness (Gemini 3.1 Pro). Aggregator (Opus) synthesizes with APPROVE / REQUEST CHANGES / BLOCK verdict.

---

### 3b. Famous Engineer Personas
**When:** You want review from specific engineering philosophies
**Mode:** `moa review --personas` or `--persona "name"`

```bash
moa review --staged --personas                    # Fowler, Beck, Hickey, Metz
moa review --staged --persona "Rich Hickey"       # "Is this simple or just easy?"
moa review --staged --persona "Sandi Metz"        # Classes <100 lines, methods <5
moa review --staged --persona "Kent Beck"         # "Where are the missing tests?"
moa review --staged --persona architecture        # Hightower, Kleppmann, DHH
```

---

### 3c. Discourse Mode
**When:** You want reviewers to react to each other's findings
**Mode:** `moa review --discourse`

```bash
moa review --staged --discourse
moa review --staged --personas --discourse
```

**What happens:** After initial review, each reviewer sees all other findings and can AGREE, CHALLENGE, CONNECT, or SURFACE new issues. Catches cross-cutting problems that isolated reviewers miss.

---

## 4. Research & Fact-Checking

### 4a. Cross-Model Fact Validation
**When:** You need to verify a claim across multiple models

```bash
moa ask "Is it true that React Server Components can't use useState?"
moa ask "Does AWS Lambda still have a 15-minute timeout limit?"
```

**Why MOA:** When 3 models from different providers agree on a fact, it's almost certainly correct. When they disagree, the system flags it and can auto-research.

---

### 4b. Deep Research
**When:** Complex investigation needing grounded, cited answers

```bash
moa ask --research deep "Compare Drizzle ORM vs Prisma for production Next.js"
moa ask --research deep "What are best practices for LiteLLM provider failover?"
```

**What happens:** Multi-hop web search (2-3 rounds via Firecrawl) → identifies gaps → searches deeper → single frontier model synthesizes with citations. ~30-60s.

---

## 5. Content & Copy

### 5a. Content Personas
**When:** Writing copy, headlines, or reviewing content quality

```bash
moa ask --persona "David Ogilvy" "Write a headline for an AI invoice tool"
moa ask --persona "Ann Handley" "Review this landing page copy for clarity"
moa ask --persona content "Does this email subject line work?"
```

---

## 6. Advanced Patterns

### 6a. Multi-Layer Verification
**When:** High-stakes queries where you want extra accuracy

```bash
moa ask --layers 2 "Design a payment pipeline with idempotency guarantees"
```

**What happens:** Layer 1 proposes and synthesizes normally. Layer 2 re-runs proposers on the synthesis to catch aggregator errors, then re-aggregates. ~2x cost but catches synthesis mistakes.

---

### 6b. Security Review via Pipe

```bash
cat src/auth/middleware.ts | moa ask --raw "Analyze for security vulnerabilities"
git diff HEAD~3 | moa ask --raw "What are the riskiest changes in this diff?"
```

---

### 6c. Spec Compliance Check

```bash
echo "Spec: Password reset via email link, expires 24h.
Implementation: [paste code]" | moa ask --raw "Does this satisfy the spec?"
```

---

## 7. Trust & Transparency Features

### 7a. Confidence Indicators
Every response includes:
- **Agreement score** (0-100%) with visual bar
- **Domain classification** (FACTUAL/TECHNICAL/CREATIVE/JUDGMENT/STRATEGIC)
- **Domain-specific threshold** (factual questions need higher agreement)
- **Pairwise ranking winner** (which model gave the best response)

### 7b. Correlated Confidence Warning
When models agree strongly on a niche topic, MOA warns:
> ⚠️ High agreement on a specific topic. Models may share the same training data gap.

### 7c. Factual Verification
On factual queries, a cheap model checks proposals for suspicious precision, conflicting numbers, and unqualified claims.

### 7d. Session Memory
MOA logs queries and response previews within a session. The synthesizer is told to acknowledge contradictions with previous answers.

---

## 8. Integration Points

### Via Claude Code
```bash
/moa "question"                    # Adaptive routing query
/moa --persona product "question"  # With personas
/moa --research deep "question"    # Deep research
/moa-debate "question"             # Multi-round debate
/moa-review                        # Expert panel on current changes
```

### Via Terminal
```bash
moa ask "question"                          # Default adaptive
moa ask --persona "DHH" "question"          # Persona
moa ask --research deep "question"          # Deep research
moa ask --layers 2 "question"              # Multi-layer verification
moa debate "question"                       # Peer debate
moa debate --style adversarial "question"   # Angel vs devil
moa review --staged                         # Code review
moa review --staged --personas --discourse  # Full review with discourse
moa status                                  # Budget + model roster
moa history --cost                          # Spend tracking
moa verify                                 # Test model connectivity
```

### Via Pipe
```bash
git diff HEAD~3 | moa ask --raw "Riskiest changes?"
cat package.json | moa ask --raw "Outdated or vulnerable deps?"
curl -s api.example.com/health | moa ask --raw "Normal response?"
```

---

## 9. Persona Reference

| Category | Personas | Best For |
|----------|----------|----------|
| **code** | Martin Fowler, Kent Beck, Rich Hickey, Sandi Metz | Code review, refactoring, testing, simplicity |
| **architecture** | Kelsey Hightower, Martin Kleppmann, DHH | Infrastructure, distributed systems, monolith advocacy |
| **product** | Shreya Doshi, Marty Cagan, April Dunford | Strategy, positioning, prioritization |
| **content** | David Ogilvy, Ann Handley | Headlines, copy, voice, clarity |
| **builder** | Pieter Levels, Daniel Vassallo | Ship fast, small bets, solopreneur decisions |

Select by name (`--persona "DHH,Kent Beck"`) or category (`--persona product`). Fuzzy matching — `"dhh"` finds DHH.

---

## Cost Reference

| Use Case | Mode | Cost | Latency |
|----------|------|------|---------|
| Quick question | adaptive:simple | ~$0.001 | 1-3s |
| Standard query | adaptive:standard | ~$0.05 | 8-15s |
| Complex decision | adaptive:complex | ~$0.15 | 15-30s |
| Deep research | --research deep | ~$0.15-0.30 | 30-60s |
| Code review | moa review | ~$0.05-0.10 | 15-25s |
| Debate (2 rounds) | moa debate | ~$0.15-0.25 | 30-60s |
| Adversarial debate | --style adversarial | ~$0.20-0.30 | 60-120s |
| Multi-layer | --layers 2 | ~2x base | ~2x base |

> **Daily budget:** $5.00/day (configurable). At typical usage, that's 50-100+ queries/day.
