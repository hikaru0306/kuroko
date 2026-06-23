"""ローカル自己対戦ランナー（cabt SDK 使用）。

使い方:
    python tools/run_match.py                 # Kuroko vs first(ベースライン) を1戦
    python tools/run_match.py --games 20       # 20戦して勝率を表示
    python tools/run_match.py --opp random     # 相手を random に
    python tools/run_match.py --self           # Kuroko 同士
    python tools/run_match.py --render out.html# 対戦を HTML 可視化で出力

事前に: pip install kaggle-environments
"""

import argparse
import logging
import os
import sys

logging.disable(logging.WARNING)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def build_kuroko_agent():
    """毎ゲーム新しい状態のエージェントを使うためのファクトリ。"""
    from kuroko_ai import KurokoAgent

    inst = KurokoAgent(base_dir=ROOT)

    def _fn(obs):
        return inst.act(obs if isinstance(obs, dict) else dict(obs))

    return _fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=1)
    ap.add_argument("--opp", choices=["first", "random", "kuroko"], default="first")
    ap.add_argument("--self", action="store_true", help="Kuroko 同士で対戦")
    ap.add_argument("--render", type=str, default="")
    args = ap.parse_args()

    from kaggle_environments import make
    from kuroko_ai.decklist import load_deck
    from kuroko_ai.config import Config

    cfg = Config.load(os.path.join(ROOT, "config"))
    deck = load_deck(os.path.join(ROOT, "deck.csv"), cfg.deck)
    assert len(deck) == 60, f"デッキは60枚必要です（現在 {len(deck)} 枚）"

    opp_name = "kuroko" if args.self else args.opp

    wins = draws = losses = 0
    for g in range(args.games):
        env = make("cabt", configuration={"decks": [deck, deck]})
        p0 = build_kuroko_agent()
        p1 = build_kuroko_agent() if opp_name == "kuroko" else opp_name
        env.run([p0, p1])
        r = env.steps[-1][0]["reward"]
        if r == 1:
            wins += 1
        elif r == -1:
            losses += 1
        else:
            draws += 1
        if args.render and g == 0:
            with open(args.render, "w", encoding="utf-8") as f:
                f.write(env.render(mode="html"))
            print(f"可視化を書き出しました: {args.render}")

    n = args.games
    print(f"Kuroko vs {opp_name}: {n}戦  勝 {wins} / 分 {draws} / 負 {losses}"
          f"  （勝率 {wins / n:.1%}）")


if __name__ == "__main__":
    main()
