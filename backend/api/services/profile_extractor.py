import logging

from pydantic import ValidationError

from common.config import settings
from common.llm import parse_structured_output
from common.prompts import profile_extraction_prompt, resume_profile_user_prompt
from common.schemas.profile import Profile
from api.services.resume_parser import ResumeProcessingError, strip_pii


logger = logging.getLogger(__name__)


def _sanitize_profile_value(value):
    if isinstance(value, str):
        return strip_pii(value)
    if isinstance(value, list):
        return [_sanitize_profile_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_profile_value(item) for key, item in value.items()}
    return value


async def extract_profile(extracted_text: str) -> Profile:
    system_prompt = profile_extraction_prompt()
    user_prompt = resume_profile_user_prompt(extracted_text)
    validation_feedback = ""

    for attempt in range(2):
        try:
            profile = await parse_structured_output(
                Profile,
                system_prompt=system_prompt,
                user_prompt=user_prompt + validation_feedback,
                model=settings.openai_model_strong,
                max_completion_tokens=2200,
            )
            sanitized = _sanitize_profile_value(profile.model_dump(mode="python"))
            return Profile.model_validate(sanitized)
        except ValidationError as exc:
            if attempt:
                logger.info("Resume profile validation failed after retry.")
                raise ResumeProcessingError(
                    "We could not extract a reliable profile from this resume. Please try another file."
                ) from exc
            validation_feedback = (
                "\n\nYour previous response did not match the required profile schema. "
                "Return a complete response that exactly matches the requested fields."
            )
            logger.info("Retrying resume profile extraction after schema validation failure.")

    raise ResumeProcessingError("We could not extract a profile from this resume. Please try again.")
