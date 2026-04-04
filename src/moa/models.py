"""Model configurations, tiers, cost tracking, and cascade flow definitions."""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ModelConfig:
    """Configuration for a single LLM model."""
    name: str                    # LiteLLM model identifier
    provider: str                # Provider name for display
    env_key: str                 # Environment variable with API key
    input_cost_per_mtok: float   # Cost per million input tokens
    output_cost_per_mtok: float  # Cost per million output tokens
    max_tokens: int = 4096       # Max output tokens
    temperature: float = 0.7     # Default temperature
    strengths: List[str] = field(default_factory=list)  # What this model excels at

    @property
    def available(self) -> bool:
        """Check if the API key for this model is set."""
        return bool(os.environ.get(self.env_key))


# ══════════════════════════════════════════════════════════════════════════════
#  MODEL DEFINITIONS — March 2026 frontier roster
# ══════════════════════════════════════════════════════════════════════════════

# ── Anthropic ──────────────────────────────────────────────────────────────────

CLAUDE_OPUS = ModelConfig(
    name="anthropic/claude-opus-4-20250514",
    provider="Anthropic",
    env_key="ANTHROPIC_API_KEY",
    input_cost_per_mtok=15.00,
    output_cost_per_mtok=75.00,
    temperature=0.1,
    strengths=["deep reasoning", "multi-file code", "architecture", "ambiguous specs"],
)

CLAUDE_SONNET = ModelConfig(
    name="anthropic/claude-sonnet-4-20250514",
    provider="Anthropic",
    env_key="ANTHROPIC_API_KEY",
    input_cost_per_mtok=3.00,
    output_cost_per_mtok=15.00,
    temperature=0.1,
    strengths=["code generation", "balanced reasoning", "synthesis", "low control-flow errors"],
)

CLAUDE_HAIKU = ModelConfig(
    name="anthropic/claude-haiku-4-5-20251001",
    provider="Anthropic",
    env_key="ANTHROPIC_API_KEY",
    input_cost_per_mtok=1.00,
    output_cost_per_mtok=5.00,
    temperature=0.3,
    strengths=["fast evaluation", "classification", "routing", "JSON output"],
)

# ── OpenAI ─────────────────────────────────────────────────────────────────────

GPT_5_4 = ModelConfig(
    name="gpt-5.4",
    provider="OpenAI",
    env_key="OPENAI_API_KEY",
    input_cost_per_mtok=2.50,
    output_cost_per_mtok=15.00,
    strengths=["terminal execution", "speed", "coding", "instruction following"],
)

GPT_4_1 = ModelConfig(
    name="gpt-4.1",
    provider="OpenAI",
    env_key="OPENAI_API_KEY",
    input_cost_per_mtok=2.00,
    output_cost_per_mtok=8.00,
    strengths=["coding", "long context (1M)", "structured output", "cost-efficient frontier"],
)

GPT4O_MINI = ModelConfig(
    name="gpt-4o-mini",
    provider="OpenAI",
    env_key="OPENAI_API_KEY",
    input_cost_per_mtok=0.15,
    output_cost_per_mtok=0.60,
    strengths=["cheap diversity", "fast", "security scanning"],
)

# ── Google ─────────────────────────────────────────────────────────────────────

GEMINI_3_1_PRO = ModelConfig(
    name="gemini/gemini-2.0-flash",
    provider="Google",
    env_key="GEMINI_API_KEY",
    input_cost_per_mtok=0.10,
    output_cost_per_mtok=0.40,
    strengths=["fast reasoning", "1M context", "structured output", "agentic workflows"],
)

GEMINI_2_5_PRO = ModelConfig(
    name="gemini/gemini-2.5-pro",
    provider="Google",
    env_key="GEMINI_API_KEY",
    input_cost_per_mtok=1.25,
    output_cost_per_mtok=10.00,
    strengths=["whole-repo analysis", "1M context", "mobile/infra review"],
)

