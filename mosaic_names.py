#!/usr/bin/env python3
"""mosaic_names.py — 画像内の指定文字列(名前など)を OCR で見つけてモザイクをかける。

スクリーンショットを公開する前に、ユーザー名・本名・メールアドレスなどの
固定文字列だけを自動で塗りつぶすための単体スクリプト。汎用の PII 検出は
しない。隠したい文字列はこちらで決める(mosaic-names.txt)。

使い方:
    python3 mosaic_names.py screenshot.png
    python3 mosaic_names.py *.png --list          # 検出位置の確認だけ(書き込みなし)
    python3 mosaic_names.py img.png -n 追加の名前  # リストに加えて一時的に追加
    python3 mosaic_names.py img.png --in-place    # 上書き(既定は <名前>.masked.png)

隠す文字列のリスト:
    スクリプトと同じディレクトリの mosaic-names.txt(1行1エントリ、# はコメント)。
    --names-file で別ファイルも指定可。大文字小文字は区別しない。

OCR バックエンド(--backend auto|vision|tesseract|easyocr):
    auto     : macOS なら vision、それ以外は tesseract → easyocr の順に試す
    vision   : macOS 標準の Vision framework(推奨。追加モデル不要・日本語対応)
               必要: pip install pyobjc-framework-Vision pyobjc-framework-Quartz pillow
    tesseract: pytesseract + tesseract 本体(brew install tesseract)
    easyocr  : EasyOCR(モデルダウンロードあり。~/.EasyOCR を再利用)

出力:
    既定では入力の隣に <stem>.masked<ext> を書き出す。元ファイルは変更しない。
"""

from __future__ import annotations

