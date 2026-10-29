import json
import math

from common.llm import parse_structured_output
from common.prompts import plan_generation_prompt, plan_generation_user_prompt
from common.schemas.plan import Plan
from common.schemas.profile import Profile


_DURATION_SETTINGS = {
    15: (60, 60, 3),
    30: (120, 120, 5),
    45: (120, 180, 8),
}


def _is_thin_profile(profile: Profile) -> bool:
    return len(profile.projects) < 2 and profile.total_experience_years < 1.0


def _weighted_budgets(weights: list[float], total_seconds: int) -> list[int]:
    safe_weights = [weight if math.isfinite(weight) and weight > 0 else 0.01 for weight in weights]
    weight_sum = sum(safe_weights)
    exact = [total_seconds * weight / weight_sum for weight in safe_weights]
    budgets = [max(1, int(value)) for value in exact]
    difference = total_seconds - sum(budgets)
    if difference > 0:
        order = sorted(range(len(exact)), key=lambda index: exact[index] - int(exact[index]), reverse=True)
        for offset in range(difference):
            budgets[order[offset % len(order)]] += 1
    elif difference < 0:
        order = sorted(range(len(exact)), key=lambda index: exact[index] - int(exact[index]))
        for offset in range(-difference):
            candidate = order[offset % len(order)]
            if budgets[candidate] > 1:
                budgets[candidate] -= 1
    return budgets


async def generate_plan(profile: Profile, level: str, duration_min: int) -> Plan:
    opening_sec, closing_sec, planned_threads = _DURATION_SETTINGS[duration_min]
    expected_threads = planned_threads - int(_is_thin_profile(profile))
    parsed = await parse_structured_output(
        Plan,
        system_prompt=plan_generation_prompt(),
        user_prompt=plan_generation_user_prompt(
            profile.model_dump_json(), level, duration_min, expected_threads
        ),
        max_completion_tokens=5000,
    )
    if len(parsed.threads) != expected_threads:
        raise ValueError(
            f"The generated plan had {len(parsed.threads)} topics; expected {expected_threads}."
        )

    allocated = duration_min * 60 - opening_sec - closing_sec
    budgets = _weighted_budgets([thread.weight for thread in parsed.threads], allocated)
    normalized_threads = [
        thread.model_copy(update={"id": f"t{index + 1}", "time_budget_sec": budget})
        for index, (thread, budget) in enumerate(zip(parsed.threads, budgets, strict=True))
    ]
    plan_data = parsed.model_dump(mode="json")
    plan_data.update(
        opening_sec=opening_sec,
        closing_sec=closing_sec,
        threads=[thread.model_dump(mode="json") for thread in normalized_threads],
    )
    return Plan.model_validate(plan_data)


def profile_snapshot(profile: Profile) -> dict:
    return json.loads(profile.model_dump_json())
