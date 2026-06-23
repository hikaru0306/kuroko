"""盤面評価（チューニング用の重みは config/evaluation.yaml）。

このモジュールは「状態 → スカラー評価値（自分視点、高いほど良い）」と、
ポリシーが個々の選択肢を点数化する際に使う部品（KO判定・ダメージ見積り）を提供する。

注意: cabt エンジンはブラックボックスで「この行動をしたら盤面がこうなる」を
安全に試打ちできない（battle_ptr がグローバル singleton）。そのため評価は
現在の盤面と選択肢のメタ情報に基づくヒューリスティックで行う（先読み無し）。
"""

from __future__ import annotations

from .cards import CardDB
from .state import GameState, PlayerState


class Evaluator:
    def __init__(self, weights: dict, card_db: CardDB, default_hp: int = 120):
        self.w = weights
        self.cards = card_db
        self.default_hp = default_hp

    # ---- 盤面全体の評価 -------------------------------------------------
    def evaluate(self, state: GameState) -> float:
        me, opp = state.me, state.opp
        w = self.w
        score = 0.0
        # サイド差（取った枚数 = 残りが少ないほど良い。6枚スタート想定）
        my_prize_taken = max(0, 6 - len(me.prize))
        opp_prize_taken = max(0, 6 - len(opp.prize))
        score += w["prize_taken"] * (my_prize_taken - opp_prize_taken)
        # 場の充実度
        score += w["bench_pokemon"] * len(me.bench)
        score -= w["bench_pokemon"] * 0.5 * len(opp.bench)
        # 手札
        score += w["hand_size"] * me.hand_count
        # アクティブの残HP（おおよそ）
        score += w["active_hp_remaining"] * self._active_hp(me)
        score -= w["active_hp_remaining"] * self._active_hp(opp)
        # メインアタッカーのエネ（serial数では測れないので場の枚数で近似）
        score += w["energy_on_attacker"] * self._energy_proxy(me)
        return score

    # ---- 部品 -----------------------------------------------------------
    def _active_hp(self, p: PlayerState) -> int:
        if not p.active:
            return 0
        return sum(self.cards.hp_of(c.id) for c in p.active)

    def _energy_proxy(self, p: PlayerState) -> int:
        # observation からエネ枚数を厳密に取れない場合の近似値。
        # 実SDKで active のエネ配列が見えるなら engine_io 側で拾って差し替える。
        return 0

    def ko_damage_needed(self, target_card_id: int) -> int:
        return self.cards.hp_of(target_card_id)

    def attack_damage(self, attack_id: int):
        """ワザの打点。DB未登録なら None（=不明）を返す。

        重要: 不明を 0 と混同しないこと。0 と誤認すると「攻撃は無価値」と判断して
        一切攻撃しなくなる（= サイドを取れず必敗）。不明時は policy 側で
        『そこそこ有効』とみなす。
        """
        a = self.cards.attack_by_id(attack_id)
        return a.damage if a else None

    def does_ko(self, attack_id: int, target_card_id: int) -> bool:
        dmg = self.attack_damage(attack_id)
        if dmg is None:
            return False
        return dmg >= self.ko_damage_needed(target_card_id)