import argparse
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("Pillow が必要です: pip install pillow", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------- data model


@dataclass
class Box:
    """検出1件: 対象文字列と画像座標(px, 左上原点)。"""

    name: str
    x: int
    y: int
    w: int
    h: int
    source_text: str  # マッチ元の OCR 行(確認用)


# ------------------------------------------------------------------ matching


@dataclass
class Targets:
    """照合対象: 固定文字列のリストと、`re:` 行から作った正規表現のリスト。"""

    names: list[str]
    regexes: list[re.Pattern]


def load_names(names_file: Path | None, extra: list[str]) -> Targets:
    """mosaic-names.txt と -n を読み込む。

    `re:` で始まる行は正規表現(大文字小文字無視)として扱う。
    例: `re:[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}` (メールアドレス全般)
        `re:sk-[a-z0-9_-]{8,}` (sk- で始まる API キー)
    """
    raw: list[str] = []
    if names_file and names_file.is_file():
        for line in names_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                raw.append(line)
    raw.extend(n for n in extra if n.strip())

    names: list[str] = []
    regexes: list[re.Pattern] = []
    for entry in raw:
        if entry.startswith("re:"):
            pattern = entry[3:].strip()
            try:
                regexes.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                print(f"正規表現が不正です: {entry!r} ({e})", file=sys.stderr)
                sys.exit(2)
        else:
            names.append(entry)
    # 長いものから照合する(「h.yamamoto」より「zephel01@gmail.com」を先に)。
    names.sort(key=len, reverse=True)
    if not names and not regexes:
        print("隠す文字列がありません(mosaic-names.txt か -n で指定)", file=sys.stderr)
        sys.exit(2)
    return Targets(names, regexes)


# OCR がよく間違える文字の正規化表(照合専用)。0とO、1とl/I/| を同一視する。
_CONFUSION = str.maketrans({"o": "0", "l": "1", "i": "1", "|": "1"})


def _normalize(text: str, confusion: bool = True) -> tuple[str, list[int]]:
    """照合用に正規化した文字列と、正規化後→元の位置の対応表を返す。

    小文字化 + 空白除去(OCR が単語間に挟む空白や `zephel01@gmail. com` の
    ような誤挿入を無視して照合できるようにする)。confusion=True のときは
    OCR 混同文字(0/O, 1/l/I)も同一視する。正規表現照合では 0/O の同一視が
    文字クラス(例: TLD の [a-z]{2,})を壊すため confusion=False を使う。
    """
    out: list[str] = []
    index_map: list[int] = []
    for i, ch in enumerate(text):
        if ch.isspace():
            continue
        ch = ch.lower()
        if confusion:
            ch = ch.translate(_CONFUSION)
        out.append(ch)
        index_map.append(i)
    return "".join(out), index_map


def find_spans(text: str, targets: Targets) -> list[tuple[int, int, str]]:
    """text 中の全ターゲット出現を (start, end, label) で返す。

    固定文字列は大文字小文字を区別せず、OCR の混同文字(0/O, 1/l/I)と
    空白揺れにも耐える。正規表現は元テキストと空白除去テキストの両方に
    当てる(OCR がトークン内に空白を挟んでも拾えるように)。
    返す start/end は元テキスト上の位置。重複スパンは除去する。
    """
    spans: set[tuple[int, int, str]] = set()

    # ---- 固定文字列(混同耐性あり) ----
    hay, index_map = _normalize(text, confusion=True)
    if hay:
        for name in targets.names:
            needle, _ = _normalize(name, confusion=True)
            if not needle:
                continue
            start = 0
            while True:
                i = hay.find(needle, start)
                if i < 0:
                    break
                spans.add((index_map[i], index_map[i + len(needle) - 1] + 1, name))
                start = i + 1

    # ---- 正規表現 ----
    if targets.regexes:
        # 1) 元テキストにそのまま当てる(\b などの境界が正しく効く)
        for rx in targets.regexes:
            for m in rx.finditer(text):
                if m.end() > m.start():
                    spans.add((m.start(), m.end(), f"re:{rx.pattern}"))
        # 2) 空白除去テキストに当てて元位置に写像(OCR の空白誤挿入対策)
        hay2, map2 = _normalize(text, confusion=False)
        if hay2:
            for rx in targets.regexes:
                for m in rx.finditer(hay2):
                    if m.end() > m.start():
                        spans.add(
                            (map2[m.start()], map2[m.end() - 1] + 1, f"re:{rx.pattern}")
                        )

    return sorted(spans)


def sub_box(x: int, y: int, w: int, h: int, text: str, start: int, end: int) -> tuple[int, int, int, int]:
    """OCR ボックス内の部分文字列の位置を、文字位置比で近似する。"""
    n = max(1, len(text))
    x0 = x + int(w * start / n)
    x1 = x + int(w * end / n)
    return x0, y, max(1, x1 - x0), h


# ------------------------------------------------------------- OCR backends


def ocr_vision(path: Path, targets: Targets) -> list[Box]:
    """macOS Vision framework。部分文字列の正確なボックスも取れる。"""
    import Quartz  # type: ignore
    import Vision  # type: ignore
    from Foundation import NSMakeRange, NSURL  # type: ignore

    url = NSURL.fileURLWithPath_(str(path.resolve()))
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    if src is None:
        raise RuntimeError(f"画像を開けません: {path}")
    cg = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    W = Quartz.CGImageGetWidth(cg)
    H = Quartz.CGImageGetHeight(cg)

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(0)  # accurate
    request.setUsesLanguageCorrection_(False)
    try:
        request.setRecognitionLanguages_(["ja-JP", "en-US"])
    except Exception:
        pass
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    ok = handler.performRequests_error_([request], None)
    if isinstance(ok, tuple):  # pyobjc は (bool, error) を返すことがある
        ok = ok[0]
    if not ok:
        raise RuntimeError("Vision の実行に失敗しました")

    def to_px(bb) -> tuple[int, int, int, int]:
        # Vision は左下原点の正規化座標。左上原点の px に変換する。
        x = int(bb.origin.x * W)
        y = int((1.0 - bb.origin.y - bb.size.height) * H)
        w = int(bb.size.width * W)
        h = int(bb.size.height * H)
        return x, y, w, h

    boxes: list[Box] = []
    for obs in request.results() or []:
        cands = obs.topCandidates_(1)
        if cands.count() == 0:
            continue
        cand = cands.objectAtIndex_(0)
        text = str(cand.string())
        for start, end, name in find_spans(text, targets):
            # 部分文字列の正確な矩形を Vision に聞く。失敗したら比率近似。
            rect = None
            try:
                res = cand.boundingBoxForRange_error_(NSMakeRange(start, end - start), None)
                rect = res[0] if isinstance(res, tuple) else res
            except Exception:
                rect = None
            if rect is not None:
                x, y, w, h = to_px(rect.boundingBox())
            else:
                bx, by, bw, bh = to_px(obs.boundingBox())
                x, y, w, h = sub_box(bx, by, bw, bh, text, start, end)
            boxes.append(Box(name, x, y, w, h, text))
    return boxes


def ocr_tesseract(path: Path, targets: Targets) -> list[Box]:
    """pytesseract。行ごとに単語ボックスを連結して照合する。"""
    import pytesseract  # type: ignore

    img = Image.open(path)
    data = pytesseract.image_to_data(
        img, lang="jpn+eng", output_type=pytesseract.Output.DICT
    )
    # (block, par, line) 単位で単語をまとめる
    lines: dict[tuple, list[int]] = {}
    for i, txt in enumerate(data["text"]):
        if txt.strip():
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(i)

    boxes: list[Box] = []
    for idxs in lines.values():
        # 行テキストを半角スペース連結で再構成し、文字位置→単語の対応表を作る
        parts: list[str] = []
        offsets: list[tuple[int, int, int]] = []  # (start, end, word_index)
        pos = 0
        for i in idxs:
            word = data["text"][i]
            if parts:
                pos += 1  # 区切りスペース
            parts.append(word)
            offsets.append((pos, pos + len(word), i))
            pos += len(word)
        line_text = " ".join(parts)
        for start, end, name in find_spans(line_text, targets):
            # マッチ区間に重なる単語ボックスを集めて合成する
            xs0, ys0, xs1, ys1 = [], [], [], []
            for wstart, wend, i in offsets:
                if wend <= start or wstart >= end:
                    continue
                wx, wy = data["left"][i], data["top"][i]
                ww, wh = data["width"][i], data["height"][i]
                # 単語の内側で部分一致した場合は比率で絞る
                s = max(start, wstart) - wstart
                e = min(end, wend) - wstart
                sx, sy, sw, sh = sub_box(wx, wy, ww, wh, data["text"][i], s, e)
                xs0.append(sx); ys0.append(sy)
                xs1.append(sx + sw); ys1.append(sy + sh)
            if xs0:
                x, y = min(xs0), min(ys0)
                boxes.append(Box(name, x, y, max(xs1) - x, max(ys1) - y, line_text))
    return boxes


def ocr_easyocr(path: Path, targets: Targets) -> list[Box]:
    """EasyOCR。チャンク単位のボックスから比率近似で絞る。"""
    import easyocr  # type: ignore

    reader = easyocr.Reader(["ja", "en"], verbose=False)
    boxes: list[Box] = []
    for quad, text, _conf in reader.readtext(str(path)):
        xs = [p[0] for p in quad]
        ys = [p[1] for p in quad]
        bx, by = int(min(xs)), int(min(ys))
        bw, bh = int(max(xs)) - bx, int(max(ys)) - by
        for start, end, name in find_spans(text, targets):
            x, y, w, h = sub_box(bx, by, bw, bh, text, start, end)
            boxes.append(Box(name, x, y, w, h, text))
    return boxes


BACKENDS = {"vision": ocr_vision, "tesseract": ocr_tesseract, "easyocr": ocr_easyocr}


def pick_backend(requested: str) -> list[str]:
    if requested != "auto":
        return [requested]
    if platform.system() == "Darwin":
        return ["vision", "tesseract", "easyocr"]
    return ["tesseract", "easyocr"]


# ------------------------------------------------------------------- mosaic


def pixelate(img: Image.Image, box: Box, pad: int) -> None:
    """box(+pad)の領域をモザイク化する(in place)。"""
    x0 = max(0, box.x - pad)
    y0 = max(0, box.y - pad)
    x1 = min(img.width, box.x + box.w + pad)
    y1 = min(img.height, box.y + box.h + pad)
    if x1 <= x0 or y1 <= y0:
        return
    region = img.crop((x0, y0, x1, y1))
    # ブロックサイズは文字高さ基準: 高さの1/3(最低6px)。読解不能な粗さにする。
    block = max(6, (y1 - y0) // 3)
    small = region.resize(
        (max(1, region.width // block), max(1, region.height // block)),
        Image.BILINEAR,
    )
    region = small.resize(region.size, Image.NEAREST)
    img.paste(region, (x0, y0))


# --------------------------------------------------------------------- main


# ディレクトリ展開の対象拡張子(小文字比較)
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}


def expand_inputs(inputs: list[Path]) -> list[Path]:
    """引数のファイル/ディレクトリを処理対象リストに展開する。

    ディレクトリは直下の画像ファイルを名前順で処理する(サブディレクトリは
    見ない)。過去の実行結果(*.masked.*)は再処理しないよう除外する。
    """
    files: list[Path] = []
    for p in inputs:
        if p.is_dir():
            found = sorted(
                f
                for f in p.iterdir()
                if f.is_file()
                and f.suffix.lower() in IMG_EXTS
                and ".masked" not in f.name
            )
            if not found:
                print(f"{p}: 画像ファイルがありません", file=sys.stderr)
            files.extend(found)
        else:
            files.append(p)
    return files


def output_path(path: Path, args) -> Path:
    if args.in_place:
        return path
    if args.output:
        return Path(args.output)
    if args.out_dir:
        return Path(args.out_dir) / path.name
    return path.with_name(f"{path.stem}.masked{path.suffix}")


def process(path: Path, targets: Targets, args, progress: str = "") -> int:
    out = output_path(path, args)
    if args.skip_existing and not args.in_place and out.exists():
        print(f"{progress}{path}: 出力が既にあるためスキップ -> {out}")
        return 0

    last_err: Exception | None = None
    boxes: list[Box] = []
    used = None
    for backend in pick_backend(args.backend):
        try:
            boxes = BACKENDS[backend](path, targets)
            used = backend
            break
        except ImportError as e:
            last_err = e
        except Exception as e:
            last_err = e
    if used is None:
        print(f"{progress}{path}: OCR バックエンドを起動できませんでした: {last_err}", file=sys.stderr)
        return 1

    for b in boxes:
        print(f"{progress}{path}: [{used}] '{b.name}' @ ({b.x},{b.y}) {b.w}x{b.h}  <- {b.source_text!r}")

    if args.list:
        if not boxes:
            print(f"{progress}{path}: 対象文字列は見つかりませんでした ({used})")
        return 0

    if not boxes:
        if args.out_dir:
            # 一括処理では「検出なし」もコピーして出力先を完全な公開用セットにする
            out.parent.mkdir(parents=True, exist_ok=True)
            Image.open(path).save(out)
            print(f"{progress}{path}: 検出なし(そのままコピー) -> {out}")
        else:
            print(f"{progress}{path}: 対象文字列は見つかりませんでした ({used})")
        return 0

    img = Image.open(path)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    for b in boxes:
        pixelate(img, b, args.pad)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"{progress}{path}: {len(boxes)}箇所をモザイク化 -> {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="画像内の指定文字列(名前など)を OCR で検出してモザイクをかける",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "images",
        nargs="*",
        type=Path,
        help="対象画像またはディレクトリ(ディレクトリは直下の画像を名前順に一括処理)。"
        "省略時は input/ を処理して output/ に書き出す(入力は変更しない)",
    )
    ap.add_argument("-n", "--name", action="append", default=[], help="追加で隠す文字列(複数可)")
    ap.add_argument(
        "--names-file",
        type=Path,
        default=None,
        help="隠す文字列リスト(既定: スクリプトと同じ場所の mosaic-names.txt)",
    )
    ap.add_argument("--backend", choices=["auto", *BACKENDS], default="auto")
    ap.add_argument("--pad", type=int, default=3, help="モザイク領域の余白px(既定3)")
    ap.add_argument("--list", action="store_true", help="検出位置を表示するだけで書き込まない")
    ap.add_argument("--in-place", action="store_true", help="元ファイルを上書きする")
    ap.add_argument("-o", "--output", default=None, help="出力ファイル名(画像1枚のときのみ)")
    ap.add_argument(
        "--out-dir",
        default=None,
        help="出力先ディレクトリ(元ファイル名のまま書き出す。一括処理向け)",
    )
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="出力ファイルが既にあればスキップ(中断した一括処理の再開用)",
    )
    args = ap.parse_args()

    # 引数なし: input/ -> output/ の既定ワークフロー。入力フォルダには一切
    # 書き込まない(出力は必ず output/ 側)。
    if not args.images:
        base = Path(__file__).resolve().parent
        default_in = base / "input"
        if not default_in.is_dir():
            ap.error(
                "画像を指定するか、input/ フォルダを作って画像を置いてください"
                f" (期待する場所: {default_in})"
            )
        args.images = [default_in]
        if not args.out_dir and not args.output and not args.in_place:
            args.out_dir = str(base / "output")

    files = expand_inputs(args.images)

    if args.output and len(files) > 1:
        ap.error("-o は画像1枚のときだけ使えます(一括なら --out-dir)")
    if args.out_dir and args.in_place:
        ap.error("--out-dir と --in-place は同時に使えません")

    names_file = args.names_file or Path(__file__).resolve().parent / "mosaic-names.txt"
    names = load_names(names_file, args.name)

    rc = 0
    total = len(files)
    for i, path in enumerate(files, 1):
        progress = f"[{i}/{total}] " if total > 1 else ""
        if not path.is_file():
            print(f"{progress}{path}: ファイルがありません", file=sys.stderr)
            rc = 1
            continue
        rc |= process(path, names, args, progress)
    return rc


if __name__ == "__main__":
    sys.exit(main())
