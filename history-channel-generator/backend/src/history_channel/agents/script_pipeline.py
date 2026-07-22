import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from history_channel.config import settings
from history_channel.models import UserFeedback

FEEDBACK_STAGES = ("hook_creation", "scripting", "general")

WRITER_SYSTEM = """You are an expert historical documentary scriptwriter for faceless YouTube channels.
Write in a cinematic, suspenseful tone with vivid scene-setting and a compelling narrative arc.
Open with a powerful hook that creates a knowledge gap — make viewers need to know what happens next.
Use short punchy sentences mixed with longer dramatic passages. No stage directions or camera cues.
Never include on-screen text, signs, or readable writing in scene descriptions."""

EDITOR_SYSTEM = """You are a senior documentary editor evaluating scripts against the Knowledge Gap Framework.

PASS the script (passed=true) unless there are CRITICAL failures only:
- Major historical inaccuracies or anachronisms
- Required user feedback was completely ignored
- Script is off-topic, incoherent, or far too short

Do NOT fail for minor stylistic preferences (hook tone, transitions, conclusion polish).
If you have minor suggestions, set passed=true and leave revised_script empty.

Only set passed=false when you also provide a complete revised_script that fixes the issues.

Checklist when evaluating:
1. Hook creates curiosity without spoiling the payoff
2. Chronological clarity and historical accuracy
3. Cinematic pacing with rising tension
4. User feedback items are addressed (if any were provided)

Respond ONLY with valid JSON:
{
  "passed": true,
  "issues": [],
  "revised_script": ""
}"""

REVISION_SYSTEM = """You are a documentary script editor. Revise the script to fix the listed issues.
Keep the same topic, approximate length, and cinematic narration style.
Return ONLY the full revised script text — no JSON, no commentary."""

POLISH_SYSTEM = """You are a documentary script editor producing the final narration script.
Apply all listed improvements while preserving historical accuracy and approximate length.
Return ONLY the complete final script — no JSON, no commentary."""


def _get_llm() -> ChatOpenAI:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured")
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0.7,
    )


def fetch_feedback_for_prompt(db: Session, project_id: int) -> str:
    rows = (
        db.query(UserFeedback)
        .filter(
            UserFeedback.project_id == project_id,
            UserFeedback.stage.in_(FEEDBACK_STAGES),
        )
        .order_by(UserFeedback.created_at.asc())
        .all()
    )
    if not rows:
        return ""
    bullets = "\n".join(f"- [{r.stage}] {r.feedback_text}" for r in rows)
    return f"\n\nUSER FEEDBACK TO INCORPORATE:\n{bullets}"


