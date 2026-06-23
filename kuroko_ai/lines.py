"""理想のムーブ（ゲームプラン / ライン）。設定は config/strategy.yaml。

「序盤は展開、エネが揃ったら殴る」といった“やりたい順番”を、行動メニュー
(select.type=0) の各選択肢への基本優先度として表現する。盤面に応じて優先度を
動的に上下させる（例: ベンチが揃っていれば put_basic の価値を下げる）。

card の役割(role)は cards.CardDB 経由で参照し、デッキ差し替え時は deck.yaml の
編集だけで挙動が変わるようにしている。
"""

from __future__ import annotations

from .cards import CardDB, CATEGORY_SUPPORTER
from .state import Decision, GameState, Option, OptionType


class GamePlan:
    def __init__(self, strategy_cfg: dict, card_db: CardDB):
        self.cfg = strategy_cfg
        self.cards = card_db
        self.priority = strategy_cfg.get("action_priority", {})

    # ---- ゲームプランの状態判定 ------------------------------------------
    def needs_more_bench(self, state: GameState) -> bool:
        return len(state.me.bench) < int(self.cfg.get("desired_bench_pokemon", 3))

    def attacker_energy_goal(self) -> int:
        return int(self.cfg.get("attacker_energy_goal", 2))

    # ---- 行動メニュー選択肢の“やりたさ” ----------------------------------
    def action_base_priority(
        self, opt: Option, state: GameState, decision: Decision
    ) -> float:
        """行動メニュー(type=0)の 1 選択肢に対する基本優先度を返す。

        attack(13) と end_turn(14) の最終的な価値は policy 側で評価値と合算する。
        ここでは“順番づけ”の土台のみを担う。
        """
        p = self.priority
        t = opt.type

        if t == OptionType.ABILITY:
            return float(p.get("ability", 90))

        if t == OptionType.PLAY_HAND:
            return self._hand_card_priority(opt, state)

        if t == OptionType.EVOLVE:
            # 進化（既存個体の上に重ねる）。アタッカー育成なので攻撃より優先。
            return float(p.get("evolve", 84))

        if t == OptionType.ATTACH_ENERGY:
            # 手札のエネルギーを場へ付ける。攻撃より先に行う最重要手。
            # （メインアタッカーへ付ける選択は policy._action_value 側で更に加点）
            return float(p.get("attach_energy", 80))

        if t == OptionType.RETREAT:
            return float(p.get("retreat", 20))

        if t == OptionType.ATTACK:
            return float(p.get("attack", 50))

        if t == OptionType.END_TURN:
            return float(p.get("end_turn", 0))

        return 10.0  # 未分類の行動は控えめに

    def _hand_card_priority(self, opt: Option, state: GameState) -> float:
        """手札のポケモン/トレーナーを出す/使う(type=7)の優先度。

        type 7 はポケモン（ベンチ展開）とトレーナーズ（サポート/グッズ）の両方を含む。
        カードの category/role で優先度を振り分ける。
        """
        p = self.priority
        card_id = self._hand_card_id_at(opt, state)
        card = self.cards.get(card_id) if card_id is not None else None
        role = card.role if card else ""

        # ドロー/サーチ系サポート → 最優先で手札を増やす
        if role in ("draw", "search") or (card and card.category == CATEGORY_SUPPORTER):
            return float(p.get("draw_supporter", 85))
        # ポケモン → ベンチ展開。ベンチが十分なら価値を下げる
        if card and card.is_pokemon:
            base = float(p.get("put_basic", 78))
            if not self.needs_more_bench(state):
                base -= 40
            return base
        # 不明 or グッズ
        return float(p.get("play_item", 60))

    def _hand_card_id_at(self, opt: Option, state: GameState):
        """option の index から、対応する手札カードidを引く（取れなければ None）。"""
        hand = state.me.hand
        if hand is None or opt.target_index is None:
            return None
        i = opt.target_index
        if 0 <= i < len(hand):
            return hand[i].id
        return None
