# MoA Use Cases — Complete Reference

Every way `moa` fits into your workflow, with the right command for each situation.

---

## 1. Daily Development

### 1a. Quick Questions (SIMPLE)
**When:** Factoid, syntax lookup, API usage, "how do I…?"  
**Mode:** `moa ask` (adaptive auto-classifies as SIMPLE → 1-2 fast models, no aggregation)

```bash
moa ask "What's the difference between useEffect and useLayoutEffect?"
moa ask "How do I create a temporary table in PostgreSQL?"
```

**What happens:** Haiku or Gemini Flash answers directly. 1 API call, ~$0.001.

---

### 1b. Design Decisions (COMPLEX)
**When:** "Should I use X or Y?" — architecture, framework choice, trade-off analysis  
**Mode:** `moa ask` (auto-classifies as COMPLEX → 3-4 frontier models + synthesis)

```bash
moa ask "Should I use microservices or a monolith for a 3-person SaaS startup?"
moa ask "Redis vs Memcached for session storage in a Next.js app with 50K DAU?"
```

**What happens:** Opus, GPT-5.4, Gemini Pro, and Sonnet all propose independently → synthesizer detects if they agree or disagree → surfaces each position with attribution if they disagree.  
~$0.15, 15-30s.

---

### 1c. Contentious Decisions (DEBATE)
**When:** You suspect models will have different opinions and you want them to argue it out  
**Mode:** `moa debate`

```bash
moa debate "Is it better to use TypeScript strict mode from day one, or add it incrementally?"
moa debate --rounds 3 "Should we use a GraphQL gateway or REST with BFF pattern?"
```

**What happens:** 3 models independently answer → see each other's answers → revise over 2-3 rounds → judge synthesizes. Models actually change their positions when they see better arguments.  
~$0.20-0.40, 30-60s.

---

## 2. Research & Fact-Checking

### 2a. Cross-Model Fact Validation
**When:** You need to validate a claim, check if something is still true, or verify docs  
**Mode:** `moa ask` with explicit validation framing

```bash
moa ask "Is it true that React Server Components can't use useState? Verify with specifics."
moa ask "Does AWS Lambda still have a 15-minute timeout limit as of 2026?"
```

**Why MoA:** Individual models have training cutoffs and biases. When 3 models from different providers agree on a fact, it's almost certainly correct. When they disagree, you know to dig deeper.

---

### 2b. Deep Research Questions
**When:** Complex technical investigation, comparing approaches across multiple dimensions  
**Mode:** `moa ask` or `moa debate` for particularly nuanced topics

```bash
moa ask "Compare Drizzle ORM vs Prisma vs TypeORM for a production Next.js app. 
Consider: type safety, migration story, performance, bundle size, and community."

moa debate "What's the best authentication strategy for a multi-tenant SaaS? 
Compare: per-tenant IdP, shared IdP with tenant claims, and per-tenant database isolation."
```

**Why MoA:** Each model has seen different codebases, benchmarks, and real-world deployments. The ensemble catches blind spots that any single model would miss.

---

### 2c. Validating AI-Generated Code
**When:** You got code from one model and want to verify it works correctly  
**Mode:** `moa ask` — paste the code and ask for review

```bash
moa ask "Review this async Python function for race conditions, error handling, 
and edge cases: [paste code]"
```

**Why MoA:** The model that wrote the code has a blind spot for its own bugs. Different models catch different classes of errors.

---

## 3. Quality Assurance

### 3a. Architecture Review  
**When:** Evaluating system design before implementation  
**Mode:** `moa ask` or `moa debate` for high-stakes decisions

```bash
moa ask "Critique this architecture: Next.js frontend → tRPC → PostgreSQL with 
Drizzle → Redis cache → S3 for media. We expect 100K users in year one."

moa debate "We're choosing between event sourcing and CRUD for our order management 
system. 3 engineers, 6-month runway. Which is the right call?"
```

**Why MoA:** Architecture mistakes are the most expensive to fix. Getting 3-4 models to independently evaluate catches issues like: missing rate limiting, wrong caching strategy, over-engineering.

---

### 3b. Security Review
**When:** Evaluating code or config for security vulnerabilities  
**Mode:** `moa ask` with explicit security framing

