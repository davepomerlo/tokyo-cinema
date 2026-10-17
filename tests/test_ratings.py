"""Score parsing.  python -m unittest discover tests"""

import unittest
from unittest import mock

from scraper.eiga import parse_movie_page
from scraper.ratings import omdb_scores, parse_eiga_rating, public_scores


class FakeResp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class TestRatings(unittest.TestCase):
    def test_eiga_rating(self):
        self.assertEqual(parse_eiga_rating("平均評価 3.8全35件"), {"v": 3.8, "n": 35})
        self.assertEqual(parse_eiga_rating("3.8\n全1,204件"), {"v": 3.8, "n": 1204})
        self.assertIsNone(parse_eiga_rating("0.0全0件"))
        self.assertIsNone(parse_eiga_rating("no rating here"))

    def test_movie_page_rating(self):
        html = "<html><body><h1>x</h1><div><a title='平均評価'><span>3.8</span><span>全35件</span></a></div></body></html>"
        self.assertEqual(parse_movie_page(html)["scores_eiga"], {"v": 3.8, "n": 35})

    def test_public_scores(self):
        out = public_scores({"eiga": {"v": 4.0, "n": 50}, "tmdb": {"v": 7.0, "n": 5},
                             "imdb": {"v": 7.6, "n": 9000}, "rt": 90, "mc": 72})
        self.assertNotIn("tmdb", out)  # too few votes
        self.assertEqual(out["avg"], round((80 + 76 + 90 + 72) / 4))

    def test_omdb(self):
        data = {"Response": "True", "imdbRating": "7.6", "imdbVotes": "92,104", "Metascore": "N/A",
                "Ratings": [{"Source": "Internet Movie Database", "Value": "7.6/10"},
                            {"Source": "Rotten Tomatoes", "Value": "85%"},
                            {"Source": "Metacritic", "Value": "71/100"}]}
        session = mock.Mock()
        session.get.return_value = FakeResp(data)
        with mock.patch.dict("os.environ", {"OMDB_API_KEY": "k"}):
            self.assertEqual(omdb_scores(session, "tt0057427"),
                             {"imdb": {"v": 7.6, "n": 92104}, "rt": 85, "mc": 71})


if __name__ == "__main__":
    unittest.main()
