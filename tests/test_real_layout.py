"""Parser tests on markup that mirrors eiga.com's actual theater page (Oct 2026).

    python -m unittest discover tests
"""

import datetime as dt
import unittest

from scraper.eiga import parse_theater_page

TODAY = dt.date(2026, 10, 18)

PAGE = """<html><body><main><div class="content-container">
<section data-title="愛し合ってるかい？" id="m104848">
 <h2 class="title-xlarge"><a href="/movie/104848/">愛し合ってるかい？</a></h2>
 <div class="theater-wrapper">
  <div class="movie-image"><img src="https://media.eiga.com/images/movie/104848/photo/x/320.jpg">
   <span class="rating-star val40">3.8</span><p class="data"><span>10月2日公開</span><span>124分</span><span>G</span></p></div>
  <div class="movie-schedule"><table class="weekly-schedule"><tbody><tr class="slide-5">
   <td class="holiday" data-date="20261018"><p class="date">10/18<span>（日）</span></p>
    <a class="official" href="http://www.eurospace.co.jp/schedule/">10:25</a>
    <a class="official" href="http://www.eurospace.co.jp/schedule/">15:25<small>～17:39</small></a></td>
   <td data-date="20261019"><p class="date">10/19<span>（月）</span></p>
    <a class="official" href="http://www.eurospace.co.jp/schedule/">10:00</a></td>
  </tr></tbody></table></div>
 </div>
</section>
<section data-title="ナギダイアリー" id="m105726">
 <h2><a href="/movie/105726/">ナギダイアリー</a></h2>
 <div class="movie-schedule"><table class="weekly-schedule"><tbody><tr>
   <td data-date="20261018"><p class="date">10/18（日）</p><a>17:55<small>～19:55</small></a></td>
 </tr></tbody></table></div>
 <div class="movie-schedule"><div class="movie-type"><span class="type-subtitled">字幕</span></div>
  <table class="weekly-schedule"><tbody><tr>
   <td data-date="20261018"><p class="date">10/18（日）</p></td>
   <td data-date="20261019"><p class="date">10/19（月）</p><a>14:15<small>～16:15</small></a></td>
 </tr></tbody></table></div>
 <div class="movie-schedule"><div class="movie-type"><span class="type-imax">IMAX</span><span class="type-dubbed">吹替</span></div>
  <table class="weekly-schedule"><tbody><tr>
   <td data-date="20261019"><p class="date">10/19（月）</p><span>25:10</span></td>
 </tr></tbody></table></div>
</section>
<section id="m999"><h2><a href="/movie/999/">近日公開の映画</a></h2>
 <div class="movie-schedule"><table class="weekly-schedule"><tr><td data-date="20261018"><p class="date">10/18</p></td></tr></table></div>
</section>
</div>
<table class="theater-table"><tbody>
 <tr><th scope="row">住所</th><td>渋谷区<br><a class="icon official" href="http://www.eurospace.co.jp/">映画館公式ページ</a></td></tr>
 <tr><th scope="row">割引情報</th><td><ul class="discount"><li>サービスデー 毎月1日1100円</li><li>毎週火曜日1300円</li><li>映画の日(12/1)1000円</li></ul></td></tr>
 <tr class="border"><th rowspan="3" scope="row">基本料金</th><td>一般 2000円</td></tr>
 <tr><td>大学生・シニア 1400円</td></tr>
 <tr><td>（作品によって料金に差異がある場合あり）</td></tr>
</tbody></table>
</main></body></html>"""

CLOSED = """<html><body><main><p>ホーム &gt; 新宿武蔵野館</p>
<p class="notice">9月23日（水・祝）武蔵野ビルで発生した火災の影響で、臨時休館となっております。</p>
<table class="theater-table"><tr><th>基本料金</th><td>一般 2000円</td></tr></table></main></body></html>"""


class TestRealLayout(unittest.TestCase):
    def setUp(self):
        self.p = parse_theater_page(PAGE, TODAY)

    def rows(self, mid):
        return [(s.date, s.start, s.end, s.fmt) for s in self.p.screenings if s.movie_id == mid]

    def test_schedule(self):
        self.assertEqual(self.rows("104848"), [
            ("2026-10-18", "10:25", None, None), ("2026-10-18", "15:25", "17:39", None),
            ("2026-10-19", "10:00", None, None)])
        self.assertEqual(self.rows("105726"), [
            ("2026-10-18", "17:55", "19:55", None), ("2026-10-19", "14:15", "16:15", "字幕"),
            ("2026-10-19", "25:10", None, "IMAX 吹替")])
        self.assertEqual(self.rows("999"), [])

    def test_film_details(self):
        self.assertEqual(self.p.movies["104848"].runtime, 124)
        self.assertTrue(self.p.movies["104848"].poster.endswith("320.jpg"))

    def test_prices(self):
        self.assertEqual(self.p.prices, [{"label_ja": "一般", "yen": 2000},
                                         {"label_ja": "大学生・シニア", "yen": 1400}])
        self.assertIn("差異", self.p.price_note)
        labels = [d["label_ja"] for d in self.p.discounts]
        self.assertEqual(labels[:2], ["サービスデー 毎月1日", "毎週火曜日"])
        self.assertFalse(any(l.startswith("1)") for l in labels))
        self.assertEqual(self.p.official_url, "http://www.eurospace.co.jp/")

    def test_closed(self):
        p = parse_theater_page(CLOSED, TODAY)
        self.assertIn("臨時休館", p.notice)
        self.assertFalse(p.notice.startswith("ホーム"))


if __name__ == "__main__":
    unittest.main()
