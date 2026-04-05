# When to Use MOA — Real Scenarios

Not a feature list. These are situations you'll actually be in, and how MOA helps.

---

## "I need to make an architecture decision and I don't want to get it wrong"

You're picking a database, choosing a framework, or deciding whether to split a monolith. The wrong call costs months.

```bash
# Get 3-4 frontier models to independently analyze your options
moa ask "We have a Next.js app with 50K DAU. Should we use Redis or Memcached for session storage? We're on AWS with a 3-person team."

# Want DHH's take specifically?
moa ask --persona "DHH" "We're considering moving from our Rails monolith to microservices. The team is 4 engineers. Convince me this is a bad idea."

# Or let two models fight about it
moa debate --style adversarial "Should we migrate from PostgreSQL to DynamoDB for our event storage?"
```

**Why MOA beats asking one model:** Claude might favor one approach, GPT another. When all three independently say "don't do it" — that's a strong signal. When they disagree, the output tells you exactly where and why.

---

## "I wrote code and I want a real review, not a rubber stamp"

You're about to merge something and want actual scrutiny — not "looks good to me."

```bash
# 4 specialist reviewers (security, architecture, performance, correctness)
moa review --staged

# Or get reviewed by famous engineers who won't be nice about it
moa review --staged --persona "Rich Hickey"
# "Is this simple or just easy? You're complecting three unrelated concerns."

moa review --staged --persona "Sandi Metz"
# "This class has 7 constructor parameters. The limit is 4."

# Want reviewers to challenge EACH OTHER's findings?
moa review --staged --discourse
```

**Why MOA beats a single reviewer:** GPT-4.1 catches SQL injection that Sonnet misses. Gemini flags the N+1 query that both missed. Different models have different training data — they literally see different bugs.

---

## "I did a bunch of research and I need someone to sanity-check my plan"

You've been researching for hours. You have notes, a plan, maybe a brief. You want a gut-check before you commit.

```bash
# Pipe your research + plan directly
cat research-notes.md implementation-plan.md | moa ask "Given this research, is this plan solid? What am I missing? What would you cut?"

# Ask product thinkers specifically
cat plan.md | moa ask --persona product "Is this a real product or a feature factory? What would Shreya Doshi say about the leverage here?"

# Let the plan get attacked
cat plan.md | moa debate --style adversarial "Should we execute this plan as written?"

# Or have specific experts weigh in
cat architecture-doc.md | moa ask --persona "Martin Kleppmann,Kelsey Hightower" "Review this architecture for distributed systems pitfalls"
```

**Why MOA:** Three models reading your plan catch different blind spots. One notices the missing error handling. Another questions your scaling assumptions. A third asks why you're building something you could buy.

---

## "I'm building a side project and I need to ship fast"

You're a solopreneur or indie hacker. You don't have a team to bounce ideas off. You need practical advice from people who've done it.

```bash
# Ask the builders
moa ask --persona builder "I want to build a SaaS tool for freelancers to track invoices. What's the fastest path to first revenue?"
# Pieter Levels: "Ship in a weekend. No database. localStorage."
# Daniel Vassallo: "Sell a template first. Don't build software until 10 people pay."

# Specific persona for specific advice
moa ask --persona "Pieter Levels" "Can I ship this without a backend?"

moa ask --persona "Daniel Vassallo" "Should I build an audience or the product first?"

# Product positioning
moa ask --persona "April Dunford" "How do I position my tool against Notion, which is free?"
```

---

## "The models are giving me a confident answer but I'm not sure I trust it"

You asked about a specific API, a niche tool, or a technical detail — and the answer sounds right but feels too confident.

```bash
# MOA auto-detects this. If models disagree, it searches the web and re-asks.
moa ask "What are the rate limits for the Firecrawl search endpoint?"

# Force deep research if you know it's niche
moa ask --research deep "How do I configure Turborepo remote caching with a self-hosted server?"

# The output tells you what happened:
# 🔍 RESEARCHED — models initially disagreed → web search → re-asked with docs
# ⚠️ High agreement on a specific topic. Models may share the same training data gap.
```

**The trust signals:** Every response shows you the confidence bar (██████░░░░), which models agreed, which disagreed, and why the synthesizer picked one model's answer over another. You can verify instead of trust.

---

## "I need to validate a claim or fact-check something"

Someone told you something. An AI told you something. You want to know if it's actually true.

```bash
moa ask "Is it true that React Server Components can't use useState? Verify with specifics."

moa ask "Does AWS Lambda still have a 15-minute timeout limit as of 2026?"

# When models cite different numbers, the factual verifier flags it:
# 🔬 Verification: Models cite conflicting values (15 min vs 10 min)
```

