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
Each model has provided a final answer to the user's question after multiple rounds \
of revision.

Your job:
1. Identify points of agreement across all models (these are likely correct)
2. Identify points of disagreement and determine which model's reasoning is strongest
3. Flag any claims that no model adequately supported with evidence
4. Synthesize the best elements into a single, authoritative answer

Do NOT mention the debate process. Write as if you are directly answering the user.

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
FOR the proposition. Find supporting evidence, anticipate objections, and construct \
a compelling argument. Be thorough and persuasive.

{previous_round}"""

DEBATE_DEVIL_SYSTEM = """You are the CRITIC. Build the strongest possible case \
AGAINST the proposition. Find weaknesses, counter-evidence, hidden risks, and \
unstated assumptions. Be rigorous and unsparing.

{previous_round}"""

DEBATE_ADVERSARIAL_JUDGE_SYSTEM = """You are judging an adversarial debate. An \
Advocate argued FOR the proposition and a Critic argued AGAINST it, over multiple \
rounds of revision.

Your job:
1. Identify where the Advocate made the strongest points
2. Identify where the Critic exposed genuine weaknesses
3. Determine which side had the stronger overall argument and why
4. Synthesize a balanced, authoritative answer that accounts for both perspectives

Do NOT mention the debate process. Write as if you are directly answering the user.

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

CLASSIFY_QUERY_PROMPT = """Classify this query into one of three complexity tiers AND one domain:

Tiers:
- SIMPLE: Factoid, lookup, single clear answer, unambiguous instruction
- STANDARD: Requires reasoning or analysis, but one best answer likely exists
- COMPLEX: Multiple valid perspectives, subjective, contentious, multi-step design decision

Domains:
- FACTUAL: Verifiable facts, definitions, lookups, "what is X?"
- TECHNICAL: Implementation details, how-to, debugging, API usage
- CREATIVE: Design, UX, naming, branding, content creation
- JUDGMENT: Opinions, trade-offs, "should I X or Y?"
- STRATEGIC: Architecture, business decisions, long-term planning

Respond with ONLY a JSON object, no other text:
{"tier": "SIMPLE" | "STANDARD" | "COMPLEX", "domain": "FACTUAL" | "TECHNICAL" | "CREATIVE" | "JUDGMENT" | "STRATEGIC"}"""


PAIRWISE_RANK_PROMPT = """Compare these two responses to the same question. \
Which is more accurate, complete, and well-reasoned?

Consider: factual correctness, depth of reasoning, completeness, and practical usefulness.

Respond with ONLY a JSON object, no other text:
{"winner": "A" or "B" or "TIE", "reason": "one sentence"}"""


DISAGREEMENT_SYNTHESIS_PROMPT = """You are a debate analyst synthesizing multiple model responses.

The user asked: {query}

These models responded to the same question and DISAGREE on key points.

Your job:
1. Identify the core points of AGREEMENT across models
2. Identify the specific points of DISAGREEMENT
3. For each disagreement, attribute each position to the model that holds it
4. Assess which position is stronger and why (with reasoning)
5. Give your final recommendation

Format:

## Points of Agreement
- [shared conclusions]

## Points of Disagreement
| Issue | Position A (Model) | Position B (Model) | Stronger |
|-------|-------------------|-------------------|----------|
| ... | ... | ... | ... |

## Recommendation
[Your synthesized answer, acknowledging where genuine uncertainty exists]

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


CONSENSUS_AGGREGATOR_PROMPT = """You have been provided with responses from multiple \
models to the user's query. The models largely AGREE on the answer.

Your job is to return the most complete, accurate, and well-written version. \
Incorporate the best elements from each response. Do NOT mention multiple models \
or that you are synthesizing.

Responses:
{proposals}"""

