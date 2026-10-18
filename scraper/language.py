"""Work out each screening's audio language and subtitles.

Two inputs:
  1. the format label eiga.com prints next to the times (字幕, 吹替, 英語字幕…), which
     is a *stated* fact;
  2. the film's original language — from TMDb when a TMDB_API_KEY secret is set,
     otherwise guessed from the production country on eiga.com.

When the label doesn't say, the screening is marked "likely" rather than stated.
Japanese convention: an unlabelled foreign film is shown in its original language with
Japanese subtitles; dubbed showings are always labelled 吹替.
"""

from __future__ import annotations

import os
import re

import requests

# eiga.com writes countries in Japanese; map the common ones to their main language.
COUNTRY_LANG = {
    "日本": "ja", "アメリカ": "en", "イギリス": "en", "カナダ": "en", "オーストラリア": "en",
    "ニュージーランド": "en", "アイルランド": "en", "フランス": "fr", "ベルギー": "fr",
    "ドイツ": "de", "オーストリア": "de", "スイス": "de", "イタリア": "it", "スペイン": "es",
    "メキシコ": "es", "アルゼンチン": "es", "チリ": "es", "コロンビア": "es", "ポルトガル": "pt",
    "ブラジル": "pt", "韓国": "ko", "中国": "zh", "台湾": "zh", "香港": "cn", "タイ": "th",
    "ベトナム": "vi", "インドネシア": "id", "フィリピン": "tl", "インド": "hi", "イラン": "fa",
    "トルコ": "tr", "ロシア": "ru", "ウクライナ": "uk", "ポーランド": "pl", "チェコ": "cs",
    "ハンガリー": "hu", "ルーマニア": "ro", "ギリシャ": "el", "スウェーデン": "sv",
    "デンマーク": "da", "ノルウェー": "no", "フィンランド": "fi", "オランダ": "nl",
    "イスラエル": "he", "エジプト": "ar", "レバノン": "ar", "パレスチナ": "ar",
    "ジョージア": "ka", "西ドイツ": "de", "東ドイツ": "de", "ソ連": "ru", "ソビエト": "ru",
    "チェコスロバキア": "cs", "ペルー": "es", "キューバ": "es", "ウルグアイ": "es",
    "ベネズエラ": "es", "ボリビア": "es", "エストニア": "et", "リトアニア": "lt", "ラトビア": "lv",
    "アイスランド": "is", "スロバキア": "sk", "セルビア": "sr", "クロアチア": "hr", "ブルガリア": "bg", "モンゴル": "mn", "カザフスタン": "kk", "セネガル": "fr",
}

# Countries where the main language is a poor guess (multilingual or English-mixed).
AMBIGUOUS = {"スイス", "ベルギー", "カナダ", "インド", "香港", "フィリピン", "イスラエル", "セネガル"}

LANG_NAMES = {  # code -> (English, Japanese)
    "orig": ("Original language", "原語"), "ja-dub": ("Japanese dub", "日本語吹替"),
    "ja": ("Japanese", "日本語"), "en": ("English", "英語"), "fr": ("French", "フランス語"),
    "de": ("German", "ドイツ語"), "it": ("Italian", "イタリア語"), "es": ("Spanish", "スペイン語"),
    "pt": ("Portuguese", "ポルトガル語"), "ko": ("Korean", "韓国語"), "zh": ("Mandarin", "中国語"),
    "cn": ("Cantonese", "広東語"), "th": ("Thai", "タイ語"), "vi": ("Vietnamese", "ベトナム語"),
    "id": ("Indonesian", "インドネシア語"), "tl": ("Filipino", "フィリピン語"),
    "hi": ("Hindi", "ヒンディー語"), "ta": ("Tamil", "タミル語"), "te": ("Telugu", "テルグ語"),
    "fa": ("Persian", "ペルシャ語"), "tr": ("Turkish", "トルコ語"), "ru": ("Russian", "ロシア語"),
    "uk": ("Ukrainian", "ウクライナ語"), "pl": ("Polish", "ポーランド語"), "cs": ("Czech", "チェコ語"),
    "hu": ("Hungarian", "ハンガリー語"), "ro": ("Romanian", "ルーマニア語"), "el": ("Greek", "ギリシャ語"),
    "sv": ("Swedish", "スウェーデン語"), "da": ("Danish", "デンマーク語"), "no": ("Norwegian", "ノルウェー語"),
    "fi": ("Finnish", "フィンランド語"), "nl": ("Dutch", "オランダ語"), "he": ("Hebrew", "ヘブライ語"),
    "ar": ("Arabic", "アラビア語"), "ka": ("Georgian", "ジョージア語"), "mn": ("Mongolian", "モンゴル語"),
    "kk": ("Kazakh", "カザフ語"), "et": ("Estonian", "エストニア語"), "lt": ("Lithuanian", "リトアニア語"),
    "lv": ("Latvian", "ラトビア語"), "is": ("Icelandic", "アイスランド語"), "sk": ("Slovak", "スロバキア語"),
    "sr": ("Serbian", "セルビア語"), "hr": ("Croatian", "クロアチア語"), "bg": ("Bulgarian", "ブルガリア語"), "xx": ("No dialogue", "台詞なし"),
}


