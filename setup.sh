#!/usr/bin/env bash
# mosaic-names セットアップスクリプト。何度実行しても安全(冪等)。
#   ./setup.sh
# やること: .venv 作成 → 依存インストール → mosaic-names.txt 初期化(無ければ)
#           → input/ output/ 作成
set -euo pipefail
cd "$(dirname "$0")"

echo "== mosaic-names setup =="

# 1) venv
if [ ! -d .venv ]; then
  echo "-- .venv を作成"
  python3 -m venv .venv
else
  echo "-- .venv は作成済み"
fi

# 2) 依存
echo "-- 依存をインストール (requirements.txt)"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# 3) 隠す文字列リスト(実ファイルが無ければサンプルから作る。上書きはしない)
if [ ! -f mosaic-names.txt ]; then
  cp mosaic-names.example.txt mosaic-names.txt
  echo "-- mosaic-names.txt をサンプルから作成しました。自分の名前等に書き換えてください"
else
  echo "-- mosaic-names.txt は作成済み(変更しません)"
fi

# 4) 入出力フォルダ
mkdir -p input output
echo "-- input/ output/ を用意"

echo ""
echo "セットアップ完了。使い方:"
echo "  1. mosaic-names.txt を自分の隠したい文字列に編集"
echo "  2. input/ にスクリーンショットを置く"
echo "  3. ./mosaic          # input/ -> output/ に一括処理"
echo "     ./mosaic --list   # 検出確認だけ(書き込みなし)"
