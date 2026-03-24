"""Model name verification — ping each available model to confirm LiteLLM strings work."""

import asyncio
import time
from typing import Dict

from litellm import acompletion

from .models import ALL_MODELS, ModelConfig


async def verify_single_model(model: ModelConfig) -> Dict:
    """Ping a single model with a trivial prompt. Returns status dict."""
    if not model.available:
        return {
            "model": model.name,
            "provider": model.provider,
            "status": "skipped",
            "reason": f"No {model.env_key} set",
        }

    start = time.monotonic()
    try:
        resp = await asyncio.wait_for(
            acompletion(
                model=model.name,
                messages=[{"role": "user", "content": "Say hello in one word."}],
                max_tokens=10,
                temperature=0.0,
            ),
            timeout=30,
        )
        elapsed = time.monotonic() - start
        content = resp.choices[0].message.content.strip()
        return {
            "model": model.name,
            "provider": model.provider,
            "status": "ok",
            "latency_s": round(elapsed, 2),
            "response": content[:50],
        }
    except asyncio.TimeoutError:
        return {
            "model": model.name,
            "provider": model.provider,
            "status": "timeout",
            "reason": "No response within 30s",
        }
    except Exception as e:
        error_msg = str(e)
        # Extract useful info from common errors
        suggestion = ""
        if "NotFoundError" in error_msg or "404" in error_msg:
            suggestion = "Model name may be wrong for LiteLLM. Check docs."
        elif "AuthenticationError" in error_msg or "401" in error_msg:
            suggestion = "API key is set but invalid or expired."
        elif "RateLimitError" in error_msg or "429" in error_msg:
            suggestion = "Rate limited. Model exists but try again later."

        return {
            "model": model.name,
            "provider": model.provider,
            "status": "error",
            "reason": error_msg[:200],
            "suggestion": suggestion,
        }


async def verify_all_models() -> list:
    """Verify all models that have API keys set. Returns list of status dicts."""
    # Only verify models that have keys
    models_to_check = [m for m in ALL_MODELS if m.available]
    if not models_to_check:
        return [{
            "model": "none",
            "status": "error",
            "reason": "No API keys set. Export ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY.",
        }]

    # Run all verifications in parallel
    tasks = [verify_single_model(m) for m in models_to_check]
    results = await asyncio.gather(*tasks)

    # Also include skipped models for completeness
    skipped = [
        {
            "model": m.name,
            "provider": m.provider,
            "status": "skipped",
            "reason": f"No {m.env_key}",
        }
        for m in ALL_MODELS if not m.available
    ]

    return list(results) + skipped
