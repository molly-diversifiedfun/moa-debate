"""Decision templates for adversarial debates.

Templates provide domain-specific framing:
- Angel/Devil get light context (what kind of decision, not what to argue)
- Judge gets full evaluation criteria, decision tree hints, de-risk steps

Based on Bandi et al. (2024): constraining advocates causes argument collapse.
Legal systems constrain roles, not arguments. Schmidt & Hunter (1998): structured
evaluation (judge) outperforms structured argumentation (debaters).
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class DecisionTemplate:
    name: str
    description: str
    keywords: List[str]
    # Light context for angel/devil — what kind of decision, not what to argue
    debater_context: str
    # Full structured criteria for the judge
    judge_addendum: str
    # Extra search queries for research phase
    research_queries: List[str]


TEMPLATES: List[DecisionTemplate] = [
    DecisionTemplate(
        name="hire",
        description="Hiring decisions — roles, team composition, senior vs junior, contractors vs FTEs",
        keywords=["hire", "hiring", "candidate", "recruit", "role", "senior vs junior",
                  "contractor", "engineer", "developer", "team member", "FTE"],
        debater_context=(
            "This is a hiring/team composition decision. The stakes include "
            "months of ramp time, team dynamics, and significant financial commitment."
        ),
        judge_addendum="""\
Domain-specific evaluation for hiring decisions:

Evaluate on these criteria:
- **Total cost per productive engineer-year**: Include salary, benefits, recruiter fees, \
  3-6 month ramp time, management overhead. A $150K hire costs ~$250K in year 1.
- **Team bus factor**: Does this hire reduce or increase single-point-of-failure risk?
- **Skill gap severity**: Is the team actively blocked without this skill, or is it a nice-to-have?
- **Management span**: Will this hire require a new manager or overload an existing one?
- **Reversibility**: How costly is a bad hire at month 6? (Usually 1.5-2x annual salary in total waste.)

Decision tree should check:
1. Is the team blocked on shipping? → If yes, bias toward faster-to-productive option.
2. Do you have a senior who can mentor? → If no, hiring junior is higher risk.
3. Is this a core competency or support function? → If support, consider contractor/agency.

De-risk steps must include:
- Paid trial project (1-2 weeks) before full commitment
- Reference checks focused on "would you rehire them?" not "were they nice?"
- Explicit 90-day evaluation checkpoint with written criteria
- Define the "what does success look like at 6 months?" before making the offer""",
        research_queries=[
            "hiring senior vs junior engineers tradeoffs data",
            "engineering team scaling best practices",
        ],
    ),

    DecisionTemplate(
        name="build",
        description="Build vs buy — in-house development vs vendor/SaaS/open-source",
        keywords=["build vs buy", "build or buy", "in-house", "vendor", "SaaS",
                  "third-party", "open source", "off-the-shelf", "custom",
                  "auth0", "stripe", "twilio", "sendgrid", "build it"],
        debater_context=(
            "This is a build-vs-buy decision. The real costs include ongoing maintenance, "
            "not just initial build time. Engineer estimates are historically 2-3x optimistic."
        ),
        judge_addendum="""\
Domain-specific evaluation for build-vs-buy decisions:

Evaluate on these criteria:
- **Honest build time**: Multiply the stated engineering estimate by 2-3x. Include testing, \
  edge cases, documentation, on-call, and the 6 months of maintenance after launch.
- **Total cost of ownership (3-year)**: Build = engineering time + maintenance + on-call + \
  opportunity cost. Buy = license fees + integration time + migration risk.
- **Vendor lock-in severity**: How hard is it to switch vendors in 2 years? Data portability? \
  API compatibility? Contractual exit terms?
- **Differentiator test**: Is this a competitive advantage or commodity infrastructure? \
  If users never see it, buy it.
- **Maintenance orphan risk**: What happens when the person who built it leaves?

Decision tree should check:
1. Is this a competitive differentiator? → If no, buy/use open-source.
2. Does a vendor cover 80%+ of requirements? → If yes, buy and customize the 20%.
3. Do you have the team to maintain it for 3+ years? → If no, don't build.

De-risk steps must include:
- Prototype the hardest part first (1-week spike) before committing
- Get 3 vendor quotes with total 3-year cost projections
- Check if an open-source solution covers 80%+ of needs
- Talk to 2-3 companies who built it in-house — ask about maintenance burden""",
        research_queries=[
            "build vs buy software decision framework",
            "total cost of ownership vendor vs in-house development",
        ],
    ),

    DecisionTemplate(
        name="invest",
        description="Investment decisions — asset allocation, risk/return tradeoffs, financial commitments",
        keywords=["invest", "investment", "portfolio", "returns", "stocks", "bonds",
                  "real estate", "rental", "index fund", "ETF", "crypto", "angel",
                  "seed", "funding", "allocation", "savings"],
        debater_context=(
            "This is an investment/financial allocation decision. What matters is "
            "risk-adjusted returns over the specific time horizon, not absolute returns. "
            "Always consider the worst realistic scenario, not just the average."
        ),
        judge_addendum="""\
Domain-specific evaluation for investment decisions:

Evaluate on these criteria:
- **Risk-adjusted return**: Not just "what could I make?" but "what's the return per unit \
  of risk?" Compare Sharpe ratios or equivalent for the asset class.
- **Liquidity profile**: Can you exit in <30 days without significant loss? If not, \
  the illiquidity premium must justify the lock-up.
- **Time horizon match**: <3 years = prioritize capital preservation. 3-10 years = balanced. \
  >10 years = can tolerate volatility for higher expected returns.
- **Downside scenario**: What happens in the bottom 10% outcome? Can you absorb that loss \
  without changing your lifestyle?
- **Time commitment**: Passive investments (index funds) take 0 hours/month. Active \
  investments (rental property, angel deals) take 10-40 hours/month. Price your time.
- **Tax implications**: After-tax returns are what matter. Tax-advantaged accounts change \
  the math significantly.

Decision tree should check:
1. What's your time horizon? → If <3 years, bias toward liquid, low-volatility assets.
2. Do you have 6 months of expenses in cash? → If no, that comes first.
3. Can you afford to lose 100% of this investment? → If no, reduce position size.
4. Is this active or passive? → If active, add your hourly rate × expected hours to the cost.

De-risk steps must include:
- Start with the smallest viable position (test the thesis before scaling)
- Paper-trade or model returns for 30 days before committing real capital
- Calculate the exact break-even timeline and required return rate
- Define your exit criteria upfront (both profit-taking and stop-loss)""",
        research_queries=[
            "risk adjusted returns comparison asset classes",
            "investment decision framework evidence based",
        ],
    ),
]


def get_template(name: str) -> Optional[DecisionTemplate]:
    """Look up a template by exact name."""
    for t in TEMPLATES:
        if t.name == name:
            return t
    return None


def detect_template(query: str) -> Optional[DecisionTemplate]:
    """Auto-detect the best template from query keywords. Returns None if no match."""
    query_lower = query.lower()
    best_match = None
    best_score = 0
    for t in TEMPLATES:
        score = sum(1 for kw in t.keywords if kw in query_lower)
        if score > best_score:
            best_score = score
            best_match = t
    # Require at least 1 keyword match
    return best_match if best_score >= 1 else None


def list_templates() -> List[DecisionTemplate]:
    """Return all available templates."""
    return list(TEMPLATES)
