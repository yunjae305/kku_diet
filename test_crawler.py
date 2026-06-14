import importlib
import sys
import types
import unittest
from datetime import datetime


fake_holidays = types.ModuleType("holidays")
fake_holidays.country_holidays = lambda country: set()
sys.modules["holidays"] = fake_holidays

import crawler


class FixedDateTime(datetime):
    value = datetime(2026, 6, 14, 12, 0)

    @classmethod
    def now(cls, tz=None):
        if tz:
            return cls.value.replace(tzinfo=tz)
        return cls.value


def html_for(dates, sunday_text=""):
    headers = "".join(f"<th>{label}</th>" for label in dates)
    empty_cells = "".join("<td></td>" for _ in dates)
    lunch_cells = []
    dinner_cells = []
    for label in dates:
        if "sun" in label:
            lunch_cells.append(f"<td>{sunday_text}</td>")
            dinner_cells.append(f"<td>{sunday_text} 저녁</td>")
        else:
            lunch_cells.append("<td>평일 점심</td>")
            dinner_cells.append("<td>평일 저녁</td>")
    return f"""
    <table class="week_menu_tbl">
      <thead>
        <tr><th></th>{headers}</tr>
      </thead>
      <tbody>
        <tr><th>아침</th>{empty_cells}</tr>
        <tr><th>점심</th>{"".join(lunch_cells)}</tr>
        <tr><th>저녁</th>{"".join(dinner_cells)}</tr>
      </tbody>
    </table>
    """


class CrawlerDateTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(crawler)
        crawler._cache.clear()
        FixedDateTime.value = datetime(2026, 6, 14, 12, 0)
        crawler.datetime = FixedDateTime

    def tearDown(self):
        crawler.datetime = datetime

    def test_today_uses_matching_date_header_when_default_page_is_next_week(self):
        default_html = html_for([
            "mon (2026-6-15)",
            "tue (2026-6-16)",
            "wed (2026-6-17)",
            "thu (2026-6-18)",
            "fri (2026-6-19)",
            "sat (2026-6-20)",
            "sun (2026-6-21)",
        ], "다음주 일요일")
        previous_html = html_for([
            "mon (2026-6-8)",
            "tue (2026-6-9)",
            "wed (2026-6-10)",
            "thu (2026-6-11)",
            "fri (2026-6-12)",
            "sat (2026-6-13)",
            "sun (2026-6-14)",
        ], "이번주 일요일")
        calls = []

        def fake_fetch(config, extra_params=None):
            calls.append(extra_params)
            if extra_params and extra_params.get("time_shift") == "prev":
                return previous_html
            return default_html

        crawler._fetch_diet_html = fake_fetch

        result = crawler.get_diet_by_day(0, "mosirae")

        self.assertIn("[모시래학사 06/14 식단]", result)
        self.assertIn("이번주 일요일", result)
        self.assertNotIn("다음주 일요일", result)
        self.assertEqual(calls, [None, {"target_day": "2026-06-15", "time_shift": "prev"}])

    def test_same_visible_week_requests_share_cached_table(self):
        FixedDateTime.value = datetime(2026, 6, 15, 12, 0)
        visible_html = html_for([
            "mon (2026-6-15)",
            "tue (2026-6-16)",
            "wed (2026-6-17)",
            "thu (2026-6-18)",
            "fri (2026-6-19)",
            "sat (2026-6-20)",
            "sun (2026-6-21)",
        ], "일요일")
        calls = []

        def fake_fetch(config, extra_params=None):
            calls.append(extra_params)
            return visible_html

        crawler._fetch_diet_html = fake_fetch

        crawler.get_diet_by_day(0, "mosirae")
        crawler.get_diet_by_day(1, "mosirae")

        self.assertEqual(calls, [None])

    def test_tomorrow_after_visible_sunday_uses_next_week_from_first_day(self):
        FixedDateTime.value = datetime(2026, 6, 21, 12, 0)
        default_html = html_for([
            "mon (2026-6-15)",
            "tue (2026-6-16)",
            "wed (2026-6-17)",
            "thu (2026-6-18)",
            "fri (2026-6-19)",
            "sat (2026-6-20)",
            "sun (2026-6-21)",
        ], "현재 일요일")
        next_html = html_for([
            "mon (2026-6-22)",
            "tue (2026-6-23)",
            "wed (2026-6-24)",
            "thu (2026-6-25)",
            "fri (2026-6-26)",
            "sat (2026-6-27)",
            "sun (2026-6-28)",
        ], "다음 일요일")
        calls = []

        def fake_fetch(config, extra_params=None):
            calls.append(extra_params)
            if extra_params and extra_params.get("time_shift") == "next":
                return next_html
            return default_html

        crawler._fetch_diet_html = fake_fetch

        result = crawler.get_diet_by_day(1, "mosirae")

        self.assertIn("[모시래학사 06/22 식단]", result)
        self.assertEqual(calls, [None, {"target_day": "2026-06-15", "time_shift": "next"}])


if __name__ == "__main__":
    unittest.main()
