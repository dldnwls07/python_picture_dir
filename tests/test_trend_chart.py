import unittest

from engine.trend_chart import TrendChartRenderer


class TrendChartRendererTest(unittest.TestCase):
    def setUp(self):
        self.renderer = TrendChartRenderer()

    def test_returns_png_bytes_when_data_in_range(self):
        scores = {"2026-06-01": 3.0, "2026-06-03": -2.0, "2026-06-05": 0.0}
        result = self.renderer.generate_trend_chart_bytes(scores, "2026-06-01", "2026-06-05")
        self.assertTrue(result)
        self.assertEqual(result[:8], b"\x89PNG\r\n\x1a\n")

    def test_returns_empty_bytes_when_no_data_in_range(self):
        scores = {"2026-01-01": 3.0}
        result = self.renderer.generate_trend_chart_bytes(scores, "2026-06-01", "2026-06-05")
        self.assertEqual(result, b"")

    def test_returns_empty_bytes_for_invalid_dates(self):
        result = self.renderer.generate_trend_chart_bytes({}, "not-a-date", "2026-06-05")
        self.assertEqual(result, b"")

    def test_handles_reversed_date_range(self):
        scores = {"2026-06-01": 3.0, "2026-06-02": 1.0}
        result = self.renderer.generate_trend_chart_bytes(scores, "2026-06-05", "2026-06-01")
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
