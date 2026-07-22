import unittest
from unittest.mock import MagicMock, patch

from history_channel.readiness import (
    audio_stale,
    can_generate_video,
    hash_script,
    has_audio,
)
from history_channel.services.audio_service import split_paragraphs


class ReadinessTests(unittest.TestCase):
    def test_hash_stable(self):
        self.assertEqual(hash_script("Hello"), hash_script("Hello"))
        self.assertNotEqual(hash_script("Hello"), hash_script("Hello!"))

    @patch("history_channel.readiness.file_exists", return_value=True)
    def test_audio_stale_when_hashes_differ(self, _mock_exists):
        p = MagicMock()
        p.script_text = "A long enough script for testing purposes here and more words."
        p.audio_path = "/tmp/x.mp3"
        p.whisper_timestamps = {"segments": []}
        p.script_hash = "aaa"
        p.audio_script_hash = "bbb"
        p.scenes = []
        self.assertTrue(has_audio(p))
        self.assertTrue(audio_stale(p))
        self.assertFalse(can_generate_video(p))

    def test_split_paragraphs_blank_lines(self):
        text = "First paragraph.\n\nSecond paragraph here."
        parts = split_paragraphs(text)
        self.assertEqual(len(parts), 2)


if __name__ == "__main__":
    unittest.main()
