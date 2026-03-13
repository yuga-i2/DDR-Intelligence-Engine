"""
LLM Wrapper — Centralized Interface to Groq LLM

This is the ONLY place in the entire codebase where the Groq LLM is called.
All agents import and use the functions from this module, never importing langchain_groq directly.
Provides a unified interface with built-in retry logic, JSON validation, and structured logging.
"""

import json
import logging
import os
import time
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

# Module-level cache for LLM instance
_llm_instance: Optional[ChatGroq] = None


def get_llm() -> ChatGroq:
    """
    Get or create the cached Groq LLM instance.
    
    Reads GROQ_MODEL and GROQ_API_KEY from environment variables.
    Caches the instance so it is only created once per process.
    
    Returns:
        ChatGroq instance configured with:
        - temperature=0.1 (deterministic output)
        - max_tokens=2048 (reasonable limit for structured responses)
    """
    global _llm_instance
    
    if _llm_instance is None:
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        api_key = os.getenv("GROQ_API_KEY")
        
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY environment variable not set. "
                "Please add it to your .env file."
            )
        
        logger.debug(f"Creating ChatGroq instance with model: {model}")
        
        _llm_instance = ChatGroq(
            model=model,
            temperature=0.1,
            max_tokens=2048,
            api_key=api_key
        )
    
    return _llm_instance


def call_llm(
    system_prompt: str,
    user_prompt: str,
    expect_json: bool = False,
    retry_count: int = 0
) -> str:
    """
    Call the LLM with system and user prompts. Handles JSON parsing with retry logic.
    
    Args:
        system_prompt: System message defining the model's role and constraints
        user_prompt: User message containing the task
        expect_json: Whether to expect and validate JSON output
        retry_count: Internal counter for recursion (do not set)
        
    Returns:
        The response content (string, not parsed)
        
    Raises:
        ValueError: If expect_json=True and JSON parsing fails after retry
    """
    llm = get_llm()
    
    # Build messages
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    # Log the call (never log actual content)
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    logger.info(
        f"LLM call: model={model}, "
        f"system_chars={len(system_prompt)}, "
        f"user_chars={len(user_prompt)}, "
        f"expect_json={expect_json}"
    )
    
    start_time = time.time()
    
    # Retry loop for rate limiting (429 errors)
    MAX_RETRIES = 3
    BASE_WAIT = 10  # seconds
    
    for attempt in range(MAX_RETRIES):
        try:
            # Call LLM
            response = llm.invoke(messages)
            response_text = response.content
            break  # Success - exit retry loop
        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str or "rate_limit_exceeded" in error_str
            is_last_attempt = attempt == MAX_RETRIES - 1
            
            if is_rate_limit and not is_last_attempt:
                wait_time = BASE_WAIT * (2 ** attempt)  # 10s, 20s, 40s
                logger.warning(
                    f"Rate limit hit (attempt {attempt + 1}/{MAX_RETRIES}). "
                    f"Waiting {wait_time}s before retry..."
                )
                time.sleep(wait_time)
                # Reset cached LLM instance so it gets a fresh connection
                global _llm_instance
                _llm_instance = None
                llm = get_llm()
                # Continue to next iteration of retry loop
            else:
                # Not a rate limit error, or last attempt exhausted
                logger.error(f"LLM error: {e}", exc_info=True)
                raise
    else:
        # This should never execute due to break above, but for safety:
        raise ValueError(f"LLM call failed after {MAX_RETRIES} retries due to rate limiting")
    
    try:
        
        duration = time.time() - start_time
        logger.info(f"LLM response received in {duration:.2f}s, chars={len(response_text)}")
        
        # Handle JSON validation
        if expect_json:
            # Try to extract JSON from markdown fences if present
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]  # Remove ```json
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]  # Remove ```
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]  # Remove trailing ```
            
            cleaned = cleaned.strip()
            
            try:
                # Validate JSON parsing
                json.loads(cleaned)
                return cleaned
            except json.JSONDecodeError as e:
                if retry_count == 0:
                    # First failure - retry once with stronger instruction
                    logger.warning(
                        f"LLM returned invalid JSON, retrying with stricter instruction. "
                        f"Error: {str(e)[:100]}"
                    )
                    
                    retry_prompt = user_prompt + (
                        "\n\nYou must respond with ONLY valid JSON. "
                        "No preamble, no explanation, no markdown fences."
                    )
                    
                    return call_llm(
                        system_prompt,
                        retry_prompt,
                        expect_json=True,
                        retry_count=1
                    )
                else:
                    # Second failure - give up
                    logger.error(f"LLM JSON parsing failed after retry. Raw response: {response_text[:200]}")
                    raise ValueError(
                        f"LLM returned invalid JSON after retry. "
                        f"Error: {str(e)}. Raw response: {response_text[:200]}"
                    )
        
        return response_text
    except Exception as e:
        logger.error(f"LLM error during JSON processing: {e}", exc_info=True)
        raise


def call_llm_with_schema(
    system_prompt: str,
    user_prompt: str,
    schema_example: dict
) -> str:
    """
    Call LLM with schema specification for structured output.
    
    Wraps call_llm with automatic schema injection and JSON validation.
    
    Args:
        system_prompt: System message
        user_prompt: User message (will be appended with schema instruction)
        schema_example: Dictionary showing the exact JSON structure expected
        
    Returns:
        The response content (valid JSON string, not parsed)
    """
    # Append schema instruction
    schema_json = json.dumps(schema_example, indent=2)
    schema_instruction = (
        f"\n\nRespond ONLY with a JSON object matching this schema exactly:\n{schema_json}\n"
        "No other text."
    )
    
    enriched_prompt = user_prompt + schema_instruction
    
    logger.debug(f"Calling LLM with schema: {len(schema_json)} chars")
    
    return call_llm(
        system_prompt,
        enriched_prompt,
        expect_json=True
    )
