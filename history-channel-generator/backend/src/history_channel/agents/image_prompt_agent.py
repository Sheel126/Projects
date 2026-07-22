import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from history_channel.config import settings

IMAGE_PROMPT_SYSTEM = """You are a visual director for historical documentary videos.
Split the narration into distinct visual scenes. For each scene provide:
- narrative_excerpt: the portion of script this scene covers (1-3 sentences)
- image_prompt: a detailed Flux image prompt for a cinematic still frame

Rules for image_prompt:
- Describe only visual elements: lighting, era-appropriate clothing, architecture, atmosphere
- NEVER request text, signs, banners, books with readable pages, or written inscriptions
- Use photorealistic, cinematic, dramatic lighting style
- No people's faces in extreme close-up unless historically necessary

Respond ONLY with valid JSON array:
[
  {"narrative_excerpt": "...", "image_prompt": "..."},
  ...
]"""


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0.5,
    )


def _parse_scenes_response(content: str) -> list[dict[str, str]]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Image prompt agent did not return a JSON array")
    return data


def generate_scene_prompts(
    script: str,
    scene_count: int,
) -> list[dict[str, str]]:
    llm = _get_llm()
    messages = [
        SystemMessage(content=IMAGE_PROMPT_SYSTEM),
        HumanMessage(
            content=(
                f"Split this documentary script into exactly {scene_count} visual scenes.\n\n"
                f"SCRIPT:\n{script}"
            )
        ),
    ]
    response = llm.invoke(messages)
    scenes = _parse_scenes_response(str(response.content))

    result = []
    for item in scenes[:scene_count]:
        result.append(
            {
                "narrative_excerpt": str(item.get("narrative_excerpt", "")).strip(),
                "image_prompt": str(item.get("image_prompt", "")).strip(),
            }
        )
    return result


def generate_thumbnail_prompt(topic: str, script_excerpt: str) -> str:
    llm = _get_llm()
    messages = [
        SystemMessage(content=IMAGE_PROMPT_SYSTEM),
        HumanMessage(
            content=(
                f"Create ONE dramatic thumbnail image prompt for a YouTube video about: {topic}\n"
                f"Use this script excerpt for mood:\n{script_excerpt[:500]}\n"
                "The image must be eye-catching, high contrast, no text or typography."
            )
        ),
    ]
    response = llm.invoke(messages)
    text = str(response.content).strip()
    try:
        data = _parse_scenes_response(text) if text.startswith("[") else json.loads(text)
        if isinstance(data, list) and data:
            return str(data[0].get("image_prompt", text))
        if isinstance(data, dict):
            return str(data.get("image_prompt", text))
    except (json.JSONDecodeError, ValueError):
        pass
    return text