GEMINI_FLASH = ModelConfig(
    name="gemini/gemini-2.5-flash",
    provider="Google",
    env_key="GEMINI_API_KEY",
    input_cost_per_mtok=0.15,
    output_cost_per_mtok=0.60,
    strengths=["fast proposer", "free tier available", "breadth analysis"],
)

# ── DeepSeek (OPTIONAL — bonus diversity when key is set) ──────────────────────

DEEPSEEK_V3 = ModelConfig(
    name="deepseek/deepseek-chat",
    provider="DeepSeek",
    env_key="DEEPSEEK_API_KEY",
    input_cost_per_mtok=0.28,
    output_cost_per_mtok=0.42,
    strengths=["near-frontier at 1/10th cost", "code quality", "math"],
)

DEEPSEEK_R1 = ModelConfig(
    name="deepseek/deepseek-reasoner",
    provider="DeepSeek",
    env_key="DEEPSEEK_API_KEY",
    input_cost_per_mtok=0.55,
    output_cost_per_mtok=2.19,
    temperature=0.1,
    strengths=["deep reasoning", "math competition", "chain of thought"],
)

# ── xAI (OPTIONAL — bonus diversity when key is set) ──────────────────────────

GROK_4_20 = ModelConfig(
    name="xai/grok-4-0709",
    provider="xAI",
    env_key="XAI_API_KEY",
    input_cost_per_mtok=2.00,
    output_cost_per_mtok=6.00,
    strengths=["real-time knowledge", "live search", "contrarian perspective"],
)

GROK_FAST = ModelConfig(
    name="xai/grok-4.1-fast",
    provider="xAI",
    env_key="XAI_API_KEY",
    input_cost_per_mtok=0.20,
    output_cost_per_mtok=0.50,
    strengths=["fast cheap proposer", "2M context window"],
)

# ── Meta/Together (OPTIONAL — bonus diversity when key is set) ─────────────────

LLAMA_4_MAVERICK = ModelConfig(
    name="together_ai/meta-llama/Llama-4-Maverick-17B-128E-Instruct-Turbo",
    provider="Together/Meta",
    env_key="TOGETHER_API_KEY",
    input_cost_per_mtok=0.22,
    output_cost_per_mtok=0.85,
    strengths=["open-source diversity", "no provider lock-in", "good code"],
)


# ══════════════════════════════════════════════════════════════════════════════
#  MODEL REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

# Core providers (Anthropic, OpenAI, Google) — always in tiers
CORE_MODELS = [
    CLAUDE_OPUS, CLAUDE_SONNET, CLAUDE_HAIKU,
    GPT_5_4, GPT_4_1, GPT4O_MINI,
    GEMINI_3_1_PRO, GEMINI_2_5_PRO, GEMINI_FLASH,
]

# Optional providers — automatically included when keys are set
OPTIONAL_MODELS = [
    DEEPSEEK_V3, DEEPSEEK_R1,
    GROK_4_20, GROK_FAST,
    LLAMA_4_MAVERICK,
]

ALL_MODELS = CORE_MODELS + OPTIONAL_MODELS
MODEL_BY_NAME = {m.name: m for m in ALL_MODELS}


def available_models() -> List[ModelConfig]:
    """Return all models with valid API keys."""
    return [m for m in ALL_MODELS if m.available]


def available_optional() -> List[ModelConfig]:
    """Return optional models that happen to have keys set."""
    return [m for m in OPTIONAL_MODELS if m.available]


# ══════════════════════════════════════════════════════════════════════════════
#  TIER DEFINITIONS
#  Core path: Anthropic + OpenAI + Google (you have keys for these)
#  Optional models auto-included when their keys are set
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Tier:
    """A routing tier with proposer models and an aggregator."""
    name: str
    proposers: List[ModelConfig]         # Core proposers (always attempted)
    optional_proposers: List[ModelConfig] # Bonus proposers (used if key exists)
    aggregator: Optional[ModelConfig]
    description: str

    @property
    def available_proposers(self) -> List[ModelConfig]:
        """Core proposers + any available optional proposers."""
        core = [m for m in self.proposers if m.available]
        bonus = [m for m in self.optional_proposers if m.available]
        return core + bonus

    @property
    def estimated_cost(self) -> float:
        proposer_cost = sum(
            (m.input_cost_per_mtok * 2 + m.output_cost_per_mtok * 1) / 1000
            for m in self.available_proposers
        )
        agg_cost = 0.0
        if self.aggregator and self.aggregator.available:
            agg_cost = (
                self.aggregator.input_cost_per_mtok * 5.5
                + self.aggregator.output_cost_per_mtok * 1.5
            ) / 1000
        return proposer_cost + agg_cost


