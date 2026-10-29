import logging
import re

from common.llm import parse_structured_output
from common.prompts import answer_evaluation_prompt
from common.schemas.evaluation import Evaluation
from common.schemas.plan import PlanThread
from common.schemas.live import LiveState


logger = logging.getLogger(__name__)
_REPEAT = re.compile(r"\b(repeat the question|say that again|didn't understand|did not understand|rephrase that)\b", re.I)
_BACKCHANNELS = {"hmm", "hm", "yeah", "yes", "okay", "ok", "right", "uh huh", "mm hmm"}


def is_repeat_request(text: str) -> bool:
    return bool(_REPEAT.search(text.strip()))


def is_unscorable(text: str, low_confidence: bool) -> bool:
    words = re.findall(r"[\w']+", text.lower())
    return low_confidence or len(words) < 4 or " ".join(words) in _BACKCHANNELS or is_repeat_request(text)


async def evaluate_answer(
    *,
    turn_idx: int,
    thread: PlanThread,
    question: str,
    answer: str,
    exchange: list[tuple[str, str]],
    low_confidence: bool,
) -> Evaluation:
    if is_unscorable(answer, low_confidence):
        return Evaluation(
            turn_idx=turn_idx,
            thread_id=thread.id,
            scored=False,
            answer_quality="unclear",
            missed_points=[],
            goals_covered=[],
        )
    user_prompt = (
        f"Thread topic: {thread.topic}\nGoals: {thread.goals}\n"
        f"Rubric strong: {thread.rubric.strong}\nRubric average: {thread.rubric.average}\n"
        f"Rubric weak: {thread.rubric.weak}\nQuestion asked: {question}\nCandidate answer: {answer}\n"
        f"Last exchange: {exchange[-2:]}"
    )
    try:
        result = await parse_structured_output(
            Evaluation,
            system_prompt=answer_evaluation_prompt(),
            user_prompt=user_prompt,
            max_completion_tokens=700,
        )
    except Exception as exc:
        logger.info("Answer evaluation skipped after model failure (%s).", type(exc).__name__)
        return Evaluation(turn_idx=turn_idx, thread_id=thread.id, scored=False, answer_quality="unclear")
    result.goals_covered = [goal for goal in result.goals_covered if goal in thread.goals]
    result.turn_idx = turn_idx
    result.thread_id = thread.id
    return result


def apply_evaluation(state: LiveState, evaluation: Evaluation) -> None:
    if not evaluation.scored:
        return
    if evaluation.answer_quality == "strong":
        state.strong_streak += 1
        state.weak_streak = 0
    elif evaluation.answer_quality == "weak":
        state.weak_streak += 1
        state.strong_streak = 0
    else:
        state.strong_streak = 0
        state.weak_streak = 0

    levels = ["easy", "medium", "hard"]
    level = levels.index(state.difficulty)
    if state.strong_streak >= 2:
        level = min(2, level + 1)
        state.strong_streak = 0
    elif state.weak_streak >= 2:
        level = max(0, level - 1)
        state.weak_streak = 0
    state.difficulty = levels[level]
    covered = state.goals_covered.setdefault(evaluation.thread_id, [])
    for goal in evaluation.goals_covered:
        if goal not in covered:
            covered.append(goal)
