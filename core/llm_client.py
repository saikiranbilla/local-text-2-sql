"""
Shared Anthropic client via KeywordsAI.

Instantiated once; imported by every agent that needs an LLM call.
Swap the model by setting MODEL= in your .env file.
"""
import os
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
load_dotenv()

# ── config ────────────────────────────────────────────────────────────────────
KEYWORDSAI_API_KEY = os.getenv("KEYWORDSAI_API_KEY", "")
MODEL = os.getenv("MODEL", "claude-3-haiku-20240307").replace("anthropic/", "")

# ── client (singleton) ────────────────────────────────────────────────────────
# We use AsyncAnthropic for both sync-like and streaming calls to keep it simple.
_client = AsyncAnthropic(
    base_url="https://api.keywordsai.co/api/anthropic/",
    api_key=KEYWORDSAI_API_KEY,
)


def _prepare_anthropic_payload(messages: list[dict]):
    """
    Separates the system message from other messages for the Anthropic API.
    Applies cache_control to the system prompt for performance.
    """
    system_prompt = None
    other_messages = []
    
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        else:
            other_messages.append(msg)
            
    # Format system prompt for caching if present
    system_blocks = []
    if system_prompt:
        system_blocks = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ]
        
    return system_blocks, other_messages


async def chat(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 1000,
) -> str:
    """Send a chat request to Keywords AI using Anthropic SDK."""
    system_blocks, anthropic_messages = _prepare_anthropic_payload(messages)
    
    response = await _client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_blocks,
        messages=anthropic_messages,
    )
    return response.content[0].text


async def stream_chat(
    messages: list[dict],
    temperature: float = 0.5,
    max_tokens: int = 1500,
):
    """Send a streaming chat request to Keywords AI using Anthropic SDK."""
    system_blocks, anthropic_messages = _prepare_anthropic_payload(messages)
    
    async with _client.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_blocks,
        messages=anthropic_messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text
