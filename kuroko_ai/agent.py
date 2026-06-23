"""KurokoAgent: cabt エンジンのエントリポイント本体。

呼び出しごとに observation を受け取り、デッキ提出 or 行動 index を返す。
試合をまたいで持つ状態（相手モデル等）はインスタンスに保持する。

設計の分離（調整しやすさのため）:
  deck.yaml      … デッキ60枚 + カード役割     -> decklist / cards
  strategy.yaml  … 理想のムーブ（優先順位）     -> lines.GamePlan
  evaluation.yaml… 盤面評価の重み               -> evaluation.Evaluator
  reads.yaml     … 読み合い（相手モデル）        -> reads.OpponentModel
"""

from __future__ import annotations

import os

from . import engine_io
from .cards import CardDB
from .config import Config
from .decklist import load_deck
from .evaluation import Evaluator
from .lines import GamePlan
from .policy import Policy
from .reads import OpponentModel
from .state import SelectType


class KurokoAgent:
    def __init__(self, base_dir: str | None = None):
        base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = base_dir
        config_dir = os.path.join(base_dir, "config")

        self.config = Config.load(config_dir)
        self.deck = load_deck(
            csv_path=os.path.join(base_dir, "deck.csv"),
            deck_cfg=self.config.deck,
        )
        default_hp = int(self.config.evaluation.get("default_pokemon_hp", 120))
        self.cards = CardDB.from_config(self.config.deck, default_hp=default_hp)

        self.plan = GamePlan(self.config.strategy, self.cards)
        self.evaluator = Evaluator(
            self.config.evaluation["weights"], self.cards, default_hp=default_hp
        )
        self.opp_model = OpponentModel(self.config.reads)
        self.policy = Policy(
            self.plan, self.evaluator, self.opp_model, self.cards, self.config.strategy
        )

        # ループ安全弁: 同一ターン内で行動メニューが続いた回数
        self._action_menu_streak = 0
        self._last_turn = -1
        # 1ターンで許す行動メニュー連続回数の上限（超えたら強制終了）
        self._action_menu_cap = 60

    # ---- エントリポイント ------------------------------------------------
    def act(self, obs: dict) -> list[int]:
        # 1) デッキ提出
        if engine_io.is_deck_request(obs):
            return self.deck

        state, decision = engine_io.parse_observation(obs)

        # 2) 対戦終了 or 意思決定不要
        if decision is None or not decision.options:
            return self.deck if state is None else []

        # 3) ターンが変わったら相手モデルを更新
        if state is not None and state.turn != self._last_turn:
            self._last_turn = state.turn
            self._action_menu_streak = 0
            self.opp_model.update(state)

        # 4) ループ安全弁: 行動メニューが続きすぎたら終了を選ぶ
        if decision.type == SelectType.ACTION_MENU:
            self._action_menu_streak += 1
            if self._action_menu_streak > self._action_menu_cap:
                end = self._find_end_turn(decision)
                if end is not None:
                    return [end]
        else:
            self._action_menu_streak = 0

        # 5) ポリシーで決定
        chosen = self.policy.decide(state, decision)
        action = engine_io.encode_action(decision, chosen)

        # 6) 念のためのフォールバック（空 = 不正手で負け）
        if not action:
            action = self._fallback(decision)
        return action

    # ---- 補助 -----------------------------------------------------------
    def _find_end_turn(self, decision):
        from .state import OptionType

        for o in decision.options:
            if o.type == OptionType.END_TURN:
                return o.index
        return None

    def _fallback(self, decision) -> list[int]:
        lo = max(0, decision.min_count)
        if lo == 0:
            lo = 1
        lo = min(lo, len(decision.options))
        return list(range(lo))
