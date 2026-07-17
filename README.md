# mosaic-names

スクリーンショット内の**指定した文字列だけ**を OCR で見つけてモザイクをかける単体スクリプト。
note 記事などにスクショを載せる前に、ユーザー名・本名・メールアドレスを自動で塗りつぶす用途。

## セットアップ

```bash
./setup.sh
```

これだけ。venv 作成 → 依存インストール → `mosaic-names.txt` 初期化(無ければ
サンプルからコピー) → `input/` `output/` 作成、まで全部やる。何度実行しても
安全(既存の `mosaic-names.txt` は上書きしない)。

以降の実行は venv を意識せずラッパーで:

```bash
./mosaic            # input/ -> output/ に一括処理
./mosaic --list     # 検出確認だけ(書き込みなし)
```

手動でやりたい場合は従来どおり:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

macOS 標準の Vision framework を使うので、OCR モデルのダウンロードは不要。日本語も読める。
(Vision が使えない環境では `brew install tesseract tesseract-lang` + `pip3 install pytesseract`、
または EasyOCR にも自動フォールバックする)

## 使い方

初回はサンプルをコピーして、自分の隠したい文字列に書き換える:

```bash
cp mosaic-names.example.txt mosaic-names.txt
```

`mosaic-names.txt` は個人情報そのものなので git にはコミットしない(.gitignore 済み)。
共有・公開するのはサンプルの方。

```bash
# 隠す文字列は mosaic-names.txt(このフォルダ)を編集
python3 mosaic_names.py screenshot.png            # -> screenshot.masked.png
python3 mosaic_names.py *.png --list              # 検出位置の確認だけ(書き込みなし)
python3 mosaic_names.py img.png -n "追加の名前"    # リストに一時追加
python3 mosaic_names.py img.png --in-place        # 元ファイルを上書き
python3 mosaic_names.py img.png --pad 6           # モザイクの余白を広げる
```

### 標準ワークフロー: input/ → output/

**引数なしで実行すると `input/` の画像を名前順に処理して `output/` に書き出す。**
入力フォルダのファイルには一切書き込まない(原本はそのまま残る)。

```bash
mkdir -p input          # 初回のみ。ここにスクショを置く
python3 mosaic_names.py            # input/ -> output/ に一括処理
python3 mosaic_names.py --list     # まとめて検出確認だけ(書き込みなし)
python3 mosaic_names.py --skip-existing  # 中断からの再開(処理済みを飛ばす)
```

検出ゼロの画像もそのままコピーされるので、`output/` が「そのまま公開できる
完全なセット」になる。進捗は `[n/総数]` で表示される。

### 任意のフォルダ/ファイルの一括処理

ディレクトリを渡すと直下の画像(png/jpg/webp 等)を名前順に処理する。
`*.masked.*` は自動で除外されるので、同じフォルダに出力しても二重処理しない。

```bash
python3 mosaic_names.py photo/                    # photo/ 内を順に -> 各 .masked.png
python3 mosaic_names.py photo/ --out-dir publish  # 出力を publish/ に元ファイル名で集約
```

## 正規表現(メールアドレス・APIキーなど)

`mosaic-names.txt` の `re:` で始まる行は正規表現(大文字小文字無視)として扱われる。
既定で次の2つが入っている:

```
# メールアドレス全般
re:[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}

# API キー類: sk- で始まるトークン(OpenAI sk-... / Anthropic sk-ant-... など)
re:\bsk-[a-z0-9_-]{8,}
```

他のトークン形式も同じ要領で足せる(例: GitHub なら `re:\bghp_[a-z0-9]{20,}`、
Slack なら `re:\bxox[bpars]-[a-z0-9-]{10,}`)。正規表現は元テキストと
「空白を除去したテキスト」の両方に当てるので、OCR がトークンの途中に
空白を挟んでも検出できる(実測: `sk-proj -Abc...` と誤読されても検出)。

## 特徴

- 汎用の個人情報検出はしない。隠す対象は `mosaic-names.txt` で自分が決める(1行1エントリ)
- OCR の誤読に耐性あり: `0/O`・`1/l/I` の混同と空白の誤挿入を無視して照合
  (実測: tesseract が `zephel01` を `zephelOl` と誤読しても検出できる)
- 大文字小文字は区別しない。行の中の部分一致でも、その部分だけをモザイク化
- 既定では元ファイルを変更せず `<名前>.masked.png` を出力

## 注意

- OCR ベースなので、極端に小さい文字・低コントラスト・装飾フォントは拾えないことがある。
  公開前に `--list` で検出結果を確認し、最後は目視でダブルチェックを推奨
- モザイクは不可逆(ダウンサンプル→ニアレスト拡大)だが、極端に大きい文字に薄いモザイクが
  かかった場合の復元耐性は保証しない。心配なら `--pad` を増やす
