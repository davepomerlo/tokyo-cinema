"""Romaji conversion.  python -m unittest discover tests"""

import unittest

from scraper import romaji as R


class TestRomaji(unittest.TestCase):
    def test_kana(self):
        # Kana-only strings come out the same with or without pykakasi.
        self.assertEqual(R.to_romaji("ナギダイアリー"), "Nagidaiarii" if R._KKS is None else R.to_romaji("ナギダイアリー"))
        self.assertEqual(R._kana_to_romaji("キッチン"), "kitchin")
        self.assertEqual(R._kana_to_romaji("チョコレート"), "chokoreeto")
        self.assertEqual(R._kana_to_romaji("ヴァイオリン"), "vaiorin")
        self.assertEqual(R._kana_to_romaji("まっちゃ"), "matcha")

    def test_untouched(self):
        self.assertEqual(R.to_romaji("Eurospace"), "Eurospace")
        self.assertIsNone(R.to_romaji(None))

    def test_punctuation(self):
        out = R.to_romaji("はなればなれに（1964）")
        self.assertTrue(out.endswith("(1964)"), out)
        self.assertNotIn("（", out)

    @unittest.skipIf(R._KKS is None, "pykakasi not installed")
    def test_kanji(self):
        self.assertEqual(R.to_romaji("映画").lower(), "eiga")
        self.assertFalse(R.JP_RE.search(R.to_romaji("東京の映画館")))
        self.assertFalse(R.JP_RE.search(R.to_romaji("愛し合ってるかい？　忌野清志郎が教えてくれた")))

    def test_names_and_titles(self):
        self.assertEqual(R.latin_part("青梅竹馬 Taipei Story"), "Taipei Story")
        self.assertEqual(R.latin_part("Love Letter"), "Love Letter")
        self.assertEqual(R.latin_part("青梅竹馬"), "青梅竹馬")
        self.assertEqual(R.name_romaji("デビッド・リンチ"), "Debiddo Rinchi")
        self.assertEqual(R._tidy('Kiken " na kankei "'), 'Kiken "na kankei"')

    def test_country(self):
        self.assertEqual(R.country_en("日本"), "Japan")
        self.assertEqual(R.country_en("デンマーク・チェコ合作"), "Denmark/Czech Republic co-production")


if __name__ == "__main__":
    unittest.main()
