"""スモークテスト: エージェントが合法手を返し、1試合完走できることを確認。

実行: .venv/bin/python -m pytest tests/ -q
（kaggle-environments が必要）
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _deck():
    from kuroko_ai.config import Config
    from kuroko_ai.decklist import load_deck

    cfg = Config.load(os.path.join(ROOT, "config"))
    return load_deck(os.path.join(ROOT, "deck.csv"), cfg.deck)


def test_deck_is_60_cards():
    assert len(_deck()) == 60


def test_deck_request_returns_deck():
    from kuroko_ai import KurokoAgent

    agent = KurokoAgent(base_dir=ROOT)
    out = agent.act({"select": None, "current": None})
    assert isinstance(out, list) and len(out) == 60


def test_main_entrypoint_importable():
    import main  # noqa: F401

    assert callable(main.agent)


def test_plays_full_game_legally():
    import logging

    logging.disable(logging.WARNING)
    from kaggle_environments import make

    from kuroko_ai import KurokoAgent

    deck = _deck()
    agent = KurokoAgent(base_dir=ROOT)

    def fn(obs):
        return agent.act(obs if isinstance(obs, dict) else dict(obs))

    env = make("cabt", configuration={"decks": [deck, deck]})
    env.run([fn, "first"])
    # 完走し、結果（勝敗どちらか）が確定していること
    last = env.steps[-1][0]
    assert last["status"] == "DONE"
    assert last["reward"] in (-1, 0, 1)
    # INVALID（不正手）で終わっていないこと
    assert last.get("reward") is not None


if __name__ == "__main__":
    test_deck_is_60_cards()
    test_deck_request_returns_deck()
    test_main_entrypoint_importable()
    test_plays_full_game_legally()
    print("smoke tests passed")
