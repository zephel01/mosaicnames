<div align="center">

# mosaic-names

**スクリーンショットの「見せたくない文字列」だけを、OCR で見つけて自動モザイク。**

ユーザー名・本名・メールアドレス・API キー。ターミナルやエディタのスクショに
写り込むそれらを、公開前にコマンド一発で塗りつぶすローカル完結ツールです。

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/managed%20by-uv-DE5FE9?logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![OCR](https://img.shields.io/badge/OCR-Apple%20Vision%20%7C%20Tesseract%20%7C%20EasyOCR-8A2BE2)](#-仕組み)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey?logo=apple)](#-仕組み)
[![Local](https://img.shields.io/badge/privacy-%E3%83%AD%E3%83%BC%E3%82%AB%E3%83%AB%E5%AE%8C%E7%B5%90%EF%BC%88%E9%80%81%E4%BF%A1%E3%81%AA%E3%81%97%EF%BC%89-brightgreen)](#-特徴)

<img src="docs/demo.png" width="880" alt="input/ の元スクリーンショットに写っていたユーザー名・メールアドレス・APIキーが、output/ では自動でモザイク化されている before/after" />

</div>

---

## ✨ 特徴

- 🎯 **自分で決めた文字列だけを隠す** — 汎用の個人情報検出はしない。`mosaic-names.txt` に書いた文字列(と正規表現)だけが対象。誤爆しない
- 🔍 **OCR の誤読に強い** — `0/O`・`1/l/I` の混同、トークン途中への空白の誤挿入(`sk-proj -Abc...`)、さらに**あいまい一致**で未知の誤読(`zephel01` → `zephel@1` など)まで拾う
- 🔑 **メールアドレス・API キーは正規表現で** — `re:` 行でパターン指定。メール全般と `sk-` 系キーは既定で同梱
- 📁 **input/ → output/ の安全設計** — 元ファイルには一切書き込まない。検出ゼロの画像もコピーされるので output/ がそのまま公開セットになる
- 🍎 **macOS は追加モデル不要** — 標準の Vision framework で日本語 OCR。画像はどこにも送信されない(完全ローカル)
- 🧩 **単一ファイルのスクリプト** — 依存は Pillow +(macOS なら pyobjc)。アプリでもサービスでもなく、読める量のPython
- 📌 **uv でバージョン固定** — `uv.lock` をコミットしているので、`uv sync` すればどのマシンでも同じ依存バージョンが入る

## 🚀 クイックスタート

[uv](https://docs.astral.sh/uv/) が必要です(未インストールなら `brew install uv`、または
`curl -LsSf https://astral.sh/uv/install.sh | sh`)。

```bash
git clone https://github.com/zephel01/mosaicnames.git
cd mosaicnames
./setup.sh        # uv sync・設定ファイル・input/ output/ を全部用意(冪等)
```

あとは3手:

```bash
vim mosaic-names.txt   # 1. 隠したい文字列を書く(サンプルから作成済み)
open input/            # 2. スクリーンショットを input/ に置く
./mosaic               # 3. 一括処理 → output/ に公開用セットが出来る
```

処理前に検出箇所だけ確認したいときは:

```bash
./mosaic --list
```

`./mosaic` は内部で `uv run` を呼ぶので、`./setup.sh` を忘れていても依存は
自動で同期されます(`.venv` の activate も不要)。

## 📝 隠す文字列の書き方(mosaic-names.txt)

1行1エントリ。`#` はコメント。大文字小文字は区別せず、行内の部分一致でも
その部分だけがモザイク化されます。

```
# 固定文字列(自分のものに置き換える)
yourname
Your Full Name
your-machine-name

# `re:` で始まる行は正規表現(大文字小文字無視)
re:[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}   # メールアドレス全般
re:\bsk-[a-z0-9_-]{8,}                     # sk- 系 API キー(OpenAI / Anthropic)
```

トークン形式は同じ要領で追加できます:

```
re:\bghp_[a-z0-9]{20,}          # GitHub personal access token
re:\bxox[bpars]-[a-z0-9-]{10,}  # Slack token
re:\bAKIA[0-9A-Z]{16}           # AWS access key ID
```

> **Note**
> 実際の `mosaic-names.txt` は個人情報そのものなので `.gitignore` 済み。
> リポジトリに入るのはサンプル(`mosaic-names.example.txt`)だけです。

## 📁 ワークフロー

```
input/    ← スクショを置く(このフォルダは読み取りのみ。絶対に変更されない)
  ↓  ./mosaic
output/   ← マスク済みが元ファイル名で出力。検出ゼロの画像もコピーされる
```

`input/`・`output/`・`photo/` は `.gitignore` 済みなので、マスク前の原本を
うっかりコミットする事故も防げます。

個別のファイルやフォルダを指定した処理も可能です:

```bash
./mosaic screenshot.png                  # 単発 → screenshot.masked.png
./mosaic shots/ --out-dir publish        # 任意フォルダを一括 → publish/ へ
./mosaic img.png -n "この文字列も追加で"   # リストに一時追加
```

## 🔧 オプション

| オプション | 説明 |
|---|---|
| `--list` | 検出位置を表示するだけ。ファイルは書き込まない |
| `--out-dir DIR` | 出力先ディレクトリ(元ファイル名のまま集約) |
| `--skip-existing` | 出力が既にあればスキップ(中断した一括処理の再開) |
| `-n TEXT` | 隠す文字列を一時追加(複数可。`re:` プレフィックスも可) |
| `--names-file FILE` | リストファイルを差し替え |
| `--pad N` | モザイク領域の余白 px(既定 3) |
| `--backend B` | `auto` / `vision` / `tesseract` / `easyocr` |
| `--no-fuzzy` | あいまい一致を無効化(既定は有効) |
| `--in-place` | 元ファイルを上書き(通常は不要) |
| `--upscale-threshold N` | 長辺がこの px 未満の画像は OCR 前に自動拡大(既定 1200。0 で無効) |
| `--upscale-factor F[,F...]` | 自動拡大の倍率。カンマ区切りで複数指定すると全倍率で検出して合算(既定 2,3。1以下のみなら無効) |
| `--version` | バージョンを表示 |

## 🧠 仕組み

1. **OCR** — 画像内の全テキストと座標を取得
   - macOS: **Apple Vision framework**(既定。モデルダウンロード不要・日本語対応・完全ローカル)
   - その他: **Tesseract** → **EasyOCR** の順に自動フォールバック
2. **照合** — 認識テキストをリストと突き合わせ
   - 固定文字列: 小文字化 + `0/O`・`1/l/I` 同一視 + 空白除去
   - **あいまい一致**: 6文字以上のエントリは編集距離1〜2までの近似一致も許容
   - 正規表現: 元テキストと空白除去テキストの両方に適用(トークン分断対策)
3. **モザイク** — 一致した部分文字列の矩形だけをピクセル化(縮小→ニアレスト拡大の不可逆処理)

Vision バックエンドでは部分文字列の正確な矩形を API から取得し、その他の
バックエンドでは単語ボックスから文字位置比で近似します。

### あいまい一致(既定 ON)

混同表で吸収できるのは既知の誤読だけですが、実際の OCR はもっと自由に
間違えます。たとえばターミナルのスラッシュ付きゼロが `@` と読まれて
`zephel01` が `zephel@1` になると、混同表では一致しません。そこで正規化後
6文字以上のエントリについては編集距離1〜2までの近似一致も拾います
(12文字以下なら1、それより長ければ2)。短いエントリは誤爆しやすいので対象外です。

まれに余計な箇所がモザイクされることがありますが、隠し忘れよりは安全側です。
厳密な一致だけにしたいときは `--no-fuzzy` を付けてください。

### 低解像度スクリーンショットの自動拡大

非 Retina などの小さいスクショは文字が潰れて OCR が取りこぼしやすいため、
長辺が 1200px 未満の画像は OCR にかける直前だけ拡大しています。同じ画像内
でも倍率によって読み取れる箇所にばらつきが出ることがあるため、既定では
2倍・3倍の両方で OCR して検出結果を合算します。実際にモザイクをかける
画像は常に元の解像度のままです。

横長なのに文字だけが小さい画像(例: 1463×440 のターミナルスクショ)は既定の
しきい値を超えるため拡大されません。取りこぼすようなら
`--upscale-threshold 2000` のように上げてください。

## 🔄 更新

```bash
git pull
uv sync                 # uv.lock どおりに揃える(通常はこれだけ)
uv sync --upgrade       # 依存そのものを新しいバージョンに上げる(uv.lock も更新)
```

`uv sync --upgrade` で `uv.lock` が変わったら、動作確認のうえコミットしてください。

## 🧪 テスト

照合ロジック(取りこぼし・誤爆)のテストが入っています。

```bash
uv run pytest
```

## ⚠️ 注意

- OCR ベースのため、極端に小さい文字・低コントラスト・装飾フォントは
  取りこぼすことがあります。自動拡大とあいまい一致はこれを軽減しますが
  完全ではないため、**公開前に `--list` と目視での最終確認を推奨**
- モザイクは不可逆ですが、巨大な文字に薄くかかった場合の復元耐性までは
  保証しません。不安なら `--pad` を増やしてください
- 対応画像形式: PNG / JPEG / WebP / TIFF / BMP(HEIC は `pillow-heif` 追加で対応可)

## セットアップを手動でやる場合

```bash
uv sync                                   # .venv 作成 + 依存を uv.lock どおりに
cp mosaic-names.example.txt mosaic-names.txt
uv run mosaic-names --help
```

任意のバックエンドを足す場合:

```bash
uv sync --extra tesseract   # 別途 brew install tesseract tesseract-lang
uv sync --extra easyocr     # torch 込みで重い。初回にモデルをダウンロードする
```

uv を使わず素の venv でも動きます(依存バージョンは固定されません):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install "pillow>=10.0" pyobjc-framework-Vision pyobjc-framework-Quartz
python3 mosaic_names.py --help
```
