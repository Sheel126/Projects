import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "src"))

from main import app  # noqa: E402


class ImageTestApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_provider_info_endpoint(self):
        response = self.client.get("/api/v1/images/provider")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("provider", payload)
        self.assertIn("default_width", payload)
        self.assertIn("default_height", payload)

    @patch("history_channel.routes.images.image_service.generate_test_image")
    def test_generate_test_image_endpoint(self, mock_generate):
        mock_generate.return_value = {
            "message": "Test image generated successfully",
            "provider": "comfyui",
            "file_path": str(BACKEND_ROOT / "output" / "test_images" / "test_x.png"),
            "media_url": "/media/test_images/test_x.png",
            "generation_time_sec": 12.3,
            "width": 1280,
            "height": 720,
            "seed": 42,
        }

        response = self.client.post(
            "/api/v1/images/test",
            json={
                "prompt": "cinematic historical still",
                "width": 1280,
                "height": 720,
                "seed": 42,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider"], "comfyui")
        self.assertEqual(payload["media_url"], "/media/test_images/test_x.png")
        mock_generate.assert_called_once_with(
            "cinematic historical still",
            width=1280,
            height=720,
            seed=42,
        )

    def test_generate_test_image_validation(self):
        response = self.client.post("/api/v1/images/test", json={"prompt": "ab"})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
