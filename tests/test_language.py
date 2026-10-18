"""Audio-language / subtitle rules.  python -m unittest discover tests"""

import unittest

from scraper.eiga import find_format
from scraper.language import audio_subs, film_language, lang_from_country


def decide(fmt, country=None, lang=None):
    m = {"country": country}
    if lang:
        m["lang"] = lang
    code, sure = film_language(m)
    return audio_subs(fmt, code, sure)


class TestLanguage(unittest.TestCase):
    def test_country_guess(self):
        self.assertEqual(lang_from_country("フランス"), ("fr", True))
        self.assertEqual(lang_from_country("日本"), ("ja", True))
        self.assertEqual(lang_from_country("カナダ"), ("en", False))
        self.assertEqual(lang_from_country("デンマーク・チェコ合作"), ("orig", True))
        self.assertEqual(lang_from_country("日本・フランス・シンガポール合作"), ("ja", False))
        self.assertEqual(lang_from_country("フランス・日本合作"), ("orig", False))
        self.assertEqual(lang_from_country(None), (None, False))

    def test_japanese_film(self):
        self.assertEqual(decide(None, "日本"), {"a": "ja", "sub": "none", "sure": True})
        # 字幕 on a Japanese film = Japanese captions (accessibility screening)
        self.assertEqual(decide("字幕", "日本"), {"a": "ja", "sub": "ja", "sure": True})
        self.assertEqual(decide("英語字幕", "日本"), {"a": "ja", "sub": "en", "sure": True})

    def test_foreign_film(self):
        self.assertEqual(decide("字幕", "フランス"), {"a": "fr", "sub": "ja", "sure": True})
        self.assertEqual(decide(None, "フランス"), {"a": "fr", "sub": "ja", "sure": False})
        self.assertEqual(decide("吹替", "アメリカ"), {"a": "ja-dub", "sub": "none", "sure": True})
        self.assertEqual(decide("字幕", "デンマーク・チェコ合作"), {"a": "orig", "sub": "ja", "sure": True})

    def test_tmdb_language_wins(self):
        # Orson Welles' The Trial: a French/German/Italian co-production in English
        self.assertEqual(decide("字幕", "フランス・西ドイツ・イタリア合作", lang="en"),
                         {"a": "en", "sub": "ja", "sure": True})

    def test_foreign_language_subtitles(self):
        self.assertEqual(decide("外国語字幕", "日本"), {"a": "ja", "sub": "en", "sure": False})

    def test_unknown(self):
        self.assertEqual(decide(None), {"a": None, "sub": None, "sure": False})

    def test_format_words(self):
        self.assertEqual(find_format("英語字幕付"), "英語字幕付")
        self.assertEqual(find_format("with English subtitles"), "with English subtitles")
        self.assertEqual(decide(find_format("英語字幕版"), "日本")["sub"], "en")


if __name__ == "__main__":
    unittest.main()