```bash
cat src/auth/middleware.ts | moa ask --raw "Analyze this authentication middleware 
for security vulnerabilities. Check for: JWT validation issues, timing attacks, 
CSRF, session fixation, and privilege escalation."
```

**Why MoA:** Security is where model diversity matters most. GPT excels at pattern-matching known CVEs, Sonnet at logical reasoning about auth flows, Gemini at finding edge cases in input validation.

---

### 3c. Spec Compliance Check
**When:** Verifying that implementation matches requirements  
**Mode:** Pipe context into `moa ask`

```bash
echo "Spec: User must be able to reset password via email link that expires in 24h.
Implementation: [paste relevant code]" | moa ask --raw "Does this implementation 
fully satisfy the spec? List any missing acceptance criteria."
```

---

## 4. Advanced Patterns

### 4a. Self-Critique / Red-Teaming
**When:** You built something and want models to find weaknesses  
**Mode:** `moa ask --cascade` or `moa debate` for thorough analysis

```bash
moa ask "Critique the architecture of this system: [describe system]. 
What are the top 3 weaknesses and how would you fix them?"

moa debate "Play devil's advocate: Why should we NOT use [approach]? 
What are the hidden risks and failure modes?"
```

**This is how MoA redesigned itself** — we asked it to critique its own cascade architecture, and it identified the binary confidence gate, cost scaling, and naive conflict resolution weaknesses.

---

### 4b. Content & Copy Review
**When:** Evaluating marketing copy, blog posts, documentation for quality  
**Mode:** `moa ask` — models are surprisingly good at editorial feedback

```bash
moa ask "Review this landing page copy for clarity, persuasiveness, and potential 
objections a technical buyer would have: [paste copy]"
```

---

### 4c. Debugging Assistance
**When:** You're stuck on a bug and want fresh perspectives  
**Mode:** `moa ask` with error context

```bash
moa ask "I'm getting 'TypeError: Cannot read properties of undefined (reading map)' 
in this React component. The data should be loaded by now because I'm using Suspense. 
Here's the component: [paste]. What's wrong?"
```

**Why MoA:** Different models have been trained on different debugging patterns. One might spot a race condition, another a missing null check, another an incorrect Suspense boundary.

---

### 4d. Learning & Explanation
**When:** You want a thorough, accurate explanation of a complex concept  
**Mode:** `moa ask` (auto-routes STANDARD or COMPLEX depending on topic)

```bash
moa ask "Explain how the V8 garbage collector works, including generational 
collection, incremental marking, and concurrent sweeping. Use concrete examples."

moa ask "What are the key differences between OAuth 2.0's authorization code flow, 
PKCE flow, and device authorization flow? When should I use each?"
```

---

## 5. Integration Points

### Via Claude Code (Effortless)
| Command | Use case |
|---------|----------|
| `/moa "question"` | Any question — adaptive routing picks the right tier |
| `/moa-debate "question"` | Contentious design decisions |
| `@researcher` | Auto-validates findings via MoA cascade |
| `@reviewer` | Escalates architectural questions to MoA |

### Via Terminal (Any Project)
```bash
moa ask "question"           # Adaptive (default)
moa ask --cascade "question" # Legacy cascade
moa ask --tier pro "question" # Manual tier selection
moa debate "question"        # Multi-round debate
moa status                   # Budget + model roster
moa history --cost           # Spend tracking
moa verify                   # Test model connectivity
```

### Via Pipe (Scripting)
```bash
git diff HEAD~3 | moa ask --raw "What are the riskiest changes in this diff?"
cat package.json | moa ask --raw "Are any of these dependencies outdated or vulnerable?"
curl -s api.example.com/health | moa ask --raw "Is this health check response normal?"
```

---

## Cost Reference

| Use Case | Mode | Est. Cost | Latency |
|----------|------|-----------|---------|
| Quick question | SIMPLE | ~$0.001 | 1-3s |
| Design decision | STANDARD | ~$0.05 | 8-15s |
| Architecture review | COMPLEX | ~$0.15 | 15-30s |
| Multi-round debate | debate (2 rounds) | ~$0.20-0.40 | 30-60s |
| Code review via pipe | ask --raw | ~$0.05 | 8-15s |
| Fact validation | STANDARD | ~$0.05 | 8-15s |

> **Daily budget:** $5.00/day. At mostly SIMPLE/STANDARD queries, that's **100+ queries/day**.
