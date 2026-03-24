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
    name="anthropic/claude-haiku-3-5-20241022",
    provider="Anthropic",
    env_key="ANTHROPIC_API_KEY",
    input_cost_per_mtok=0.80,
    output_cost_per_mtok=4.00,
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
    name="gemini/gemini-3.1-pro",
    provider="Google",
    env_key="GEMINI_API_KEY",
    input_cost_per_mtok=2.00,
    output_cost_per_mtok=12.00,
    strengths=["near-Opus quality", "1M context", "cost-efficient", "ARC-AGI reasoning"],
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
