"""LLM client wrapper — handles Claude API calls with rate limiting and fallback."""

import os
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Search up from this file to find .env
    for parent in [Path.cwd()] + list(Path(__file__).resolve().parents):
        env_path = parent / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
            break
except ImportError:
    pass


def get_client():
    """Create and return an Anthropic client. Raises if no API key."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Either:\n"
            "  1. Set env var: $env:ANTHROPIC_API_KEY = 'sk-ant-...'\n"
            "  2. Create a .env file with: ANTHROPIC_API_KEY=sk-ant-...\n"
            "  3. Install python-dotenv: pip install python-dotenv"
        )
    return anthropic.Anthropic(api_key=api_key)


def call_claude(prompt: str, system: str = "", max_tokens: int = 4096,
                model: str = "claude-sonnet-4-20250514") -> str:
    """Send a prompt to Claude and return the response text.

    Uses Sonnet by default for cost efficiency. Switch to Opus for deeper analysis.
    Includes basic retry logic for rate limits.
    """
    client = get_client()

    messages = [{"role": "user", "content": prompt}]

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system if system else "You are an expert code reviewer.",
                messages=messages,
            )
            return response.content[0].text

        except Exception as e:
            error_str = str(e)
            if "rate_limit" in error_str.lower() or "429" in error_str:
                wait = 2 ** attempt * 5
                logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt + 1}/3)")
                time.sleep(wait)
                continue
            raise

    raise RuntimeError("Failed after 3 retries due to rate limiting")


def estimate_cost(file_contents: dict[str, str], mode: str = "smart") -> dict:
    """Estimate API cost before running.

    Returns dict with token_estimate, cost_estimate, and file_count.
    """
    total_chars = sum(len(c) for c in file_contents.values())
    # Rough estimate: 1 token ~= 4 chars
    input_tokens = total_chars // 4

    if mode == "smart":
        # Smart mode: sends findings + context snippets, not full files
        input_tokens = input_tokens // 4  # ~25% of full content
        output_tokens = 2000  # validation response per batch
    elif mode == "auto-fix":
        # Auto-fix: sends full files that need fixing
        output_tokens = input_tokens // 2  # generates code patches

    # Sonnet pricing: $3/M input, $15/M output
    cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": round(cost, 4),
        "file_count": len(file_contents),
    }