def lang_from_country(country: str | None) -> tuple[str | None, bool]:
    """Guess (language, certain?) from eiga.com's production-country text.

    'フランス' -> ('fr', True); 'デンマーク・チェコ合作' -> ('orig', True): co-productions
    are too mixed to name a language, but are clearly not Japanese-language films unless
    Japan is involved. Returns 'orig' for "original (non-Japanese) language".
    """
    if not country:
        return None, False
    parts = [p.strip() for p in re.split(r"[・、/／,]", country.replace("合作", "")) if p.strip()]
    if not parts:
        return None, False
    if len(parts) == 1:
        code = COUNTRY_LANG.get(parts[0])
        return (code or "orig"), parts[0] not in AMBIGUOUS
    if parts[0] == "日本":
        return "ja", False
    if "日本" in parts:
        return "orig", False
    return "orig", True


def tmdb_lookup(session: requests.Session, title_ja: str, title_en: str | None,
                year: int | None) -> dict | None:
    """Find the film on TMDb; return original language and an English title."""
    key = os.environ.get("TMDB_API_KEY")
    if not key:
        return None
    base = "https://api.themoviedb.org/3/search/movie"
    auth = {"Authorization": f"Bearer {key}"} if len(key) > 40 else {}
    queries = [q for q in (title_ja, title_en) if q]
    for q in queries:
        params = {"query": q, "language": "en-US", "include_adult": "false"}
        if len(key) <= 40:
            params["api_key"] = key
        try:
            r = session.get(base, params=params, headers=auth, timeout=20)
            r.raise_for_status()
            results = r.json().get("results", [])
        except Exception as exc:
            print(f"  TMDb lookup failed for {q}: {exc}")
            return None
        for res in results[:8]:
            ry = (res.get("release_date") or "")[:4]
            if year and ry.isdigit() and abs(int(ry) - year) > 1:
                continue
            return {
                "tmdb_id": res.get("id"),
                "lang": res.get("original_language"),
                "tmdb_title": res.get("title"),
                "tmdb_original_title": res.get("original_title"),
            }
    return None


def film_language(movie: dict) -> tuple[str | None, bool]:
    """(language code, certain?) for a cached movie record."""
    if movie.get("lang"):
        return movie["lang"], True
    return lang_from_country(movie.get("country"))


def audio_subs(fmt: str | None, film_lang: str | None, lang_certain: bool) -> dict:
    """Decide audio + subtitles for one screening.

    Returns {"a": code|"ja-dub"|None, "sub": "ja"|"en"|"none"|None, "sure": bool}
    """
    f = (fmt or "").lower()
    foreign = film_lang not in (None, "ja", "xx")

    if "吹替" in f or "吹き替え" in f or "dub" in f:
        return {"a": "ja-dub", "sub": "none", "sure": True}
    if "外国語字幕" in f:
        # "foreign-language subtitles": subtitles for non-Japanese speakers, usually English
        return {"a": film_lang, "sub": "en", "sure": False}
    if "英語字幕" in f or "english sub" in f or "eng sub" in f:
        return {"a": film_lang, "sub": "en", "sure": film_lang is not None and lang_certain}
    if "日本語字幕" in f or "字幕" in f:
        if film_lang == "ja":
            # Japanese film with Japanese captions (barrier-free / accessibility screening)
            return {"a": "ja", "sub": "ja", "sure": lang_certain}
        return {"a": film_lang, "sub": "ja", "sure": lang_certain and film_lang is not None}

    # No label on the page.
    if film_lang == "ja":
        return {"a": "ja", "sub": "none", "sure": lang_certain}
    if foreign:
        # Unlabelled foreign film: original audio + Japanese subtitles is the norm.
        return {"a": film_lang, "sub": "ja", "sure": False}
    return {"a": None, "sub": None, "sure": False}
