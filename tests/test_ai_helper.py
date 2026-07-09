"""
test_ai_helper.py — AIHelper 모듈 단위 테스트
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import requests

from engine.ai_helper import AIHelper

class AIHelperTest(unittest.TestCase):

    def setUp(self):
        # 테스트 전 환경 변수 백업
        self.original_key = os.environ.get("GEMINI_API_KEY")
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

    def tearDown(self):
        # 환경 변수 복구
        if self.original_key is not None:
            os.environ["GEMINI_API_KEY"] = self.original_key
        elif "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

    def test_missing_api_key_raises_value_error(self):
        helper = AIHelper()
        with self.assertRaises(ValueError) as ctx:
            helper.summarize_diary("2026-07-08", "일기 내용")
        self.assertIn("GEMINI_API_KEY가 존재하지 않습니다", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            helper.analyze_empathy("2026-07-08", "일기 내용")
        self.assertIn("GEMINI_API_KEY가 존재하지 않습니다", str(ctx.exception))

    def test_empty_content_raises_value_error(self):
        os.environ["GEMINI_API_KEY"] = "fake_key"
        helper = AIHelper()
        with self.assertRaises(ValueError) as ctx:
            helper.summarize_diary("2026-07-08", "")
        self.assertIn("일기 내용이 비어있습니다", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            helper.analyze_empathy("2026-07-08", "")
        self.assertIn("일기 내용이 비어있습니다", str(ctx.exception))

    @patch("requests.post")
    def test_summarize_diary_successful_api_call(self, mock_post):
        os.environ["GEMINI_API_KEY"] = "fake_key"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": '{"summary": "테스트 요약"}'
                    }]
                }
            }]
        }
        mock_post.return_value = mock_response

        helper = AIHelper()
        summary = helper.summarize_diary("2026-07-08", "오늘 너무 슬펐어")

        self.assertEqual(summary, "테스트 요약")
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_analyze_empathy_successful_api_call(self, mock_post):
        os.environ["GEMINI_API_KEY"] = "fake_key"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": '{"empathy": "따뜻한 공감", "drawing_analysis": "테스트 그림 분석"}'
                    }]
                }
            }]
        }
        mock_post.return_value = mock_response

        helper = AIHelper()
        result = helper.analyze_empathy("2026-07-08", "오늘 너무 슬펐어")

        self.assertEqual(result["empathy"], "따뜻한 공감")
        self.assertEqual(result["drawing_analysis"], "테스트 그림 분석")
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_network_failure_raises_runtime_error(self, mock_post):
        os.environ["GEMINI_API_KEY"] = "fake_key"
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection Refused")

        helper = AIHelper()
        with self.assertRaises(RuntimeError) as ctx:
            helper.summarize_diary("2026-07-08", "오늘의 일기")
        self.assertIn("네트워크 오류가 발생했습니다", str(ctx.exception))

    @patch("requests.post")
    def test_malformed_json_response_raises_runtime_error(self, mock_post):
        os.environ["GEMINI_API_KEY"] = "fake_key"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "{invalid json}"
                    }]
                }
            }]
        }
        mock_post.return_value = mock_response

        helper = AIHelper()
        with self.assertRaises(RuntimeError) as ctx:
            helper.summarize_diary("2026-07-08", "오늘의 일기")
        self.assertIn("AI 응답 분석 중 오류가 발생했습니다", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
