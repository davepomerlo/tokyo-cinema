"""Genre classification.  python -m unittest discover tests"""

import unittest

from scraper.eiga import parse_movie_page
from scraper.genres import combine, from_synopsis, from_tmdb


class TestGenres(unittest.TestCase):
    def test_synopsis(self):
        self.assertEqual(from_synopsis("ウクライナ侵攻後からロシアで行われている愛国教育の全貌を暴いたドキュメンタリー。教師たちの葛藤を描く。"),
                         ["documentary"])
        self.assertEqual(from_synopsis("人気漫画を原作にした劇場アニメ。少年たちの友情と冒険を描く。"), ["anime", "action"])
        self.assertEqual(from_synopsis("孤独な刑事が連続殺人事件の真相に迫るサスペンススリラー。"),
                         ["suspense", "thriller", "crime"])
        self.assertEqual(from_synopsis("離婚寸前の夫婦が旅に出るヒューマンドラマ。笑いと涙のコメディ要素も。"), ["comedy", "drama"])
        self.assertEqual(from_synopsis("近未来を舞台にしたSFアクション。"), ["action", "scifi"])
        self.assertEqual(from_synopsis("英国ナショナル・シアター・ライブの舞台ドラマを映画館で上映。"), ["stage"])
        self.assertEqual(from_synopsis(""), [])
        self.assertEqual(from_synopsis("天国の恋人に宛てた1通の手紙を描く。"), ["romance"])
        self.assertEqual(from_synopsis("英雄オデュッセウスの壮大な冒険を描く。"), ["action"])
        self.assertEqual(from_synopsis("北海道の小さな町で暮らす少女の成長を描く。"), ["drama"])

    def test_lead_only(self):
        # "ドラマ" late in a long synopsis (e.g. "TVドラマで知られる監督") shouldn't count
        text = "老人と犬が海を目指す。二人の旅路。監督はテレビドラマで知られる人物。"
        self.assertNotIn("drama", from_synopsis(text))

    def test_tmdb(self):
        self.assertEqual(from_tmdb([18, 10749, 999]), ["drama", "romance"])
        self.assertEqual(combine(["anime"], ["drama", "anime"]), ["anime", "drama"])

    def test_movie_page(self):
        html = """<html><head><script type="application/ld+json">[{"@type":"Movie","name":"x",
        "description":"記憶を失った男の逃亡を描くアクション・スリラー。"}]</script></head><body><h1>x</h1></body></html>"""
        self.assertEqual(parse_movie_page(html)["genres_eiga"], ["action", "thriller"])


if __name__ == "__main__":
    unittest.main()
