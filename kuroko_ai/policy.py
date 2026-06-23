"""意思決定ポリシー。

GamePlan（理想ムーブ）・Evaluator（盤面評価）・OpponentModel（読み合い）を
束ね、Decision の種類ごとに最適な Option を選ぶ。先読みはせず、選択肢のメタ情報と
現盤面に対するヒューリスティック点数化で決める。

返すのは「選んだ Option のリスト」。件数は必ず min_count..max_count に収める。
"""

from __future__ import annotations

from .cards import CardDB
from .evaluation import Evaluator
from .lines import GamePlan
from .reads import OpponentModel
from .state import Decision, GameState, Option, OptionType, SelectType


class Policy:
    def __init__(
        self,
        plan: GamePlan,
        evaluator: Evaluator,
        opp_model: OpponentModel,
        card_db: CardDB,
        strategy_cfg: dict,
    ):
        self.plan = plan
        self.eval = evaluator
        self.opp = opp_model
        self.cards = card_db
        self.cfg = strategy_cfg

    # 公開API: 1 意思決定を解く -------------------------------------------
    def decide(self, state: GameState, decision: Decision) -> list[Option]:
        if not decision.options:
            return []
        handler = {
            SelectType.ACTION_MENU: self._action_menu,
            SelectType.TARGET: self._target,
            SelectType.ENERGY: self._energy,
            SelectType.PICK_N: self._pick_n,
            SelectType.NUMBER: self._number,
            SelectType.YES_NO: self._yes_no,
        }.get(decision.type, self._default)
        chosen = handler(state, decision)
        return self._enforce_counts(chosen, decision)

    # ---- ハンドラ -------------------------------------------------------
    def _action_menu(self, state: GameState, d: Decision) -> list[Option]:
        """行動メニュー（1つ選ぶ）。

        モード:
          "engine_order"（既定/推奨）:
              cabt エンジンは選択肢を「展開→攻撃→終了」の良い順で並べてくれるため、
              基本は先頭(index 0)を信頼する。その上で『確実にKOできるワザ』があれば
              それを優先する、という最小限の賢い上書きだけを行う。
          "priority":
              strategy.yaml の action_priority + evaluation で完全に並べ替える。
              （実験用。カードDBを正しく整備するとこちらが伸びる余地がある）
        """
        mode = self.cfg.get("action_menu_mode", "engine_order")
        if mode == "priority":
            best, best_val = None, float("-inf")
            for opt in d.options:
                val = self._action_value(opt, state, d)
                if val > best_val:
                    best, best_val = opt, val
            return [best] if best is not None else [d.options[0]]

        # engine_order: 基本はエンジン順の先頭(index 0)を信頼する。
        # ただし「何をするか」の順序はエンジンに従いつつ、以下の局面では
        # 「対象/ワザの選び方」だけを最適化する。
        head = d.options[0]

        # (1) 攻撃局面: ワザ選択を効率スコアで最適化（KO/副作用込み）
        if self.cfg.get("enable_ko_override", False):
            attacks = [o for o in d.options if o.type == OptionType.ATTACK]
            head_is_attack = head.type == OptionType.ATTACK
            if attacks and (head_is_attack or self._find_ko_attack(state, d) is not None):
                return [self._best_attack(state, attacks)]

        # (2) エネ付け局面: エンジンが「今エネを付ける」と判断したら(先頭がエネ付け)、
        #     付け先をメインアタッカー/アクティブへ集中させる。
        if self.cfg.get("concentrate_energy", True) and head.type == OptionType.ATTACH_ENERGY:
            attaches = [o for o in d.options if o.type == OptionType.ATTACH_ENERGY]
            return [self._best_energy_target(state, attaches)]

        return [head]

    def _best_energy_target(self, state: GameState, attaches: list[Option]) -> Option:
        """エネの付け先を選ぶ。メインアタッカー > アクティブ > その他。

        理想のムーブ「エネはアタッカーに集中」を表現。付け先は option の
        inPlayArea/inPlayIndex（自分の場）で示される。同点はエンジン順を維持。
        """
        def score(o: Option) -> float:
            cid = self._inplay_card_id(o, state, state.your_index)
            s = 0.0
            if cid is not None:
                role = self.cards.role_of(cid)
                if role == "main_attacker":
                    s += 100.0
                elif role == "sub_attacker":
                    s += 50.0
            if o.in_play_area == 1:   # アクティブ（多くの場合の攻撃役）
                s += 20.0
            return s

        best = attaches[0]
        best_s = score(best)
        for o in attaches[1:]:
            s = score(o)
            if s > best_s:
                best, best_s = o, s
        return best

    def _best_attack(self, state: GameState, attacks: list[Option]) -> Option:
        """ワザ選択。最大打点ではなく『効率スコア』で選ぶ。

        効率スコアは副作用込み（反動・エネ加速/捨て・ベンチ打点・次攻撃不可など）。
        KOできるワザ同士でも、反動やエネ捨ての少ない＝後に響かない方を選ぶ。
        詳細は evaluation.Evaluator.attack_score。
        """
        opp_active = state.opp.active
        target_id = opp_active[0].id if opp_active else None
        return max(attacks, key=lambda o: self.eval.attack_score(o.attack_id, target_id))

    def _find_ko_attack(self, state: GameState, d: Decision):
        """相手アクティブを確実に倒せるワザ option を返す（無ければ None）。"""
        opp_active = state.opp.active
        if not opp_active:
            return None
        target_id = opp_active[0].id
        for opt in d.options:
            if opt.type == OptionType.ATTACK and opt.attack_id is not None:
                if self.eval.does_ko(opt.attack_id, target_id):
                    return opt
        return None

    def _action_value(self, opt: Option, state: GameState, d: Decision) -> float:
        base = self.plan.action_base_priority(opt, state, d)
        if opt.type == OptionType.ATTACK:
            return base + self._attack_bonus(opt, state)
        if opt.type == OptionType.ATTACH_ENERGY:
            return base + self._attach_target_bonus(opt, state)
        if opt.type == OptionType.END_TURN:
            return base  # 0 が基準。他に良い手が無ければ終了する
        return base

    def _attach_target_bonus(self, opt: Option, state: GameState) -> float:
        """エネを誰に付けるか。メインアタッカー > アクティブ > その他、で加点。

        理想のムーブ「エネはメインアタッカーへ集中」を表現する。
        付け先は option の inPlayArea/inPlayIndex（自分の場）で示される。
        """
        cid = self._inplay_card_id(opt, state, state.your_index)
        w = self.cfg.get("attach_bonus", {})
        bonus = 0.0
        if cid is not None and self.cards.role_of(cid) == "main_attacker":
            bonus += float(w.get("main_attacker", 0.0))
        if opt.in_play_area == 1:   # アクティブ（攻撃役）
            bonus += float(w.get("active", 0.0))
        return bonus

    def _attack_bonus(self, opt: Option, state: GameState) -> float:
        w = self.eval.w
        dmg = self.eval.attack_damage(opt.attack_id) if opt.attack_id is not None else None
        # 打点が不明（カードDB未登録）の場合: エンジンが提示している=合法な攻撃なので
        # 「そこそこ有効」とみなして攻撃を選ばせる。0 とは決して混同しない。
        if dmg is None:
            return float(w.get("unknown_attack_value", 30.0))
        if dmg <= 0:
            return -100.0  # 打点が明確に0のワザは終了より下げる
        bonus = w["damage_dealt"] * dmg
        opp_active = state.opp.active
        if opp_active and self.eval.does_ko(opt.attack_id, opp_active[0].id):
            bonus += w["ko_opponent"]
        return bonus

    def _target(self, state: GameState, d: Decision) -> list[Option]:
        """対象選択。

        攻撃的文脈（ダメージを振り分ける等で相手側を選べる）なら『倒せる/厄介な相手』を
        優先。それ以外（自分の進化先・配置など）はエンジン順(index 0)を信頼する。
        """
        opp_idx = 1 - state.your_index
        ctx_dmg = d.remain_damage_counter
        opp_options = [o for o in d.options if o.player_index == opp_idx]

        # 攻撃的文脈でなければエンジン順をそのまま使う
        if not opp_options:
            return list(d.options)

        def score(o: Option) -> float:
            if o.player_index != opp_idx:
                return -1.0
            s = 50.0
            cid = self._card_id_for_target(o, state, opp_idx)
            if cid is not None:
                hp = self.eval.ko_damage_needed(cid)
                if ctx_dmg and ctx_dmg >= hp:
                    s += float(self.eval.w["ko_opponent"])  # 倒せる相手を最優先
                else:
                    s += 0.1 * hp                            # 高HP=厄介を優先
            return s

        return sorted(d.options, key=score, reverse=True)

    def _energy(self, state: GameState, d: Decision) -> list[Option]:
        # メインアタッカー(role=main_attacker)へ優先して付ける
        def score(o: Option) -> float:
            cid = self._card_id_for_target(o, state, state.your_index)
            role = self.cards.role_of(cid) if cid is not None else ""
            s = 0.0
            if role == "main_attacker":
                s += 100.0
            elif role == "sub_attacker":
                s += 50.0
            # アクティブ(area=1)を気持ち優先
            if o.area == 1:
                s += 5.0
            return s

        return sorted(d.options, key=score, reverse=True)

    def _pick_n(self, state: GameState, d: Decision) -> list[Option]:
        # N 枚選ぶ系。トラッシュ要求とみなし、価値の低いカードから差し出す。
        def keep_value(o: Option) -> float:
            cid = self._hand_card_id(o, state)
            if cid is None:
                return 0.0
            card = self.cards.get(cid)
            v = 0.0
            if card.role in ("main_attacker", "sub_attacker"):
                v += 100
            if card.is_basic:
                v += 30
            if card.is_energy:
                v += 5
            return v

        # keep_value が低い順 = 手放してよい順
        return sorted(d.options, key=keep_value)

    def _number(self, state: GameState, d: Decision) -> list[Option]:
        # 数値選択は基本「最大」を選ぶ（多く引く/多く探す等が有利なことが多い）
        return sorted(d.options, key=lambda o: (o.number or 0), reverse=True)

    def _yes_no(self, state: GameState, d: Decision) -> list[Option]:
        want_yes = bool(self.cfg.get("default_yes", True))
        yes = [o for o in d.options if o.type == OptionType.YES]
        no = [o for o in d.options if o.type == OptionType.NO]
        if want_yes and yes:
            return yes + no
        if not want_yes and no:
            return no + yes
        return d.options

    def _default(self, state: GameState, d: Decision) -> list[Option]:
        return list(d.options)

    # ---- 件数の調整 -----------------------------------------------------
    def _enforce_counts(self, ordered: list[Option], d: Decision) -> list[Option]:
        """min_count..max_count に必ず収める。

        - lo(=minCount) 件は必須。
        - 任意選択(min=0)でも、行動メニュー等は最低 1 件選ぶ必要があるため、
          上限が許す限り 1 件は選ぶ。
        - それ以外は「必要最小限だけ選ぶ」= lo 件（無駄に多く選ばない）。
        """
        if not ordered:
            return []
        n = len(ordered)
        lo = max(0, min(d.min_count, n))
        hi = d.max_count if d.max_count > 0 else lo
        hi = min(hi, n)
        count = lo
        if count == 0:
            count = 1 if hi >= 1 else 0   # 最低1件選ぶ必要がある選択への保険
        count = min(count, hi) if hi > 0 else count
        return ordered[:count]

    # ---- カードid解決ヘルパ ---------------------------------------------
    def _hand_card_id(self, o: Option, state: GameState):
        hand = state.me.hand
        if hand is None or o.target_index is None:
            return None
        if 0 <= o.target_index < len(hand):
            return hand[o.target_index].id
        return None

    def _inplay_card_id(self, o: Option, state: GameState, player_index: int):
        """option の inPlayArea/inPlayIndex から自分の場のカードidを引く。"""
        p = state.players[player_index] if 0 <= player_index < len(state.players) else None
        if p is None or o.in_play_index is None:
            return None
        pool = p.active if o.in_play_area == 1 else p.bench if o.in_play_area == 4 else None
        if pool is None:
            return None
        if 0 <= o.in_play_index < len(pool):
            return pool[o.in_play_index].id
        return None

    def _card_id_for_target(self, o: Option, state: GameState, player_index: int):
        """target系optionの area/index から場のカードidを引く。"""
        if o.target_index is None:
            return None
        p = state.players[player_index] if 0 <= player_index < len(state.players) else None
        if p is None:
            return None
        area = o.area
        pool = None
        if area == 1:        # ACTIVE
            pool = p.active
        elif area == 4:      # BENCH
            pool = p.bench
        elif area == 2:      # HAND
            pool = p.hand or []
        if pool is None:
            return None
        if 0 <= o.target_index < len(pool):
            return pool[o.target_index].id
        return None
