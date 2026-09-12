"""A bounded feedback loop; replace the critic with a task-specific evaluator."""

from collections.abc import Callable

Complete = Callable[[str, str], str]


def run_loop(task: str, complete: Complete, rounds: int = 1) -> dict:
    if not task.strip():
        raise ValueError("Task must not be empty.")
    if not 1 <= rounds <= 3:
        raise ValueError("Revision rounds must be between 1 and 3.")

    draft = complete("Produce a useful answer to the user's task.", task)
    initial = draft
    revisions = []
    for _ in range(rounds):
        feedback = complete(
            "Critique the draft against the task. Give specific, actionable corrections. "
            "Identify unsupported claims and unmet requirements.",
            f"Task:\n{task}\n\nDraft:\n{draft}",
        )
        revised = complete(
            "Revise the draft using the critique. Return only the revised answer. "
            "Do not invent evidence or claim external actions were completed.",
            f"Task:\n{task}\n\nDraft:\n{draft}\n\nCritique:\n{feedback}",
        )
        revisions.append({"draft": draft, "feedback": feedback, "revised": revised})
        draft = revised

    return {"task": task, "initial": initial, "revisions": revisions, "final": draft}
