import asyncio
import logging
from typing import TypeVar, cast

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel

from common.config import settings


logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
_client: AsyncOpenAI | None = None


class StructuredOutputError(RuntimeError):
    pass


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for language model requests.")
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            max_retries=0,
        )
    return _client


async def parse_structured_output(
    response_model: type[T],
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    max_completion_tokens: int = 1800,
) -> T:
    client = get_openai_client()
    selected_model = model or settings.openai_model_strong
    if not selected_model:
        raise RuntimeError("OPENAI_MODEL_STRONG is required for structured model requests.")

    for attempt in range(2):
        try:
            response = await client.chat.completions.parse(
                model=selected_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=response_model,
                max_completion_tokens=max_completion_tokens,
            )
            message = response.choices[0].message
            if message.refusal:
                raise StructuredOutputError("The model refused to produce the requested output.")
            if message.parsed is None:
                raise StructuredOutputError("The model returned no parsed structured output.")
            return cast(T, message.parsed)
        except (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError) as exc:
            if attempt:
                raise
            logger.warning("Transient model request failed; retrying once (%s).", type(exc).__name__)
            await asyncio.sleep(0.5)
        except APIStatusError as exc:
            if attempt or exc.status_code < 500:
                raise
            logger.warning("Model API returned HTTP %s; retrying once.", exc.status_code)
            await asyncio.sleep(0.5)

    raise RuntimeError("Structured model request failed after retry.")