def _parse_editor_response(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # Unparseable editor output should not block the pipeline
    return {"passed": True, "issues": [], "revised_script": ""}


def _word_count(text: str) -> int:
    return len(text.split())


def _minimum_words(is_test_mode: bool) -> int:
    target = settings.script_word_count(is_test_mode)
    return max(80, int(target * 0.4))


def run_writer(
    llm: ChatOpenAI,
    topic: str,
    word_count: int,
    feedback_block: str,
    revision_notes: list[str] | None = None,
) -> str:
    revision = ""
    if revision_notes:
        revision = "\n\nFix these editor issues:\n" + "\n".join(f"- {n}" for n in revision_notes)

    messages = [
        SystemMessage(content=WRITER_SYSTEM + feedback_block),
        HumanMessage(
            content=(
                f"Write a historical documentary narration script about: {topic}\n"
                f"Target length: approximately {word_count} words.\n"
                f"{revision}"
            )
        ),
    ]
    response = llm.invoke(messages)
    return str(response.content).strip()


def run_revision_pass(
    llm: ChatOpenAI,
    script: str,
    topic: str,
    issues: list[str],
    feedback_block: str,
) -> str:
    issues_block = "\n".join(f"- {issue}" for issue in issues)
    messages = [
        SystemMessage(content=REVISION_SYSTEM + feedback_block),
        HumanMessage(
            content=(
                f"Topic: {topic}\n\n"
                f"Issues to fix:\n{issues_block}\n\n"
                f"Current script:\n\n{script}"
            )
        ),
    ]
    response = llm.invoke(messages)
    revised = str(response.content).strip()
    return revised if revised else script


def run_forced_polish(
    llm: ChatOpenAI,
    script: str,
    topic: str,
    issues: list[str],
    feedback_block: str,
) -> str:
    if not issues:
        return script
    issues_block = "\n".join(f"- {issue}" for issue in issues)
    messages = [
        SystemMessage(content=POLISH_SYSTEM + feedback_block),
        HumanMessage(
            content=(
                f"Topic: {topic}\n\n"
                f"Apply these final improvements:\n{issues_block}\n\n"
                f"Script to polish:\n\n{script}"
            )
        ),
    ]
    response = llm.invoke(messages)
    polished = str(response.content).strip()
    return polished if polished else script


def run_editor(
    llm: ChatOpenAI,
    script: str,
    topic: str,
    feedback_block: str,
    final_pass: bool = False,
) -> dict[str, Any]:
    extra = ""
    if final_pass:
        extra = (
            "\n\nThis is the FINAL review. Set passed=true unless there are "
            "critical historical errors. Provide revised_script only if essential."
        )
    messages = [
        SystemMessage(content=EDITOR_SYSTEM + feedback_block + extra),
        HumanMessage(
            content=(
                f"Topic: {topic}\n\n"
                f"Evaluate this script:\n\n{script}"
            )
        ),
    ]
    response = llm.invoke(messages)
    return _parse_editor_response(str(response.content))


def _pick_script(candidate: str, fallback: str) -> str:
    candidate = candidate.strip()
    return candidate if candidate else fallback.strip()


def generate_script_with_reflection(
    db: Session,
    project_id: int,
    topic: str,
    is_test_mode: bool,
) -> tuple[str, int, list[str]]:
    """
    Run writer + editor loop. Always returns a script.
    editor_notes contains unresolved suggestions (warnings), never a hard failure.
    """
    llm = _get_llm()
    word_count = settings.script_word_count(is_test_mode)
    min_words = _minimum_words(is_test_mode)
    feedback_block = fetch_feedback_for_prompt(db, project_id)

    editor_notes: list[str] = []
    best_script = ""
    iterations = 0

    for attempt in range(settings.max_editor_retries):
        iterations = attempt + 1

        if attempt == 0:
            script = run_writer(llm, topic, word_count, feedback_block)
        elif best_script and editor_notes:
            script = run_revision_pass(
                llm, best_script, topic, editor_notes, feedback_block
            )
        else:
            script = run_writer(
                llm, topic, word_count, feedback_block, editor_notes or None
            )

        evaluation = run_editor(
            llm,
            script,
            topic,
            feedback_block,
            final_pass=(attempt == settings.max_editor_retries - 1),
        )

        revised = evaluation.get("revised_script", "").strip()
        script = _pick_script(revised, script)
        best_script = script

        if evaluation.get("passed"):
            if _word_count(best_script) >= min_words:
                return best_script, iterations, []
            editor_notes = ["Script shorter than minimum length; expanding."]
            continue

        editor_notes = [str(i) for i in evaluation.get("issues", []) if str(i).strip()]
        if revised:
            best_script = revised

    # Final polish pass — always produce deliverable output
    if best_script and editor_notes:
        best_script = run_forced_polish(
            llm, best_script, topic, editor_notes, feedback_block
        )

    if not best_script or _word_count(best_script) < min_words:
        best_script = run_writer(llm, topic, word_count, feedback_block, editor_notes or None)

    if not best_script.strip():
        raise ValueError("Writer returned an empty script. Check OPENAI_API_KEY and try again.")

    return best_script, iterations, editor_notes