**Why MOA:** If Claude says "yes" and GPT says "no" — you know to look it up. If all three say the same thing with specifics, you can be confident. A single model can hallucinate; three independent models hallucinating the same wrong answer is much rarer.

---

## "I'm writing copy and I want it to not sound like AI wrote it"

You need a headline, a landing page, an email — and you want it to be specific, persuasive, and human.

```bash
# Ogilvy: specific, benefit-driven, long-form sells
moa ask --persona "David Ogilvy" "Write 5 headlines for a landing page selling an AI invoice tool for freelancers"

# Handley: clear, conversational, no jargon
moa ask --persona "Ann Handley" "Review this email for clarity. Would a real person say this out loud?"

# Both perspectives at once
moa ask --persona content "Rewrite this landing page copy. The current version sounds like a robot wrote it."
```

---

## "We're debating something on the team and we need structured thinking"

Two engineers disagree. The PM has a different opinion. Nobody's going to change their mind without structured arguments.

```bash
# Peer debate: models challenge each other, find flaws, revise
moa debate "Should we use event sourcing or CRUD for our order management system?"

# Adversarial: one side argues FOR, one argues AGAINST
moa debate --style adversarial "Should we rewrite our backend in Rust?"

# Persona debate: specific thinkers argue
moa debate --persona "DHH,Kelsey Hightower" "Do we actually need Kubernetes?"

# The output shows:
# - What the debate settled (things all models agreed on after arguing)
# - Remaining disagreements (genuine open questions)
# - Strongest arguments (which model made the best case)
# - What changed during debate (who conceded what)
```

**Why debate over just asking:** Models that revise after seeing challenges produce better reasoning than models answering in isolation. The challenge round prevents sycophantic agreement — models MUST find flaws before they can agree.

---

## "I want to review code but I want a specific perspective, not generic feedback"

Different reviewers catch different things. A security specialist won't notice bad test coverage. A TDD expert won't catch SQL injection.

```bash
# Security-focused review
cat src/auth/*.py | moa review --raw

# "Is this over-engineered?" — ask Rich Hickey
cat src/services/ | moa review --persona "Rich Hickey"

# "Where are the tests?" — ask Kent Beck
moa review --staged --persona "Kent Beck"

# Architecture review from the ops perspective
cat docker-compose.yml k8s/ | moa review --persona architecture

# Full review with discourse: reviewers react to each other
moa review --staged --personas --discourse
# Security: "I found SQL injection on line 42"
# Architecture: "CONNECT — that same function also violates SRP"
# Performance: "AGREE — and it's called in a loop, making it O(n) injection risk"
```

---

## "I need to make a high-stakes decision and want maximum confidence"

Payment systems, auth flows, data migrations — things where being wrong costs real money.

```bash
# Multi-layer verification: proposers → synthesize → proposers check the synthesis → re-synthesize
moa ask --layers 2 --tier ultra "Design a payment processing pipeline with idempotency guarantees for a system handling $10M/month"

# Use --debug to see exactly what was sent to models
moa ask --debug --layers 2 "Design the retry logic for failed payment captures"
```

---

## "I'm in Claude Code and want quick access"

MOA integrates as slash commands — no terminal switching needed.

```bash
# In Claude Code:
/moa "Should we add a cache layer?"
/moa --persona product "Is this feature worth building?"
/moa --research deep "How does Vercel Workflow DevKit handle retries?"

/moa-debate "Monorepo vs polyrepo?"
/moa-debate --style adversarial "Should we rewrite in Go?"

/moa-review                    # Review staged changes
/moa-review --personas         # Fowler/Beck/Hickey/Metz review
```

---

## Quick Reference: Picking the Right Mode

| Situation | Command | Cost | Time |
|-----------|---------|------|------|
| Quick lookup | `moa ask "..."` | ~$0.001 | 2s |
| Need reasoning | `moa ask "..."` | ~$0.05 | 10s |
| Architecture decision | `moa ask --persona architecture "..."` | ~$0.15 | 20s |
| Niche tooling question | `moa ask "..."` (auto-researches) | ~$0.10 | 15s |
| Deep research | `moa ask --research deep "..."` | ~$0.25 | 45s |
| Code review | `moa review --staged` | ~$0.10 | 20s |
| Persona review | `moa review --staged --persona "name"` | ~$0.05 | 15s |
| Peer debate | `moa debate "..."` | ~$0.20 | 60s |
| Adversarial debate | `moa debate --style adversarial "..."` | ~$0.25 | 90s |
| Plan review | `cat plan.md \| moa ask "Review this"` | ~$0.10 | 15s |
| High-stakes verification | `moa ask --layers 2 --tier ultra "..."` | ~$0.50 | 40s |
