"""Film genres.

eiga.com has no genre field, but its synopses almost always name the genre:
"…を描いたヒューマンドラマ", "…のアニメーション映画", "…サスペンス", "ドキュメンタリー".
We read those words. When TMDB is set up, its genres are added too.

A film can have several genres. Films whose synopsis names none get none.
"""

from __future__ import annotations

import re

# Order here is the order of the filter buttons in the app.
GENRES = [
    "anime", "comedy", "drama", "action", "suspense", "thriller", "mystery", "horror",
    "romance", "scifi", "fantasy", "documentary", "music", "history", "crime", "family", "stage",
]

# (genre, regex, where): where = "lead" (first two sentences) or "all" (whole synopsis)
_RULES: list[tuple[str, str, str]] = [
    ("anime", r"アニメ(?!化)|劇場アニメ|アニメーション", "all"),
    ("documentary", r"ドキュメンタリー", "all"),
    ("stage", r"ナショナル・シアター・ライブ|ライブビューイング|ライブ・ビューイング|METライブ|オペラ|バレエ|歌舞伎|舞台を映画館|舞台映像|演劇公演", "all"),
    ("comedy", r"コメディ|喜劇|爆笑|コミカル|ラブコメ", "lead"),
    ("drama", r"ドラマ(?!シリーズ|化)|人間ドラマ|ヒューマンドラマ|青春映画|家族の物語", "lead"),
    ("action", r"アクション|カンフー|格闘|カーチェイス|ガンアクション|スパイ|アドベンチャー|冒険|スペクタクル", "lead"),
    ("suspense", r"サスペンス", "lead"),
    ("thriller", r"スリラー|サイコ(?:パス|スリラー)?", "lead"),
    ("mystery", r"ミステリー|ミステリ|推理|謎解き|探偵", "lead"),
    ("horror", r"ホラー|ゾンビ|怪談|心霊|スプラッター|恐怖を描", "lead"),
    ("romance", r"ラブストーリー|ラブロマンス|ロマンス|恋愛|純愛|ラブコメ", "lead"),
    ("scifi", r"\bSF\b|ＳＦ|SF(?=[ァ-ヶー一-龯])|サイエンス・?フィクション", "lead"),
    ("fantasy", r"ファンタジー", "lead"),
    ("music", r"ミュージカル|音楽映画|音楽ドキュメンタリー|コンサート|ライブ映像|ライブフィルム|バンドの", "all"),
    ("history", r"時代劇|歴史劇|史劇|戦争映画|戦争ドラマ|史実|伝記", "lead"),
    ("crime", r"犯罪|クライム|ヤクザ|ギャング|マフィア|刑事|ノワール", "lead"),
    ("family", r"ファミリー映画|家族で楽しめる|子ども向け|親子で", "all"),
]
_COMPILED = [(g, re.compile(rx), where) for g, rx, where in _RULES]

TMDB_GENRES = {  # TMDB genre id -> ours
    16: "anime", 35: "comedy", 18: "drama", 28: "action", 12: "action", 53: "thriller",
    9648: "mystery", 27: "horror", 10749: "romance", 878: "scifi", 14: "fantasy",
    99: "documentary", 10402: "music", 36: "history", 10752: "history", 80: "crime",
    10751: "family", 37: "action",
}


def _lead(text: str) -> str:
    parts = re.split(r"(?<=[。！？])", text)
    return "".join(parts[:2])


def from_synopsis(synopsis: str | None, title: str | None = None) -> list[str]:
    """Genres named in an eiga.com synopsis (and title)."""
    text = (synopsis or "").strip()
    found: set[str] = set()
    if not text and not title:
        return []
    lead = _lead(text) + " " + (title or "")
    whole = text + " " + (title or "")
    for genre, rx, where in _COMPILED:
        if rx.search(lead if where == "lead" else whole):
            found.add(genre)
    # A documentary "about" crime or war is still a documentary first.
    if "documentary" in found:
        found -= {"drama", "crime", "history"}
    # A stage recording isn't a drama film, whatever the play is.
    if "stage" in found:
        found.discard("drama")
    # A story with no genre word is, nearly always, a drama.
    if not found and re.search(r"描く|描いた|描き|描写|物語|ストーリー|人生|主人公|少女|少年|男|女", _lead(text)):
        found.add("drama")
    return [g for g in GENRES if g in found]


def from_tmdb(genre_ids: list[int] | None) -> list[str]:
    out = {TMDB_GENRES[i] for i in (genre_ids or []) if i in TMDB_GENRES}
    return [g for g in GENRES if g in out]


def combine(*lists: list[str] | None) -> list[str]:
    s: set[str] = set()
    for lst in lists:
        s.update(lst or [])
    return [g for g in GENRES if g in s]
