"""読み合い（相手モデリング / yomiai）。設定は config/reads.yaml。

相手の手札・山札・サイドは非公開なので、ここでは
  1) アーキタイプの事前分布（reads.yaml の archetype_prior）
  2) 試合中の観測（ベンチ枚数・与えてくるダメージ等）による事後更新
を保持し、ポリシーへ「補正のヒント」を返す。

このモジュールはターンをまたいで状態を持つ（OpponentModel は agent が保持）。
"""

from __future__ import annotations

from .state import GameState


class OpponentModel:
    def __init__(self, reads_cfg: dict):
        self.cfg = reads_cfg
        self.belief = dict(reads_cfg.get("archetype_prior", {}))
        self._normalize()
        self.observed_max_damage = 0
        self.seen_card_ids: set[int] = set()

    def _normalize(self):
        total = sum(self.belief.values()) or 1.0
        for k in self.belief:
            self.belief[k] /= total

    # ターン開始ごとに観測を取り込む
    def update(self, state: GameState) -> None:
        opp = state.opp
        for c in opp.active + opp.bench + opp.discard:
            self.seen_card_ids.add(c.id)
        # 直近ログから相手の与ダメージを拾う（log type16: value, putDamageCounter）
        for lg in state.logs:
            if lg.get("type") == 16 and lg.get("playerIndex") == (1 - state.your_index):
                self.observed_max_damage = max(
                    self.observed_max_damage, int(lg.get("value", 0))
                )
        # ベンチが薄い → アグロ寄りへ事後を寄せる（簡易ベイズ風）
        low = self.cfg.get("low_bench_threshold", 1)
        if len(opp.bench) <= low and state.turn >= 2:
            self._nudge("aggro", 0.05)

    def _nudge(self, key: str, amount: float) -> None:
        if key not in self.belief:
            return
        self.belief[key] = min(1.0, self.belief[key] + amount)
        self._normalize()

    # ---- ポリシーへのヒント ----------------------------------------------
    @property
    def aggro_weight(self) -> float:
        return self.belief.get("aggro", 0.0)

    def desired_hp_buffer(self) -> int:
        """相手の打点を考慮し、自アクティブに残しておきたいHP目安。"""
        base = int(self.cfg.get("hp_buffer_vs_aggro", 30))
        # 観測した最大打点と事前分布のアグロ度合いを反映
        return int(max(self.observed_max_damage, base * self.aggro_weight))

    def summary(self) -> str:
        b = ", ".join(f"{k}:{v:.2f}" for k, v in self.belief.items())
        return f"belief[{b}] maxdmg={self.observed_max_damage}"
