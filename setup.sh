#!/usr/bin/env bash
# mosaic-names セットアップスクリプト。何度実行しても安全(冪等)。
#   ./setup.sh
# やること: uv sync(.venv 作成 + uv.lock どおりの依存インストール)
#           → mosaic-names.txt 初期化(無ければ) → input/ output/ 作成
set -euo pipefail
cd "$(dirname "$0")"

echo "== mosaic-names setup =="

# 0) uv
if ! command -v uv >/dev/null 2>&1; then
  cat >&2 <<'MSG'
uv が見つかりません。先にインストールしてください:
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Homebrew なら: brew install uv
MSG
  exit 1
fi

# 1) 依存(.venv は uv が作る。uv.lock があるので毎回同じバージョンが入る)
echo "-- 依存を同期 (uv sync)"
uv sync

# 2) 隠す文字列リスト(実ファイルが無ければサンプルから作る。上書きはしない)
if [ ! -f mosaic-names.txt ]; then
  cp mosaic-names.example.txt mosaic-names.txt
  echo "-- mosaic-names.txt をサンプルから作成しました。自分の名前等に書き換えてください"
else
  echo "-- mosaic-names.txt は作成済み(変更しません)"
fi

# 3) 入出力フォルダ
mkdir -p input output
echo "-- input/ output/ を用意"

echo ""
echo "セットアップ完了。使い方:"
echo "  1. mosaic-names.txt を自分の隠したい文字列に編集"
echo "  2. input/ にスクリーンショットを置く"
echo "  3. ./mosaic          # input/ -> output/ に一括処理"
echo "     ./mosaic --list   # 検出確認だけ(書き込みなし)"
echo ""
echo "依存を最新版に上げたいときは: uv sync --upgrade"
