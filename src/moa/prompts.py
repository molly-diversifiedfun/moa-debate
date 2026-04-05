"""Prompt templates for MoA aggregation, debate, and code review synthesis."""

# ── MoA Aggregator ─────────────────────────────────────────────────────────────

MOA_AGGREGATOR_SYSTEM = """You have been provided with a set of responses from various \
models to the latest user query. Your job is to synthesize these into a single, \
high-quality response.

Critically evaluate the information provided by each model. Some responses may be \
biased, incomplete, or incorrect. Do not simply merge them — identify the most \
accurate and well-reasoned points across all responses, resolve contradictions by \
reasoning about which answer is more likely correct, and produce a refined, accurate, \
and comprehensive reply.

Do NOT mention that you are synthesizing multiple responses. Write as if you are \
directly answering the user's question.

Responses from models:
{proposals}"""


# ── Debate ─────────────────────────────────────────────────────────────────────

DEBATE_ROUND_SYSTEM = """You previously answered a question. Other models have also \
answered the same question. Their responses are shown below.

Review their responses carefully. If you see points that are more accurate or \
well-reasoned than yours, update your answer accordingly. If you believe your original \
answer was correct where others disagree, explain why with specific reasoning.

Produce your revised answer — a complete, self-contained response to the original \
question incorporating any improvements.

Other models' responses:
{other_responses}"""

DEBATE_JUDGE_SYSTEM = """You are judging a multi-round debate between AI models. \
Each model has refined their position through challenge and revision rounds.

Synthesize into this exact format:

## Verdict
[The authoritative answer, incorporating the strongest reasoning from all models. Write as if directly answering the user.]

## What the Debate Settled
- [Bullet points of conclusions that ALL models converged on after debate — high confidence]

## Remaining Disagreements
- **[Model]**: [Position they held even after seeing challenges]
[Only include genuine remaining splits. If models fully converged, write "None — models reached full consensus."]

## Strongest Arguments
- **[Model]** won on [topic]: [1 sentence why their reasoning was strongest]
[Repeat for each model that made a notably strong argument]

Final positions from each model:
{final_positions}"""


# ── Multi-layer MoA: verification pass (from togethercomputer/MoA) ────────────

MOA_VERIFY_SYSTEM = """A previous synthesis of multiple model responses is shown below. \
Your job is to evaluate it critically:

1. Is it factually accurate? Flag any claims that seem wrong or unsupported.
2. Did it miss important points from the original responses?
3. Did it introduce errors or biases not present in any original response?
4. Is it well-structured and clear?

If the synthesis is good, say so briefly and reproduce it. \
If it has issues, provide a corrected version.

Previous synthesis:
{synthesis}

Original model responses:
{proposals}"""


# ── Debate: Challenge round (from duh) ────────────────────────────────────────

DEBATE_CHALLENGE_SYSTEM = """You are reviewing other models' responses to a question. \
Your job is to find FLAWS — errors, weak reasoning, missing considerations, \
unsupported claims, or hidden assumptions.

Rules:
- You MUST identify at least one flaw per response. Do not agree with everything.
- Be specific: quote the exact claim you're challenging and explain why it's wrong or weak.
- If a response is genuinely excellent, challenge the scope or assumptions instead.
- Do NOT rewrite your own answer. Only critique others.

Other models' responses:
{other_responses}"""

DEBATE_REVISION_WITH_CHALLENGES_SYSTEM = """You previously answered a question. Other \
models challenged your response and found potential flaws. Their challenges are below.

Address each challenge directly:
- If the challenge is valid, update your answer to fix the issue.
- If the challenge is wrong, explain why with specific reasoning.

Then produce your revised answer — complete and self-contained.

Challenges of your response:
{challenges}

Other models' current responses:
{other_responses}"""


# ── Debate: Adversarial roles (from Multi-Agents-Debate) ─────────────────────

DEBATE_ANGEL_SYSTEM = """You are the ADVOCATE. Build the strongest possible case \
FOR the proposition.

Rules:
- State your assumptions explicitly: "I'm assuming X because the plan doesn't say"
- If critical context is missing, flag it: "I'd need to know Y before fully committing to this"
- Build conditional arguments when appropriate: "If they've validated demand, then A. If not, then B."
- Be thorough and persuasive, but honest about what you don't know.

{previous_round}"""

DEBATE_DEVIL_SYSTEM = """You are the CRITIC. Build the strongest possible case \
AGAINST the proposition.

Rules:
- Identify unstated assumptions and challenge them: "This assumes X, but what if...?"
- Flag missing context that would change your assessment: "Without knowing Y, I have to assume the worst"
- Don't just attack — suggest what would make this viable: "This would work IF..."
- Be rigorous and unsparing, but constructive.

{previous_round}"""

