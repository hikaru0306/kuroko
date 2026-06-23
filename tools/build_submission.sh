#!/usr/bin/env bash
# Kaggle 提出用 submission.tar.gz を作る。
# main.py を最上位に、kuroko_ai/ と config/ と deck.csv を同梱する。
set -euo pipefail

cd "$(dirname "$0")/.."

OUT="submission.tar.gz"

# 提出に含めるもの（main.py は必ず最上位）。--exclude はファイル指定より前に置く。
tar --exclude='__pycache__' --exclude='*.pyc' -czvf "$OUT" \
  main.py \
  deck.csv \
  kuroko_ai \
  config

echo ""
echo "作成: $OUT"
echo "中身（main.py が最上位にあることを確認）:"
tar -tzf "$OUT" | head -20
