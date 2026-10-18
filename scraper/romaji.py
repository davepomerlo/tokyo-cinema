"""Japanese → romaji for display.

Uses pykakasi (installed in the GitHub Action) for kanji. If pykakasi isn't
available, a built-in kana table converts hiragana and katakana and leaves any
kanji as they are, so the scan still works.

Style: Hepburn as pykakasi writes it, with long vowels doubled (東京 → toukyou,
シアター → shiataa) — the way you'd type it on a Japanese keyboard.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

JP_RE = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ々〆]")

try:  # pragma: no cover - exercised in CI where pykakasi is installed
    import pykakasi

    _KKS = pykakasi.kakasi()
except Exception:  # noqa: BLE001
    _KKS = None

# ── built-in kana table (fallback) ───────────────────────────────────────────
_BASE = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "ゐ": "i", "ゑ": "e", "を": "wo", "ん": "n",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o", "ゃ": "ya", "ゅ": "yu", "ょ": "yo",
    "ゔ": "vu", "ゎ": "wa",
}
_DIGRAPH = {
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo", "しゃ": "sha", "しゅ": "shu", "しぇ": "she", "しょ": "sho",
    "ちゃ": "cha", "ちゅ": "chu", "ちぇ": "che", "ちょ": "cho", "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
    "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo", "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
    "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo", "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
    "じゃ": "ja", "じゅ": "ju", "じぇ": "je", "じょ": "jo", "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
    "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",
    "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo", "てぃ": "ti", "でぃ": "di", "とぅ": "tu",
    "どぅ": "du", "うぃ": "wi", "うぇ": "we", "うぉ": "wo", "ゔぁ": "va", "ゔぃ": "vi", "ゔぇ": "ve",
    "ゔぉ": "vo", "つぁ": "tsa", "つぃ": "tsi", "つぇ": "tse", "つぉ": "tso", "いぇ": "ye", "でゅ": "dyu",
}


def _kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _kana_to_romaji(s: str) -> str:
    s = _kata_to_hira(s)
    out: list[str] = []
    i = 0
    double_next = False
    while i < len(s):
        c = s[i]
        pair = s[i:i + 2]
        if c in "っ":
            double_next = True
            i += 1
            continue
        if c == "ー":
            m = re.search(r"[aeiou]$", "".join(out))
            if m:
                out.append(m.group(0))
            i += 1
            continue
        if pair in _DIGRAPH:
            r = _DIGRAPH[pair]
            i += 2
        elif c in _BASE:
            r = _BASE[c]
            i += 1
        else:
            r = c
            i += 1
        if double_next and r and r[0] in "bcdfghjkmpqrstvwxyz":
            r = ("t" if r.startswith("ch") else r[0]) + r
        double_next = False
        out.append(r)
    return "".join(out)


def _tidy(s: str) -> str:
    s = s.replace("・", " ").replace("、", ", ").replace("。", ". ").replace("「", "\"").replace("」", "\"")
    s = s.replace("『", "\"").replace("』", "\"").replace("〜", "~").replace("～", "~").replace("〈", "<").replace("〉", ">")
    s = s.replace("【", "[").replace("】", "]")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([,.!?:)\]])", r"\1", s)
    s = re.sub(r"([(\[])\s+", r"\1", s)
    return s.strip()


@lru_cache(maxsize=None)
def to_romaji(text: str | None) -> str | None:
    """'審判（1962）' -> 'Shinpan (1962)'. Text without Japanese is returned unchanged."""
    if not text or not JP_RE.search(text):
        return text
    s = unicodedata.normalize("NFKC", text)
    if _KKS is not None:
        parts: list[str] = []
        for seg in _KKS.convert(s):
            orig = seg.get("orig", "")
            if JP_RE.search(orig):
                parts.append(seg.get("hepburn") or orig)
            else:
                parts.append(orig)
        # pykakasi splits into words; put spaces between Japanese words only
        out = ""
        for p in parts:
            if not p:
                continue
            if out and not out.endswith((" ", "(", "[", "\"", "-", "/")) and not p.startswith((" ", ")", "]", ",", ".", "!", "?", ":", "-", "/")):
                out += " "
            out += p
        s = out
    else:
        s = re.sub(r"[぀-ヿー]+", lambda m: " " + _kana_to_romaji(m.group(0)) + " ", s)
    s = _tidy(s)
    return s[:1].upper() + s[1:] if s else s


# ── countries in English (better than romaji for these) ─────────────────────
COUNTRY_EN = {
    "日本": "Japan", "アメリカ": "USA", "イギリス": "UK", "カナダ": "Canada", "オーストラリア": "Australia",
    "ニュージーランド": "New Zealand", "アイルランド": "Ireland", "フランス": "France", "ベルギー": "Belgium",
    "ドイツ": "Germany", "西ドイツ": "West Germany", "東ドイツ": "East Germany", "オーストリア": "Austria",
    "スイス": "Switzerland", "イタリア": "Italy", "スペイン": "Spain", "ポルトガル": "Portugal",
    "メキシコ": "Mexico", "アルゼンチン": "Argentina", "チリ": "Chile", "コロンビア": "Colombia",
    "ブラジル": "Brazil", "ペルー": "Peru", "キューバ": "Cuba", "ウルグアイ": "Uruguay", "ベネズエラ": "Venezuela",
    "ボリビア": "Bolivia", "韓国": "South Korea", "北朝鮮": "North Korea", "中国": "China", "台湾": "Taiwan",
    "香港": "Hong Kong", "マカオ": "Macau", "タイ": "Thailand", "ベトナム": "Vietnam", "インドネシア": "Indonesia",
    "フィリピン": "Philippines", "マレーシア": "Malaysia", "シンガポール": "Singapore", "カンボジア": "Cambodia",
    "ミャンマー": "Myanmar", "インド": "India", "パキスタン": "Pakistan", "バングラデシュ": "Bangladesh",
    "スリランカ": "Sri Lanka", "ネパール": "Nepal", "ブータン": "Bhutan", "イラン": "Iran", "イラク": "Iraq",
    "トルコ": "Turkey", "ロシア": "Russia", "ソ連": "USSR", "ソビエト": "USSR", "ウクライナ": "Ukraine",
    "ポーランド": "Poland", "チェコ": "Czech Republic", "チェコスロバキア": "Czechoslovakia",
    "スロバキア": "Slovakia", "ハンガリー": "Hungary", "ルーマニア": "Romania", "ブルガリア": "Bulgaria",
    "セルビア": "Serbia", "クロアチア": "Croatia", "ユーゴスラビア": "Yugoslavia", "ギリシャ": "Greece",
    "スウェーデン": "Sweden", "デンマーク": "Denmark", "ノルウェー": "Norway", "フィンランド": "Finland",
    "アイスランド": "Iceland", "オランダ": "Netherlands", "ルクセンブルク": "Luxembourg",
    "エストニア": "Estonia", "ラトビア": "Latvia", "リトアニア": "Lithuania", "イスラエル": "Israel",
    "パレスチナ": "Palestine", "レバノン": "Lebanon", "ヨルダン": "Jordan", "シリア": "Syria",
    "サウジアラビア": "Saudi Arabia", "カタール": "Qatar", "アラブ首長国連邦": "UAE", "エジプト": "Egypt",
    "モロッコ": "Morocco", "チュニジア": "Tunisia", "アルジェリア": "Algeria", "セネガル": "Senegal",
    "南アフリカ": "South Africa", "ナイジェリア": "Nigeria", "ケニア": "Kenya", "エチオピア": "Ethiopia",
    "コンゴ": "Congo", "ブルキナファソ": "Burkina Faso", "マリ": "Mali", "ジョージア": "Georgia",
    "アルメニア": "Armenia", "アゼルバイジャン": "Azerbaijan", "モンゴル": "Mongolia",
    "カザフスタン": "Kazakhstan", "キルギス": "Kyrgyzstan", "ウズベキスタン": "Uzbekistan",
    "アフガニスタン": "Afghanistan",
}


def country_en(country: str | None) -> str | None:
    """'デンマーク・チェコ合作' -> 'Denmark/Czech Republic co-production'."""
    if not country:
        return None
    co = "合作" in country
    parts = [p.strip() for p in re.split(r"[・、/／,]", country.replace("合作", "")) if p.strip()]
    names = [COUNTRY_EN.get(p) or to_romaji(p) for p in parts]
    text = "/".join(n for n in names if n)
    return f"{text} co-production" if co and len(names) > 1 else text