DEBATE_ADVERSARIAL_JUDGE_SYSTEM = """You are judging an adversarial debate. An \
Advocate argued FOR and a Critic argued AGAINST, over multiple rounds.

Synthesize into this exact format:

## Verdict
[Your balanced, authoritative answer. Be direct about the recommendation.]

## Key Assumptions
[What assumptions did both sides make? Flag any that are unverified and would change the verdict if wrong.]

## Advocate's Strongest Points
- [2-3 bullet points — the best arguments FOR]

## Critic's Strongest Points
- [2-3 bullet points — the best arguments AGAINST]

## It Depends On...
[2-3 conditional scenarios that change the answer. Format as:]
- **If [condition]**: then [recommendation]. Example: "If you've already validated with 10+ users, the risk profile changes significantly."
- **If [opposite condition]**: then [different recommendation].

## What Changed During Debate
- [What did the Advocate concede or strengthen?]
- [What did the Critic concede or strengthen?]

## How to De-Risk This
[3-5 specific, actionable steps to reduce risk before fully committing. These should be things you can do in days, not months. Example: "Run a landing page test for 2 weeks before writing code."]

## Bottom Line
[1-2 sentences: which side had the stronger case, and what's the single most important thing to do next?]

Advocate's final position:
{angel_position}

Critic's final position:
{devil_position}"""


# ── Code Review Synthesis ──────────────────────────────────────────────────────

CODE_REVIEW_AGGREGATOR = """You are synthesizing code review findings from three \
specialized reviewers: a Security Reviewer, an Architecture Reviewer, and a \
Performance Reviewer. Each has analyzed the same code changes from their area of \
expertise.

Your job:
1. Deduplicate findings that multiple reviewers flagged
2. Prioritize by severity: Critical > High > Medium > Low
3. For each finding, preserve the specific file, line, and suggested fix
4. Add your own assessment if you spot issues the specialists missed
5. Conclude with a clear APPROVE / REQUEST CHANGES / BLOCK verdict

Format your output as:

## Review Summary
[1-2 sentence overview + verdict]

### 🔴 Critical (blocks merge)
- [finding + file:line + fix]

### 🟡 Important (should fix)
- [finding + file:line + fix]

### 🟢 Suggestions (nice to have)
- [suggestion]

### ✅ Strengths
- [positive observations]

Reviewer findings:
{findings}"""


# ── Code Review: Reviewer discourse (from Open Code Review) ──────────────────

REVIEWER_DISCOURSE_SYSTEM = """You are the {role} reviewer. You already reviewed this code. \
Now other specialists have shared their findings.

React to their findings using ONLY these structured moves:
- AGREE: "I confirm [finding] — here's additional evidence: ..."
- CHALLENGE: "I disagree with [finding] because ..."
- CONNECT: "[My finding X] relates to [their finding Y] because ..."
- SURFACE: "Reading their findings, I now notice: ..."

Only use moves that add value. Don't react to every finding. Be specific.

Your original findings:
{own_findings}

Other reviewers' findings:
{other_findings}"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def format_proposals(proposals: list, model_names: list = None) -> str:
    """Format a list of proposals into a numbered string for injection into prompts."""
    parts = []
    for i, proposal in enumerate(proposals):
        label = model_names[i] if model_names and i < len(model_names) else f"Model {i+1}"
        parts.append(f"--- {label} ---\n{proposal}")
    return "\n\n".join(parts)


def format_review_findings(findings: list) -> str:
    """Format specialized review findings for the aggregator."""
    parts = []
    for finding in findings:
        parts.append(f"--- {finding['role']} ---\n{finding['content']}")
    return "\n\n".join(parts)


# ── Adaptive flow prompts ──────────────────────────────────────────────────────

CLASSIFY_QUERY_PROMPT = """Classify this query into one complexity tier AND one domain.

Tiers:
- SIMPLE: Factoid, lookup, single clear answer. Example: "What port does HTTP use?"
- STANDARD: Requires reasoning, but one best answer likely exists. Example: "How do I handle errors in async JavaScript?"
- COMPLEX: Multiple valid perspectives, subjective, contentious. Example: "Should we use microservices or a monolith?"

Domains (choose based on what the question is REALLY asking, not what tools it mentions):
- FACTUAL: Verifiable facts, definitions, lookups. "What is X?" "How many Y?"
- TECHNICAL: Implementation HOW-TO, debugging, specific API usage. "How do I configure X?" "Why is this error happening?"
- CREATIVE: Design, UX, naming, branding, content creation. "What should I name this?" "Design a logo concept."
- JUDGMENT: Trade-offs between options, "should I X or Y?" where both are valid. "Redis vs Memcached?" "Is TypeScript worth it?"
- STRATEGIC: Business decisions, platform/architecture choices for a team/company, long-term planning. "Should our startup use Supabase or Firebase?" "Monorepo vs polyrepo for our org?" "Build vs buy?"

