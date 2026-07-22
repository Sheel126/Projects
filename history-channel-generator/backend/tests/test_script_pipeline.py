import unittest
from unittest.mock import MagicMock, patch

from history_channel.agents.script_pipeline import (
    _minimum_words,
    _parse_editor_response,
    _pick_script,
    _word_count,
    generate_script_with_reflection,
)


class ScriptPipelineTests(unittest.TestCase):
    def test_parse_editor_response_handles_invalid_json(self):
        result = _parse_editor_response("not json at all")
        self.assertTrue(result["passed"])
        self.assertEqual(result["issues"], [])

    def test_pick_script_prefers_candidate(self):
        self.assertEqual(_pick_script("revised", "original"), "revised")

    def test_pick_script_falls_back(self):
        self.assertEqual(_pick_script("", "original"), "original")

    def test_minimum_words_test_mode(self):
        self.assertGreaterEqual(_minimum_words(True), 80)

    @patch("history_channel.agents.script_pipeline.run_forced_polish")
    @patch("history_channel.agents.script_pipeline.run_editor")
    @patch("history_channel.agents.script_pipeline.run_revision_pass")
    @patch("history_channel.agents.script_pipeline.run_writer")
    @patch("history_channel.agents.script_pipeline._get_llm")
    @patch("history_channel.agents.script_pipeline.fetch_feedback_for_prompt")
    def test_always_returns_script_after_failed_reviews(
        self,
        mock_feedback,
        mock_get_llm,
        mock_writer,
        mock_revision,
        mock_editor,
        mock_polish,
    ):
        mock_feedback.return_value = ""
        mock_get_llm.return_value = MagicMock()

        long_script = " ".join(["word"] * 200)
        mock_writer.return_value = long_script
        mock_revision.return_value = long_script
        mock_polish.return_value = long_script
        mock_editor.return_value = {
            "passed": False,
            "issues": ["Hook needs more aggression"],
            "revised_script": long_script,
        }

        db = MagicMock()
        script, iterations, notes = generate_script_with_reflection(
            db, 1, "Fall of Constantinople", True
        )

        self.assertGreater(_word_count(script), 0)
        self.assertEqual(iterations, 3)
        self.assertEqual(notes, ["Hook needs more aggression"])
        mock_polish.assert_called_once()

    @patch("history_channel.agents.script_pipeline.run_editor")
    @patch("history_channel.agents.script_pipeline.run_writer")
    @patch("history_channel.agents.script_pipeline._get_llm")
    @patch("history_channel.agents.script_pipeline.fetch_feedback_for_prompt")
    def test_passes_on_first_good_review(
        self,
        mock_feedback,
        mock_get_llm,
        mock_writer,
        mock_editor,
    ):
        mock_feedback.return_value = ""
        mock_get_llm.return_value = MagicMock()

        long_script = " ".join(["word"] * 200)
        mock_writer.return_value = long_script
        mock_editor.return_value = {"passed": True, "issues": [], "revised_script": ""}

        db = MagicMock()
        script, iterations, notes = generate_script_with_reflection(
            db, 1, "Fall of Constantinople", True
        )

        self.assertEqual(script, long_script)
        self.assertEqual(iterations, 1)
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
