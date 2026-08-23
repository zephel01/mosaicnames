"""照合ロジック(find_spans)のテスト。OCR は使わない。

ここで守りたいのは2点:
  1. OCR がどう誤読しても、隠したい文字列は見つかる(取りこぼさない)
  2. 関係ない文字列を巻き込まない(誤爆しない)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mosaic_names import Targets, find_spans  # noqa: E402

NAMES = [
    "zephel01@gmail.com",
    "hyamamotonomacbook-pro",
    "Hideki Yamamoto",
    "h.yamamoto",
    "zephel01",
]


def targets(fuzzy: bool = True, regexes: list[str] | None = None) -> Targets:
    # 本体と同じく長い順に照合する
    return Targets(
        sorted(NAMES, key=len, reverse=True),
        [re.compile(r, re.IGNORECASE) for r in (regexes or [])],
        fuzzy,
    )


def matched(text: str, fuzzy: bool = True, regexes: list[str] | None = None) -> set[str]:
    """検出された「元テキスト上の部分文字列」の集合。"""
    return {text[s:e] for s, e, _name in find_spans(text, targets(fuzzy, regexes))}


# ---------------------------------------------------------------- 取りこぼし


@pytest.mark.parametrize(
    "line",
    [
        # そのまま
        "zephel01@NucBox-EVO-X2:/mnt/data/models$ ls",
        # 0/O・1/l/I の混同(正規化表で吸収)
        "zephelOl@NucBox-EVO-X2:/mnt/data/models$ ls",
        "zephe1O1@NucBox-EVO-X2:/mnt/data/models$ ls",
        # スラッシュ付きゼロが @ と読まれる(あいまい一致が必要)
        "zephel@1@NucBox-EVO-X2: /mnt/data/models$ 1s",
        "zepheL@1@NucBox-EV0-X2: /mnt/data/models$ 1s",
        # 1文字読み落とし / 余計な1文字
        "zephe01@NucBox",
        "zepheli01@NucBox",
    ],
)
def test_username_is_found_despite_ocr_errors(line: str) -> None:
    assert matched(line), f"検出できなかった: {line!r}"


def test_exact_match_needs_no_fuzzy() -> None:
    line = "zephel01@NucBox-EVO-X2:~$"
    assert "zephel01" in matched(line, fuzzy=False)


def test_fuzzy_is_required_for_unknown_confusion() -> None:
    """`0` が `@` と読まれるケースは正規化表では拾えない = あいまい一致の存在意義。"""
    line = "zephel@1@NucBox-EVO-X2:~$"
    assert not matched(line, fuzzy=False)
    assert matched(line, fuzzy=True)


def test_space_injected_inside_token() -> None:
    """OCR がトークン途中に空白を挟んでも照合できる。"""
    assert matched("mail: zephel01@gmail. com", fuzzy=False)


def test_regex_matches_across_injected_space() -> None:
    found = matched(
        "key: sk-proj -abcdef123456",
        fuzzy=False,
        regexes=[r"\bsk-[a-z0-9_-]{8,}"],
    )
    assert found


# -------------------------------------------------------------------- 誤爆


@pytest.mark.parametrize(
    "line",
    [
        "BugTraceAI-Apex-G4-26B-Q4.gguf",
        "Qwen3.8-27B-Heretic-Q4_K_M.gguf",
        "Kwaipilot_KAT-Coder-V2.5-Dev-Q4_K_M.gguf",
        "DeepSeek-V4-Flash-0731-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-imatrix.gguf",
        "gemma4-12b-qat-google",
        "Qwen3.5-9B-The-Defiant-Fable-Uncnr-Heretic-NEO-MAX",
        "$ ls -la /mnt/nas-data/models",
    ],
)
def test_unrelated_lines_are_not_matched(line: str) -> None:
    assert not matched(line), f"誤検出した: {line!r}"


def test_short_entries_are_excluded_from_fuzzy() -> None:
    """短いエントリで編集距離を許すと誤爆だらけになるので、対象外にしている。"""
    t = Targets(["4.85"], [], True)
    assert not find_spans("Qwen 4.35 / 4.05 / 1.85", t)
    assert find_spans("version 4.85 build", t)


# ---------------------------------------------------------------- 範囲の妥当性


def test_span_covers_only_the_username() -> None:
    line = "zephel@1@NucBox-EVO-X2:/mnt/data/models$ ls"
    spans = [(s, e) for s, e, n in find_spans(line, targets()) if n == "zephel01"]
    assert spans
    s, e = spans[0]
    assert line[s:e] == "zephel@1"
