"""Parser tests on synthetic pages covering the layouts eiga.com could use.

    python -m unittest discover tests
"""

import datetime as dt
import unittest

from scraper.eiga import extract_times, parse_movie_page, parse_theater_page
from scraper.translate import price_label_en

TODAY = dt.date(2026, 10, 17)

PRICES = """
<section><h2>料金</h2>
<table><tr><th>一般</th><td>2,000円</td></tr>
<tr><th>大学生・シニア</th><td>1,400円</td></tr>
<tr><th>高校生</th><td>900円</td></tr></table>
<p>サービスデー（毎月1日）1,100円 / 毎週火曜日 1300円</p></section>
"""

# Layout A: header row of dates, rows of times; second table labelled 字幕.
LAYOUT_A = f"""<html><body><main>
<section><h2><a href="/movie/104848/">愛し合ってるかい？</a></h2><p>124分</p>
<table><tr><th data-date="20261017">10/17（土）</th><th data-date="20261018">10/18（日）</th></tr>
<tr><td data-date="20261017"><a href="http://www.eurospace.co.jp/schedule/">9:50</a>
<a href="http://www.eurospace.co.jp/schedule/">12:15</a> 15:00～17:14</td>
<td data-date="20261018">10:25 12:55 15:25～17:39</td></tr></table></section>
<section><h2><a href="https://eiga.com/movie/105726/">ナギダイアリー</a></h2><p>110分</p>
<table><tr><th>10/17（土）</th><th>10/18（日）</th></tr>
<tr><td>12:45 17:30～19:30</td><td>10:10</td></tr></table>
<p>字幕</p>
<table><tr><th>10/17（土）</th><th>10/18（日）</th></tr>
<tr><td>10:30～12:30</td><td>-</td></tr></table></section>
</main>{PRICES}</body></html>"""

# Layout B: rows start with the date.
LAYOUT_B = """<html><body>
<div><h3><a href="/movie/45735/">審判（1962）</a></h3>
<table><tr><td>10/17（土）</td><td>11:00 13:00</td></tr>
<tr><td>10/18（日）</td><td>19:05～20:46</td></tr></table></div>
</body></html>"""

# Layout C: plain lists, flat structure (no wrapper per film).
LAYOUT_C = """<html><body><div id="s">
<h2><a href="/movie/1/">映画ワン</a></h2>
<ul><li>10/17（土）</li><li>9:00</li><li>11:30</li><li>10/18（日）</li><li>14:00～15:50</li></ul>
<h2><a href="/movie/2/">映画ツー</a></h2>
<p>吹替</p><ul><li>10/17（土） 18:00 20:10～22:00</li></ul>
</div></body></html>"""

MOVIE = """<html><head><meta property="og:image" content="https://img/x.jpg"></head><body>
<h1>プーチンの愛国教室</h1><p>原題または英題：Mr. Nobody Against Putin</p>
<p>2025年製作／90分／G／デンマーク・チェコ合作</p>
<dl><dt>監督</dt><dd>デビッド・ボレンスタイン</dd></dl></body></html>"""


def by_movie(page, mid):
    return [(s.date, s.start, s.end, s.fmt) for s in page.screenings if s.movie_id == mid]


class TestParser(unittest.TestCase):
    def test_times(self):
        self.assertEqual(extract_times("9:50, 12:15, 15:00～17:14"),
                         [("09:50", None), ("12:15", None), ("15:00", "17:14")])
        self.assertEqual(extract_times("24:30"), [("24:30", None)])

    def test_layout_a(self):
        p = parse_theater_page(LAYOUT_A, TODAY)
        self.assertEqual(set(p.movies), {"104848", "105726"})
        self.assertEqual(by_movie(p, "104848"), [
            ("2026-10-17", "09:50", None, None), ("2026-10-17", "12:15", None, None),
            ("2026-10-17", "15:00", "17:14", None), ("2026-10-18", "10:25", None, None),
            ("2026-10-18", "12:55", None, None), ("2026-10-18", "15:25", "17:39", None)])
        nagi = by_movie(p, "105726")
        self.assertIn(("2026-10-17", "10:30", "12:30", "字幕"), nagi)
        self.assertIn(("2026-10-17", "12:45", None, None), nagi)
        self.assertEqual(len(nagi), 4)
        self.assertEqual(p.movies["105726"].runtime, 110)
        self.assertEqual(p.official_url, "http://www.eurospace.co.jp/schedule/")
        prices = {x["label_ja"]: x["yen"] for x in p.prices}
        self.assertEqual(prices.get("一般"), 2000)
        self.assertEqual(prices.get("大学生・シニア"), 1400)
        self.assertEqual(prices.get("毎週火曜日"), 1300)

    def test_layout_b(self):
        p = parse_theater_page(LAYOUT_B, TODAY)
        self.assertEqual(by_movie(p, "45735"), [
            ("2026-10-17", "11:00", None, None), ("2026-10-17", "13:00", None, None),
            ("2026-10-18", "19:05", "20:46", None)])

    def test_layout_c(self):
        p = parse_theater_page(LAYOUT_C, TODAY)
        self.assertEqual(by_movie(p, "1"), [
            ("2026-10-17", "09:00", None, None), ("2026-10-17", "11:30", None, None),
            ("2026-10-18", "14:00", "15:50", None)])
        self.assertEqual(by_movie(p, "2"), [
            ("2026-10-17", "18:00", None, "吹替"), ("2026-10-17", "20:10", "22:00", "吹替")])

    def test_year_rollover(self):
        p = parse_theater_page(LAYOUT_B.replace("10/17", "12/31").replace("10/18", "1/1"),
                               dt.date(2026, 12, 30))
        self.assertEqual({s.date for s in p.screenings}, {"2026-12-31", "2027-01-01"})

    def test_movie_page(self):
        info = parse_movie_page(MOVIE)
        self.assertEqual(info["title_en"], "Mr. Nobody Against Putin")
        self.assertEqual(info["year"], 2025)
        self.assertEqual(info["runtime"], 90)
        self.assertEqual(info["country"], "デンマーク・チェコ合作")
        self.assertEqual(info["director"], "デビッド・ボレンスタイン")
        self.assertEqual(info["poster"], "https://img/x.jpg")

    def test_movie_page_without_rating(self):
        info = parse_movie_page("<p>1997年製作／95分／台湾</p><p>監督 チェン</p>")
        self.assertEqual((info["year"], info["runtime"], info["country"]), (1997, 95, "台湾"))
        self.assertNotIn("rating", info)
        info = parse_movie_page("<p>2024年製作／101分／PG12／フランス・ベルギー合作</p>")
        self.assertEqual((info["rating"], info["country"]), ("PG12", "フランス・ベルギー合作"))

    def test_price_labels(self):
        self.assertEqual(price_label_en("一般"), "General")
        self.assertEqual(price_label_en("大学生・シニア"), "University · Senior")
        self.assertEqual(price_label_en("毎週火曜日"), "Tuesday")


if __name__ == "__main__":
    unittest.main()
