"""Shared infrastructure: model calls, cost tracking, agreement detection, ranking."""

import asyncio
import json
import time
from typing import List, Optional, Dict, Any

from litellm import acompletion

from .config import (
    MODEL_TIMEOUT_SECONDS, AGGREGATOR_TIMEOUT_SECONDS, PROVIDER_CONCURRENCY,
)
from .budget import check_budget, record_spend
from .models import (
    ModelConfig, QueryCost, CLAUDE_HAIKU, CLASSIFIER_MODEL,
)
from .prompts import format_proposals, PAIRWISE_RANK_PROMPT


# ── Per-provider rate limiting ─────────────────────────────────────────────────

_provider_semaphores: Dict[str, asyncio.Semaphore] = {}


def _get_semaphore(provider: str) -> asyncio.Semaphore:
    """Get or create a per-provider concurrency semaphore."""
    if provider not in _provider_semaphores:
        limit = PROVIDER_CONCURRENCY.get(provider, 5)
        _provider_semaphores[provider] = asyncio.Semaphore(limit)
    return _provider_semaphores[provider]


def _check_budget_or_raise():
    """Check daily budget and raise if exceeded."""
    allowed, spend, cap = check_budget()
    if not allowed:
        raise RuntimeError(
            f"Daily budget exceeded: ${spend:.4f} / ${cap:.2f}. "
            f"Increase MAX_DAILY_SPEND_USD in config or wait until tomorrow."
        )


# ── Real cost calculation ──────────────────────────────────────────────────────

def calculate_real_cost(model: ModelConfig, input_tokens: int, output_tokens: int) -> float:
    """Calculate actual cost from real token counts."""
    return (
        model.input_cost_per_mtok * input_tokens / 1_000_000
        + model.output_cost_per_mtok * output_tokens / 1_000_000
    )


# ── Low-level model call with timeout ─────────────────────────────────────────