Key distinction: "How do I use Supabase auth?" = TECHNICAL. "Should our startup use Supabase or Firebase?" = STRATEGIC. The presence of tool names doesn't make it TECHNICAL — the nature of the decision does.

Respond with ONLY a JSON object, no other text:
{"tier": "SIMPLE" | "STANDARD" | "COMPLEX", "domain": "FACTUAL" | "TECHNICAL" | "CREATIVE" | "JUDGMENT" | "STRATEGIC"}"""


PAIRWISE_RANK_PROMPT = """Compare these two responses to the same question. \
Which is more accurate, complete, and well-reasoned?

Consider: factual correctness, depth of reasoning, completeness, and practical usefulness.

Respond with ONLY a JSON object, no other text:
{"winner": "A" or "B" or "TIE", "reason": "one sentence"}"""


DISAGREEMENT_SYNTHESIS_PROMPT = """You are synthesizing multiple model responses that DISAGREE on key points.

The user asked: {query}

Synthesize into this exact format:

## Answer
[Your best synthesized answer, incorporating the strongest reasoning from all models. Write as if directly answering the user. Acknowledge genuine uncertainty where it exists.]

## Where Models Agreed
- [Bullet points of shared conclusions — these are high-confidence]

## Where Models Differed
- **[Model name]**: [Their distinct position, in 1-2 sentences]
[Repeat for each model with a meaningfully different take]

## Why This Answer
[2-3 sentences explaining which model's reasoning was strongest and why. Name the models. This is the "show your work" that builds trust.]

Model responses:
{proposals}"""


# ── Research prompts ──────────────────────────────────────────────────────────

SEARCH_QUERY_DERIVATION_PROMPT = """Given a user's question, derive 2-3 focused web search queries \
that would find authoritative documentation, official docs, or technical references to help answer it.

Rules:
- Make queries specific and technical (not the original question verbatim)
- Target official documentation, GitHub repos, RFCs, or authoritative sources
- If the question mentions a specific tool/library/framework, include its name
- Keep each query under 10 words

Respond with ONLY a JSON object, no other text:
{"queries": ["search query 1", "search query 2"]}"""


IDENTIFY_GAPS_PROMPT = """You have initial research for a question. Identify what's still \
missing or unclear that would require additional searches.

Rules:
- Only suggest follow-up queries if there are genuine gaps
- Target specific missing details, not broad topics
- If the research is sufficient, return an empty list
- Keep each query under 10 words

Respond with ONLY a JSON object, no other text:
{"queries": ["follow-up query 1", "follow-up query 2"]}"""


DEEP_RESEARCH_SYNTHESIS_PROMPT = """You are answering a question using research gathered \
from web sources. The research context is provided below.

Rules:
- Ground your answer in the provided sources
- Cite sources by name/URL when making specific claims
- If sources conflict, note the conflict and reason about which is more authoritative
- If the research doesn't fully answer the question, say what's still uncertain
- Be specific and technical — the user chose deep research because they need precision"""


STRATEGIC_ADDENDUM = """

IMPORTANT — this is a strategic/judgment question. In addition to the format above, \
add these sections at the end:

## It Depends On...
[2-3 conditional scenarios where the answer changes. Format as:]
- **If [condition]**: then [recommendation].
- **If [opposite condition]**: then [different recommendation].
[Focus on the conditions the asker is least likely to have considered.]

## How to De-Risk This
[3-5 specific, actionable steps to reduce risk before fully committing. \
These should be things you can do in days or weeks, not months. Examples: \
"Run a landing page test," "Interview 10 potential customers," "Build a prototype in a weekend."]
"""


FACTUAL_VERIFICATION_PROMPT = """You are a fact-checker. Multiple AI models answered the \
same question. Check their responses for:

1. Suspicious precision — exact numbers, dates, or statistics that seem too specific to be \
   recalled accurately (e.g., "47.3 million" for a population that's hard to measure)
2. Internal inconsistency — do the models cite different numbers for the same claim?
3. Confident claims without qualification — are they stating uncertain things as facts?

Respond with ONLY a JSON object:
{"suspicious": true/false, "warning": "one sentence explaining the concern", "claims": ["claim 1 to verify", "claim 2"]}

If everything looks consistent and well-qualified, return:
{"suspicious": false, "warning": "", "claims": []}"""


CONSENSUS_AGGREGATOR_PROMPT = """You have been provided with responses from multiple \
models to the user's query. The models largely AGREE on the answer.

Synthesize into this exact format:

## Answer
[The best, most complete answer. Write as if directly answering the user. Do NOT mention models or synthesis.]

## Key Points of Agreement
- [3-5 bullet points where all models converged — these are high-confidence conclusions]

## Unique Contributions
- **[Model name]**: [1 sentence — what unique insight this model added that others missed]
[Repeat for each model that contributed something distinct. Skip models that added nothing new.]

Responses:
{proposals}"""

