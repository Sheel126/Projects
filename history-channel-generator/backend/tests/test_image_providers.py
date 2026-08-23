import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from history_channel.providers.comfyui import ComfyUIImageProvider, ComfyUIUnavailableError
from history_channel.providers.comfyui_workflow import (
    DEFAULT_MAPPING,
    inject_workflow_parameters,
    load_workflow_template,
    validate_workflow,
)
from history_channel.providers.factory import get_image_provider
from history_channel.providers.io import atomic_write_bytes
from history_channel.providers.replicate import ReplicateImageProvider
from history_channel.providers.types import ImageGenerationRequest


class ComfyUIWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = {
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
            "27": {
                "class_type": "EmptySD3LatentImage",
                "inputs": {"width": 512, "height": 512, "batch_size": 1},
            },
            "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": 1}},
        }

    def test_inject_workflow_parameters(self):
        patched = inject_workflow_parameters(
            self.workflow,
            DEFAULT_MAPPING,
            prompt="ancient Rome at dusk",
            width=1280,
            height=720,
            seed=99,
        )
        self.assertEqual(
            patched["6"]["inputs"]["text"], "ancient Rome at dusk"
        )
        self.assertEqual(patched["27"]["inputs"]["width"], 1280)
        self.assertEqual(patched["27"]["inputs"]["height"], 720)
        self.assertEqual(patched["25"]["inputs"]["noise_seed"], 99)

    def test_validate_workflow_missing_node(self):
        broken = {"6": self.workflow["6"]}
        with self.assertRaises(ValueError) as ctx:
            validate_workflow(broken, DEFAULT_MAPPING)
        self.assertIn("27", str(ctx.exception))

    def test_load_default_workflow_file(self):
        from history_channel.config import settings

        path = settings.comfyui_workflow_path_resolved()
        workflow = load_workflow_template(path)
        validate_workflow(workflow, DEFAULT_MAPPING)


class ProviderFactoryTests(unittest.TestCase):
    @patch("history_channel.providers.factory.settings")
    def test_factory_selects_comfyui_by_default(self, mock_settings):
        mock_settings.image_provider = "comfyui"
        provider = get_image_provider()
        self.assertEqual(provider.name, "comfyui")

    @patch("history_channel.providers.factory.settings")
    def test_factory_selects_replicate(self, mock_settings):
        mock_settings.image_provider = "replicate"
        provider = get_image_provider()
        self.assertEqual(provider.name, "replicate")

    @patch("history_channel.providers.factory.settings")
    def test_factory_rejects_unknown_provider(self, mock_settings):
        mock_settings.image_provider = "unknown"
        with self.assertRaises(ValueError):
            get_image_provider()


class ComfyUIProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        workflow_path = Path(self.tmp.name) / "workflow.json"
        workflow_path.write_text(
            json.dumps(
                {
                    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
                    "27": {
                        "class_type": "EmptySD3LatentImage",
                        "inputs": {"width": 512, "height": 512, "batch_size": 1},
                    },
                    "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": 1}},
                }
            ),
            encoding="utf-8",
        )
        self.provider = ComfyUIImageProvider(
            base_url="http://127.0.0.1:8188",
            workflow_path=workflow_path,
            timeout_sec=5,
            poll_interval_sec=0.01,
            default_width=1280,
            default_height=720,
        )

    @patch.object(ComfyUIImageProvider, "_download_output_image", return_value=b"PNG")
    @patch.object(
        ComfyUIImageProvider,
        "_wait_for_outputs",
        return_value={"9": {"images": [{"filename": "x.png", "type": "output"}]}},
    )
    @patch.object(ComfyUIImageProvider, "_submit_prompt", return_value="prompt-123")
    def test_generate_returns_bytes(self, _submit, _wait, _download):
        result = self.provider.generate(
            ImageGenerationRequest(prompt="test prompt", seed=42)
        )
        self.assertEqual(result.provider, "comfyui")
        self.assertEqual(result.image_bytes, b"PNG")
        self.assertEqual(result.width, 1280)
        self.assertEqual(result.height, 720)
        self.assertEqual(result.seed, 42)

    @patch.object(
        ComfyUIImageProvider,
        "_request_with_retries",
        side_effect=ComfyUIUnavailableError("down"),
    )
    def test_unavailable_comfyui_raises_clear_error(self, _request):
        with self.assertRaises(ComfyUIUnavailableError):
            self.provider._submit_prompt({"6": {"inputs": {}}})


class ProviderIOTests(unittest.TestCase):
    def test_atomic_write_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "scene_0.png"
            atomic_write_bytes(dest, b"abc")
            self.assertTrue(dest.is_file())
            self.assertEqual(dest.read_bytes(), b"abc")


class ReplicateProviderTests(unittest.TestCase):
    @patch("history_channel.providers.replicate.settings")
    @patch("history_channel.providers.replicate.replicate.Client")
    def test_replicate_generate_returns_url(self, mock_client_cls, mock_settings):
        mock_settings.replicate_api_token = "token"
        mock_settings.flux_model = "black-forest-labs/flux-schnell"
        mock_settings.flux_negative_prompt = "text"
        mock_settings.image_generation_timeout_sec = 60

        mock_client = MagicMock()
        mock_client.run.return_value = "https://example.com/image.png"
        mock_client_cls.return_value = mock_client

        provider = ReplicateImageProvider()
        result = provider.generate(ImageGenerationRequest(prompt="a prompt"))
        self.assertEqual(result.provider, "replicate")
        self.assertEqual(result.image_url, "https://example.com/image.png")


if __name__ == "__main__":
    unittest.main()
