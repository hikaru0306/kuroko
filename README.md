# Kuroko — ポケモンカードゲーム AI Battle Challenge (cabt) エージェント

[Pokémon Trading Card Game AI Battle Challenge](https://ptcg-abc.pokemon.co.jp/)
（Kaggle / cabt エンジン）向けの対戦AIエージェント。

**設計方針: 調整しやすいように、要素ごとにファイルと設定を分離。**

| 要素 | 設定ファイル（編集対象） | ロジック |
|------|------------------------|----------|
| デッキ + カード知識 | `config/deck.yaml`, `deck.csv` | `kuroko_ai/decklist.py`, `cards.py` |
| 理想のムーブ（ゲームプラン） | `config/strategy.yaml` | `kuroko_ai/lines.py` |
| 盤面評価（重み） | `config/evaluation.yaml` | `kuroko_ai/evaluation.py` |
| 読み合い（相手モデル） | `config/reads.yaml` | `kuroko_ai/reads.py` |

設定は YAML を編集するだけで挙動が変わる（コード変更不要）。
YAML が無い/PyYAML が無い環境でも `kuroko_ai/config.py` の `DEFAULTS` で動く。

## 現在の強さ（ローカル自己対戦・各80〜120戦）

| 対戦相手 | 勝率 |
|----------|------|
| `random`（ランダム） | **約 83%** |
| `first`（エンジン同梱の強baseline。randomに87%勝つ） | **約 60%**（同席条件） |

> cabt エンジンは選択肢を「展開→エネ→進化→攻撃→終了」の良い順に並べてくれる。
> 現状の主戦略 `action_menu_mode: engine_order` はこの順序を信頼し、無駄な
> 並べ替えをしないことで強さを出している。詳しくは `docs/ARCHITECTURE.md`。

## 使い方

```bash
# 1) 依存をいれる（ローカル検証用）
python3 -m venv .venv && .venv/bin/pip install kaggle-environments pyyaml

# 2) 自己対戦で強さを測る
.venv/bin/python tools/run_match.py --games 80 --opp first
.venv/bin/python tools/run_match.py --games 80 --opp random
.venv/bin/python tools/run_match.py --self --render out.html   # 対戦をHTML可視化

# 3) スモークテスト
.venv/bin/python -m pytest tests/ -q     # または: .venv/bin/python tests/test_agent_smoke.py

# 4) 提出物 submission.tar.gz を作る（main.py を最上位に同梱）
bash tools/build_submission.sh
```

`submission.tar.gz` を Kaggle のシミュレーション部門にアップロードする。

## 調整のしかた（例）

- **デッキを変える**: `deck.csv` の `id,枚数` を編集（合計60枚厳守）。
- **カードの意味を教える**: `config/deck.yaml` の `cards:` に HP・ワザ・役割を記入。
  → 正確にするほど評価・KO判断・エネ集中が機能する。
- **ムーブの優先順位を変える**: `config/strategy.yaml`。
  実験的に完全自前ロジックを使うなら `action_menu_mode: priority` に。
- **評価の重み**: `config/evaluation.yaml`。
- **相手想定**: `config/reads.yaml`。

## 重要な注意

`config/deck.yaml` のカード定義（名前/HP/ワザ打点/役割）は**self-playで出現した
idに対する仮置き**です。公式の「指定カードリスト」を見て正しい値に直すことで、
`enable_ko_override` や評価ベースの戦略が活きてきます。