TIERS = {
    "flash": Tier(
        name="flash",
        proposers=[GEMINI_FLASH],
        optional_proposers=[],
        aggregator=None,
        description="Single Gemini Flash, sub-second (~$0.001)",
    ),
    "lite": Tier(
        name="lite",
        proposers=[GPT4O_MINI, GEMINI_FLASH],            # Core: OpenAI + Google cheap
        optional_proposers=[DEEPSEEK_V3, GROK_FAST, LLAMA_4_MAVERICK],  # Bonus diversity
        aggregator=CLAUDE_SONNET,
        description="2-5 cheap proposers → Sonnet (~$0.05)",
    ),
    "pro": Tier(
        name="pro",
        proposers=[GPT_4_1, GEMINI_2_5_PRO, CLAUDE_HAIKU],  # Core: 3-provider mid-tier
        optional_proposers=[DEEPSEEK_V3, GROK_FAST],
        aggregator=CLAUDE_SONNET,
        description="3-5 mid-tier proposers → Sonnet (~$0.09)",
    ),
    "ultra": Tier(
        name="ultra",
        proposers=[GPT_5_4, GEMINI_3_1_PRO, CLAUDE_SONNET],  # Core: 3-provider frontier
        optional_proposers=[DEEPSEEK_R1, GROK_4_20],
        aggregator=CLAUDE_OPUS,
        description="3-5 frontier proposers → Opus (~$0.25)",
    ),
}


# ── Adaptive routing tiers (SIMPLE / STANDARD / COMPLEX) ──────────────────────
# Used by run_adaptive() — classification determines which tier to use

@dataclass
class AdaptiveTier:
    """An adaptive tier selected by query classification."""
    proposers: List[ModelConfig]
    synthesizer: Optional[ModelConfig]
    max_calls: int
    description: str

ADAPTIVE_TIERS = {
    "SIMPLE": AdaptiveTier(
        proposers=[CLAUDE_HAIKU, GEMINI_FLASH],
        synthesizer=None,  # No aggregation needed — return best
        max_calls=2,
        description="1-2 fast models, no synthesis",
    ),
    "STANDARD": AdaptiveTier(
        proposers=[CLAUDE_SONNET, GPT_4_1, GEMINI_2_5_PRO],
        synthesizer=CLAUDE_SONNET,
        max_calls=4,
        description="2-3 strong models → Sonnet synthesis",
    ),
    "COMPLEX": AdaptiveTier(
        proposers=[CLAUDE_OPUS, GPT_5_4, GEMINI_2_5_PRO, CLAUDE_SONNET],
        synthesizer=CLAUDE_OPUS,
        max_calls=5,
        description="3-4 frontier models → Opus synthesis with disagreement detection",
    ),
}

# The classifier model — cheapest available
CLASSIFIER_MODEL = GPT4O_MINI


# ══════════════════════════════════════════════════════════════════════════════
#  CASCADE FLOW — lite pass → confidence check → premium verification
# ══════════════════════════════════════════════════════════════════════════════

CASCADE_CONFIDENCE_PROMPT = """You are a JSON-only evaluator. Respond with raw JSON only.

You just received synthesized responses from multiple AI models. Evaluate whether 
the answer is confident and complete, or whether it needs premium verification.

Escalate to premium if ANY of these apply:
- Models disagreed on factual claims
- The topic involves safety, security, legal, or medical implications
- The answer contains hedging language ("might", "possibly", "it depends")
- The question requires multi-step reasoning that the lite models may have gotten wrong
- Code was generated that could have subtle bugs in async, auth, or data handling

Respond with:
{"confident": true, "reason": "All models agreed and the answer is straightforward."}
or
{"confident": false, "reason": "[specific reason premium pass is needed]"}"""


