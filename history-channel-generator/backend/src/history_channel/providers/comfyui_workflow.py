"""ComfyUI workflow parameter injection and validation."""

from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ComfyUIWorkflowMapping:
    """Maps logical generation parameters to ComfyUI workflow node inputs.

    The default workflow under ``backend/assets/comfyui/flux_schnell_16x9.json``
    uses these node IDs (export your own workflow in ComfyUI and update this
    mapping if your node IDs differ):

    - ``prompt_node``  — CLIPTextEncode (positive prompt)
    - ``width_node``   — EmptySD3LatentImage (width)
    - ``height_node``  — EmptySD3LatentImage (height)
    - ``seed_node``    — RandomNoise (noise_seed)
    """

    prompt_node: str
    width_node: str
    height_node: str
    seed_node: str
    prompt_field: str = "text"
    width_field: str = "width"
    height_field: str = "height"
    seed_field: str = "noise_seed"

    def required_nodes(self) -> set[str]:
        return {self.prompt_node, self.width_node, self.height_node, self.seed_node}


DEFAULT_MAPPING = ComfyUIWorkflowMapping(
    prompt_node="6",
    prompt_field="text",
    width_node="27",
    width_field="width",
    height_node="27",
    height_field="height",
    seed_node="25",
    seed_field="noise_seed",
)


def load_workflow_template(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"ComfyUI workflow file not found: {path}. "
            "Set COMFYUI_WORKFLOW_PATH or place the default workflow at "
            "backend/assets/comfyui/flux_schnell_16x9.json"
        )
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"ComfyUI workflow must be a JSON object: {path}")
    return data


def validate_workflow(workflow: dict[str, Any], mapping: ComfyUIWorkflowMapping) -> None:
    missing = sorted(mapping.required_nodes() - set(workflow.keys()))
    if missing:
        raise ValueError(
            "ComfyUI workflow is missing required node(s): "
            f"{', '.join(missing)}. "
            "Export a compatible FLUX Schnell workflow from ComfyUI or update "
            "ComfyUIWorkflowMapping in providers/comfyui_workflow.py."
        )
    for node_id in mapping.required_nodes():
        node = workflow[node_id]
        if not isinstance(node, dict) or "inputs" not in node:
            raise ValueError(
                f"ComfyUI workflow node {node_id!r} must be an object with an "
                "'inputs' field."
            )


def inject_workflow_parameters(
    workflow: dict[str, Any],
    mapping: ComfyUIWorkflowMapping,
    *,
    prompt: str,
    width: int,
    height: int,
    seed: int | None,
) -> dict[str, Any]:
    validate_workflow(workflow, mapping)
    patched = copy.deepcopy(workflow)
    resolved_seed = seed if seed is not None else random.randint(0, 2**32 - 1)

    patched[mapping.prompt_node]["inputs"][mapping.prompt_field] = prompt
    patched[mapping.width_node]["inputs"][mapping.width_field] = width
    patched[mapping.height_node]["inputs"][mapping.height_field] = height
    patched[mapping.seed_node]["inputs"][mapping.seed_field] = resolved_seed
    return patched