async def call_model(
    model: ModelConfig,
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Call a single model via LiteLLM with timeout, retry, and graceful failure.

    Returns dict with 'content', 'input_tokens', 'output_tokens', 'model',
    'provider', 'cost_usd', 'latency_s' or None on total failure.
    """
    from .health import should_skip, record_success, record_failure, get_timeout_for_attempt

    # Circuit breaker: skip models that are consistently failing
    skip_reason = should_skip(model.name)
    if skip_reason:
        return None

    temp = temperature if temperature is not None else model.temperature
    max_tok = max_tokens or model.max_tokens
    base_timeout = timeout or MODEL_TIMEOUT_SECONDS

    start = time.monotonic()
    last_error = None

    for attempt in range(3):
        call_timeout = get_timeout_for_attempt(base_timeout, attempt)
        try:
            sem = _get_semaphore(model.provider)
            async with sem:
                resp = await asyncio.wait_for(
                    acompletion(
                        model=model.name,
                        messages=messages,
                        temperature=temp,
                        max_tokens=max_tok,
                    ),
                    timeout=call_timeout,
                )
            elapsed = time.monotonic() - start
            usage = resp.get("usage", {})
            input_tok = usage.get("prompt_tokens", 0)
            output_tok = usage.get("completion_tokens", 0)

            record_success(model.name)
            return {
                "content": resp.choices[0].message.content,
                "input_tokens": input_tok,
                "output_tokens": output_tok,
                "cost_usd": calculate_real_cost(model, input_tok, output_tok),
                "model": model.name,
                "provider": model.provider,
                "latency_s": round(elapsed, 2),
            }
        except asyncio.TimeoutError:
            last_error = f"timeout ({call_timeout}s)"
            record_failure(model.name)
            break  # Don't retry timeouts
        except Exception as e:
            last_error = str(e)[:100]
            record_failure(model.name)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

    return None


def _update_cost(cost: QueryCost, result: Dict, model: ModelConfig = None, is_aggregator: bool = False):
    """Update cost tracker with a model call result."""
    if is_aggregator:
        cost.aggregator_calls += 1
    else:
        cost.proposer_calls += 1
    cost.total_input_tokens += result["input_tokens"]
    cost.total_output_tokens += result["output_tokens"]
    cost.estimated_cost_usd += result.get("cost_usd", 0.0)
    cost.models_used.append(result["model"])


# ── Agreement detection ────────────────────────────────────────────────────────

def compute_agreement(proposals: list, model_names: list = None) -> dict:
    """Compute agreement between proposals using word overlap similarity.

    Returns dict with 'score' (0.0-1.0), 'consensus' (bool), and 'details'.
    Uses Jaccard similarity on significant words (>3 chars) across all pairs.
    """
    if len(proposals) < 2:
        return {"score": 1.0, "consensus": True, "details": "Only one proposal"}

    def significant_words(text: str) -> set:
        """Extract significant words (>3 chars, lowercase) from text."""
        return {
            w.lower().strip(".,!?;:()[]{}\"'")
            for w in text.split()
            if len(w) > 3
        }

    word_sets = [significant_words(p) for p in proposals]

    # Pairwise Jaccard similarity
    similarities = []
    for i in range(len(word_sets)):
        for j in range(i + 1, len(word_sets)):
            intersection = word_sets[i] & word_sets[j]
            union = word_sets[i] | word_sets[j]
            if union:
                similarities.append(len(intersection) / len(union))
            else:
                similarities.append(1.0)

    avg_sim = sum(similarities) / len(similarities) if similarities else 1.0
    consensus = avg_sim > 0.35  # Threshold: 35% word overlap = general agreement

    return {
        "score": round(avg_sim, 3),
        "consensus": consensus,
        "pairwise": similarities,
        "details": f"avg_similarity={avg_sim:.3f}, pairs={len(similarities)}",
    }


# ── Pairwise ranking ──────────────────────────────────────────────────────────

async def pairwise_rank(
    proposals: List[str], model_names: List[str]
) -> Dict[str, Any]:
    """Use a cheap model to rank proposals via pairwise comparison (from LLM-Blender).

    Returns dict with 'rankings' (sorted best->worst) and 'best_index'.
    """
    model = CLASSIFIER_MODEL if CLASSIFIER_MODEL.available else CLAUDE_HAIKU
    if not model or not model.available or len(proposals) < 2:
        return {"rankings": list(range(len(proposals))), "best_index": 0}

    # Compare each pair (cap at 6 to control cost)
    pairs = []
    for i in range(len(proposals)):
        for j in range(i + 1, len(proposals)):
            pairs.append((i, j))

    wins = [0] * len(proposals)

    tasks = []
    pair_indices = []
    for i, j in pairs[:6]:
        tasks.append(call_model(
            model,
            [
                {"role": "system", "content": PAIRWISE_RANK_PROMPT},
                {"role": "user", "content": (
                    f"Response A ({model_names[i] if i < len(model_names) else 'Model ' + str(i)}):\n"
                    f"{proposals[i][:2000]}\n\n"
                    f"Response B ({model_names[j] if j < len(model_names) else 'Model ' + str(j)}):\n"
                    f"{proposals[j][:2000]}"
                )},
            ],
            temperature=0.0,
            max_tokens=100,
            timeout=10,
        ))
        pair_indices.append((i, j))

    results = await asyncio.gather(*tasks)

    for (i, j), result in zip(pair_indices, results):
        if not result:
            continue
        try:
            text = result["content"].strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(text)
            winner = parsed.get("winner", "TIE").upper()
            if winner == "A":
                wins[i] += 1
            elif winner == "B":
                wins[j] += 1
            else:
                wins[i] += 0.5
                wins[j] += 0.5
        except (json.JSONDecodeError, KeyError, AttributeError):
            pass

    rankings = sorted(range(len(proposals)), key=lambda x: wins[x], reverse=True)
    return {"rankings": rankings, "best_index": rankings[0], "wins": wins}