# ══════════════════════════════════════════════════════════════════════════════
#  AGGREGATOR FALLBACK CHAIN
# ══════════════════════════════════════════════════════════════════════════════

AGGREGATOR_FALLBACKS = [CLAUDE_OPUS, CLAUDE_SONNET, GPT_5_4, GEMINI_3_1_PRO]


def get_aggregator(prefer_premium: bool = False) -> Optional[ModelConfig]:
    """Return best available aggregator. If prefer_premium, try Opus first."""
    chain = AGGREGATOR_FALLBACKS if prefer_premium else [CLAUDE_SONNET, CLAUDE_OPUS, GPT_5_4, GEMINI_3_1_PRO]
    for model in chain:
        if model.available:
            return model
    # Last resort: any available model
    avail = available_models()
    return avail[0] if avail else None


# ══════════════════════════════════════════════════════════════════════════════
#  CODE REVIEW SPECIALIST ROLES — remapped to stronger models
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReviewerRole:
    """A specialized code reviewer with a role-specific system prompt."""
    name: str
    model: ModelConfig
    fallback: ModelConfig       # If primary model is unavailable
    system_prompt: str


REVIEWER_ROLES = [
    ReviewerRole(
        name="Security Reviewer",
        model=GPT_4_1,
        fallback=GPT4O_MINI,
        system_prompt=(
            "You are a senior security engineer reviewing code changes. "
            "Focus exclusively on: injection vulnerabilities (SQL, XSS, command), "
            "authentication and authorization flaws, secret/credential exposure, "
            "insecure data handling, OWASP Top 10 concerns, and unsafe deserialization. "
            "For each finding, state: severity (critical/high/medium/low), "
            "the specific file and line, the vulnerability, and the fix. "
            "If you find nothing, say so — don't invent issues."
        ),
    ),
    ReviewerRole(
        name="Architecture Reviewer",
        model=CLAUDE_SONNET,
        fallback=GEMINI_2_5_PRO,
        system_prompt=(
            "You are a senior software architect reviewing code changes. "
            "Focus exclusively on: SOLID principle violations, coupling and cohesion, "
            "dependency direction, async/concurrency patterns and race conditions, "
            "error handling completeness, and API contract consistency. "
            "For each finding, state the principle violated, location, impact, "
            "and recommended refactor."
        ),
    ),
    ReviewerRole(
        name="Performance Reviewer",
        model=GEMINI_2_5_PRO,
        fallback=GEMINI_FLASH,
        system_prompt=(
            "You are a senior performance engineer reviewing code changes. "
            "Focus exclusively on: algorithm complexity (Big-O), N+1 query patterns, "
            "unnecessary re-renders in React, memory leaks, bundle size impact, "
            "layout shifts, missing lazy loading, and inefficient data structures. "
            "Quantify impact where possible and suggest the specific optimization."
        ),
    ),
    ReviewerRole(
        name="Correctness Reviewer",
        model=GEMINI_3_1_PRO,       # Primary: Google (you have key)
        fallback=DEEPSEEK_R1,       # Bonus: DeepSeek R1 if key is set
        system_prompt=(
            "You are a reasoning-focused code reviewer. Trace through the logic "
            "step by step. Focus on: off-by-one errors, boundary conditions, "
            "null/undefined edge cases, type mismatches, incorrect boolean logic, "
            "unreachable code paths, and missing error propagation. "
            "For each finding, show the exact execution trace that exposes the bug."
        ),
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
#  PERSONA REGISTRY — usable across review, debate, and ask modes
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Persona:
    """A named perspective that can be applied to review, debate, or ask."""
    name: str
    category: str              # code, product, content, architecture, builder
    system_prompt: str
    model: ModelConfig
    fallback: ModelConfig

    def as_reviewer_role(self) -> "ReviewerRole":
        """Convert to ReviewerRole for code review mode."""
        return ReviewerRole(
            name=self.name, model=self.model,
            fallback=self.fallback, system_prompt=self.system_prompt,
        )


PERSONA_REGISTRY: List[Persona] = [
    # ── Code Review ───────────────────────────────────────────────────────
    Persona(
        name="Martin Fowler", category="code",
        model=CLAUDE_SONNET, fallback=GPT_4_1,
        system_prompt=(
            "You think like Martin Fowler. Focus on: refactoring opportunities, code smells "
            "(long method, feature envy, data clumps), design patterns, readability. "
            "Ask: 'Is this code telling a clear story?' Be specific about which refactoring applies."
        ),
    ),
    Persona(
        name="Kent Beck", category="code",
        model=GPT_4_1, fallback=CLAUDE_SONNET,
        system_prompt=(
            "You think like Kent Beck. Focus on: test coverage gaps, TDD violations, simplicity "
            "(YAGNI, KISS), XP principles. Ask: 'What is the simplest thing that could possibly work?' "
            "and 'Where are the missing tests?'"
        ),
    ),
    Persona(
        name="Rich Hickey", category="code",
        model=GEMINI_2_5_PRO, fallback=CLAUDE_SONNET,
        system_prompt=(
            "You think like Rich Hickey. Focus on: accidental complexity, mutable state, complecting "
            "unrelated concerns. Ask: 'Is this simple or just easy?' Prefer data over objects, "
            "immutability over mutation, composition over inheritance. Be blunt."
        ),
    ),
    Persona(
        name="Sandi Metz", category="code",
        model=CLAUDE_SONNET, fallback=GPT_4_1,
        system_prompt=(
            "You think like Sandi Metz. Focus on: single responsibility, dependency injection, "
            "object composition. Rules: classes <100 lines, methods <5 lines, <=4 params. "
            "If something violates these, say so directly."
        ),
    ),

    # ── Architecture / Systems ────────────────────────────────────────────
    Persona(
        name="Kelsey Hightower", category="architecture",
        model=CLAUDE_SONNET, fallback=GPT_4_1,
        system_prompt=(
            "You think like Kelsey Hightower. Question every layer of complexity. "
            "Ask: 'Do you actually need Kubernetes for this?' Focus on operational simplicity, "
            "12-factor principles, and whether the infrastructure matches the team size."
        ),
    ),
    Persona(
        name="Martin Kleppmann", category="architecture",
        model=GEMINI_2_5_PRO, fallback=CLAUDE_SONNET,
        system_prompt=(
            "You think like Martin Kleppmann. Focus on: distributed systems correctness, "
            "what happens during network partitions, data consistency guarantees, "
            "event sourcing vs state. Ask: 'What's your consistency model and have you tested it?'"
        ),
    ),
    Persona(
        name="DHH", category="architecture",
        model=GPT_4_1, fallback=CLAUDE_SONNET,
        system_prompt=(
            "You think like DHH. Aggressively question complexity. Prefer monoliths over "
            "microservices, server-rendered HTML over SPAs, simple CRUD over event sourcing. "
            "Ask: 'Could you ship this with Rails and a Postgres database?' Be provocative."
        ),
    ),

    # ── Product / Strategy ────────────────────────────────────────────────
    Persona(
        name="Shreya Doshi", category="product",
        model=CLAUDE_SONNET, fallback=GPT_4_1,
        system_prompt=(
            "You think like Shreya Doshi. Evaluate through the lens of high-leverage product "
            "thinking. Ask: 'What's the impact-to-effort ratio?' Focus on pre-mortems, "
            "decision quality over decision speed, and whether this is a one-way or two-way door."
        ),
    ),
    Persona(
        name="Marty Cagan", category="product",
        model=GPT_4_1, fallback=CLAUDE_SONNET,
        system_prompt=(
            "You think like Marty Cagan. Distinguish between feature factories and empowered "
            "product teams. Ask: 'Is this solving a real customer problem or is it a stakeholder "
            "request?' Focus on discovery over delivery, and whether the team has validated risk."
        ),
    ),
    Persona(
        name="April Dunford", category="product",
        model=CLAUDE_SONNET, fallback=GEMINI_2_5_PRO,
        system_prompt=(
            "You think like April Dunford. Focus on positioning: who is the real customer, "
            "what category does this compete in, and what is the unique value? "
            "Ask: 'If I had to explain why this wins in one sentence, what would I say?'"
        ),
    ),

    # ── Content / Writing ─────────────────────────────────────────────────
    Persona(
        name="David Ogilvy", category="content",
        model=CLAUDE_SONNET, fallback=GPT_4_1,
        system_prompt=(
            "You think like David Ogilvy. Focus on: headlines that promise a benefit, "
            "specificity over vagueness, research-backed claims, long copy that sells. "
            "Ask: 'Would this make someone stop scrolling?' Hate cleverness without clarity."
        ),
    ),
    Persona(
        name="Ann Handley", category="content",
        model=GPT_4_1, fallback=CLAUDE_SONNET,
        system_prompt=(
            "You think like Ann Handley. Focus on: clarity, voice, empathy for the reader. "
            "Ask: 'Would a real person say this out loud?' Cut jargon. Make it conversational. "
            "Every sentence should earn its place."
        ),
    ),

    # ── Solopreneur / Builder ─────────────────────────────────────────────
    Persona(
        name="Pieter Levels", category="builder",
        model=GPT_4_1, fallback=CLAUDE_SONNET,
        system_prompt=(
            "You think like Pieter Levels. Ship fast, validate faster. Ask: 'Can you build "
            "this in a weekend?' Prefer no-code/low-code, static sites, simple APIs, flat files "
            "over databases. Revenue before features. Launch before polish."
        ),
    ),
    Persona(
        name="Daniel Vassallo", category="builder",
        model=CLAUDE_SONNET, fallback=GPT_4_1,
        system_prompt=(
            "You think like Daniel Vassallo. Focus on small bets and portfolio strategy. "
            "Ask: 'What's the minimum viable test for this idea?' Prefer selling before building, "
            "audience before product, and multiple small experiments over one big bet."
        ),
    ),
]

# Legacy compatibility — code review personas as ReviewerRole list
PERSONA_ROLES = [p.as_reviewer_role() for p in PERSONA_REGISTRY if p.category == "code"]

# Category groups for easy lookup
PERSONA_CATEGORIES = {}
for _p in PERSONA_REGISTRY:
    PERSONA_CATEGORIES.setdefault(_p.category, []).append(_p)


def get_personas(names: str = None, category: str = None) -> List[Persona]:
    """Look up personas by comma-separated names or category.

    Examples:
        get_personas(names="DHH,Kent Beck")
        get_personas(category="product")
        get_personas(names="DHH", category="code")  # names take priority
    """
    if names:
        name_list = [n.strip() for n in names.split(",")]
        # Case-insensitive fuzzy match
        result = []
        for target in name_list:
            target_lower = target.lower()
            for p in PERSONA_REGISTRY:
                if target_lower in p.name.lower():
                    result.append(p)
                    break
        return result if result else PERSONA_REGISTRY[:3]  # fallback to first 3

    if category:
        cat_lower = category.lower()
        return PERSONA_CATEGORIES.get(cat_lower, PERSONA_REGISTRY[:3])

    return list(PERSONA_REGISTRY)


# ══════════════════════════════════════════════════════════════════════════════
#  COST TRACKING
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class QueryCost:
    """Track cost of a single query execution."""
    tier: str
    proposer_calls: int = 0
    aggregator_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    models_used: List[str] = field(default_factory=list)
    escalated: bool = False         # True if cascade escalated to premium

    def summary(self) -> str:
        esc = " 🔺 ESCALATED" if self.escalated else ""
        return (
            f"Tier: {self.tier}{esc} | Models: {', '.join(self.models_used)} | "
            f"Tokens: {self.total_input_tokens:,}in + {self.total_output_tokens:,}out | "
            f"Est. cost: ${self.estimated_cost_usd:.4f}"
        )
