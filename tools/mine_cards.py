"""カードデータ自動マイナー。

公式カードリストはKaggleログインが必要で直接は取れないため、cabt エンジンの
自己対戦ログから「分かる範囲のカード情報」を実測抽出する補助ツール。

抽出するもの:
  - cardId -> 使用するワザ(attackId) と その観測打点（最頻値）   … log type15/16
  - cardId のカテゴリ推定（エネ/ポケモン/トレーナー）            … log type6/11/15
  - cardId のHP推定（気絶までの累計ダメージから）               … log type6(→トラッシュ)/16
  - 進化ライン（evolves_from）の手掛かり                         … log type12

使い方:
    python tools/mine_cards.py --games 60 --out config/deck.auto.yaml

出力 YAML はあくまで“実測の下書き”。公式カードリストで必ず検証・補正すること。
特に打点/HPの絶対値とスケール、特殊エネルギーの扱いは要確認。
"""

import argparse
import collections
import logging
import os
import statistics
import sys

logging.disable(logging.WARNING)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# log type の意味（self-play 実測）
LOG_DRAW = 4
LOG_MOVE = 6          # {cardId, fromArea, toArea}
LOG_ENERGY = 11       # {cardId(=エネ), cardIdTarget(=付け先)}
LOG_EVOLVE = 12       # {cardId, cardIdTarget}
LOG_ATTACK = 15       # {cardId, attackId}
LOG_DAMAGE = 16       # {cardId, serial, value}
AREA_ACTIVE, AREA_HAND, AREA_DISCARD, AREA_BENCH = 1, 2, 3, 4


class Miner:
    def __init__(self):
        self.card_attacks = collections.defaultdict(set)       # cardId -> {attackId}
        self.attack_dmg = collections.defaultdict(list)        # attackId -> [value]
        self.signals = collections.defaultdict(collections.Counter)  # cardId -> signals
        self.ko_cum = collections.defaultdict(list)            # cardId -> [cum dmg at KO]
        self.evolve_from = collections.defaultdict(collections.Counter)  # cardId -> {target}

    def feed_game(self, logs):
        last_attacker = None              # (player, attackId)
        cum = collections.defaultdict(int)  # (player, serial) -> dmg
        for lg in logs:
            t = lg.get("type")
            pi = lg.get("playerIndex")
            if t == LOG_DRAW:
                self.signals[lg.get("cardId")]["drawn"] += 1
            elif t == LOG_ENERGY:
                self.signals[lg.get("cardId")]["as_energy"] += 1
                self.signals[lg.get("cardIdTarget")]["gets_energy"] += 1
            elif t == LOG_EVOLVE:
                src, tgt = lg.get("cardId"), lg.get("cardIdTarget")
                self.signals[src]["evolves"] += 1
                if tgt is not None:
                    self.evolve_from[src][tgt] += 1
            elif t == LOG_MOVE:
                cid, fr, to = lg.get("cardId"), lg.get("fromArea"), lg.get("toArea")
                if fr == AREA_HAND and to in (AREA_ACTIVE, AREA_BENCH):
                    self.signals[cid]["into_play_as_pokemon"] += 1
                if fr == AREA_HAND and to == AREA_DISCARD:
                    self.signals[cid]["hand_to_discard"] += 1   # トレーナー使用の手掛かり
                if to == AREA_DISCARD and fr in (AREA_ACTIVE, AREA_BENCH):
                    c = cum.get((pi, lg.get("serial")), 0)
                    if c > 0:
                        self.ko_cum[cid].append(c)
            elif t == LOG_ATTACK:
                cid, aid = lg.get("cardId"), lg.get("attackId")
                self.card_attacks[cid].add(aid)
                self.signals[cid]["attacks"] += 1
                last_attacker = (pi, aid)
            elif t == LOG_DAMAGE:
                val = abs(lg.get("value", 0))
                cum[(pi, lg.get("serial"))] += val
                if last_attacker and pi == 1 - last_attacker[0] and val > 0:
                    self.attack_dmg[last_attacker[1]].append(val)

    # ---- 推定 -----------------------------------------------------------
    def category(self, cid: int) -> str:
        s = self.signals[cid]
        # エネルギー: エネとして付けられた実績がある（ポケモン挙動が無い）
        if s["as_energy"] > 0 and s["attacks"] == 0 and s["gets_energy"] == 0:
            return "basic_energy"   # ※特殊エネの可能性あり→要確認
        # ポケモン: ワザを使う/エネを受ける/進化する のいずれか（確度高）
        if s["attacks"] > 0 or s["gets_energy"] > 0 or s["evolves"] > 0:
            return "pokemon"
        # ここまで該当無し: トレーナー（サポート/グッズ）の可能性が高いが、
        # 控えポケモンの可能性も残る。要・公式リスト確認。
        return "trainer_or_bench_pokemon?"

    def attack_damage(self, aid: int):
        v = self.attack_dmg.get(aid)
        if not v:
            return None
        return collections.Counter(v).most_common(1)[0][0]  # 最頻値

    def hp_estimate(self, cid: int):
        v = self.ko_cum.get(cid)
        if not v:
            return None
        # 気絶時の累計ダメージの最小値 ≈ HP の上界に近い（最後の一撃で超えた分を含む）
        return min(v)


def run(games: int):
    from kaggle_environments import make
    import random
    from kuroko_ai import engine_io
    from kuroko_ai.config import Config
    from kuroko_ai.decklist import load_deck

    cfg = Config.load(os.path.join(ROOT, "config"))
    deck = load_deck(os.path.join(ROOT, "deck.csv"), cfg.deck)
    miner = Miner()

    def make_collector(buf):
        def fn(obs):
            o = obs if isinstance(obs, dict) else dict(obs)
            if engine_io.is_deck_request(o):
                return deck
            for lg in (o.get("logs") or []):
                buf.append(lg)
            sel = o.get("select")
            if sel is None:
                return []
            opts = sel.get("option") or []
            n = len(opts)
            if n == 0:
                return []
            mn = sel.get("minCount") or 0
            mx = sel.get("maxCount") or 1
            k = max(mn, 1)
            k = min(k, n, mx if mx > 0 else k)
            return random.sample(range(n), k)
        return fn

    for _ in range(games):
        buf = []
        env = make("cabt", configuration={"decks": [deck, deck]})
        env.run([make_collector(buf), make_collector(buf)])
        miner.feed_game(buf)
    return miner, sorted(set(deck))


def to_yaml(miner: Miner, card_ids) -> str:
    lines = [
        "# 自動生成（tools/mine_cards.py）— cabt 自己対戦ログからの実測下書き。",
        "# ★必ず公式カードリストで検証・補正すること（特に打点/HPのスケール、",
        "#   special_energy か basic_energy か、supporter か item か、進化段階）。",
        "cards:",
    ]
    for cid in card_ids:
        cat = miner.category(cid)
        s = miner.signals[cid]
        lines.append(f"  {cid}:")
        lines.append(f'    name: "card{cid}(仮)"')
        lines.append(f"    category: {cat}    # 推定: {dict(s)}")
        if cat == "pokemon":
            hp = miner.hp_estimate(cid)
            if hp is not None:
                lines.append(f"    hp: {hp}        # 気絶累計ダメージからの粗い推定。要確認")
            ev = miner.evolve_from.get(cid)
            if ev:
                tgt = ev.most_common(1)[0][0]
                lines.append(f"    evolves_from: {tgt}    # 推定")
            atks = sorted(miner.card_attacks.get(cid, []))
            if atks:
                lines.append("    attacks:")
                for aid in atks:
                    dmg = miner.attack_damage(aid)
                    dmg_s = dmg if dmg is not None else 0
                    lines.append(f"      - {{id: {aid}, damage: {dmg_s}}}   # 打点は観測最頻値")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    miner, card_ids = run(args.games)

    print(f"=== マイニング結果（{args.games}戦） ===")
    print("cardId -> category / attacks(打点) / HP推定")
    for cid in card_ids:
        atks = ", ".join(
            f"{a}={miner.attack_damage(a)}" for a in sorted(miner.card_attacks.get(cid, []))
        )
        hp = miner.hp_estimate(cid)
        print(f"  {cid:5}  {miner.category(cid):18} "
              f"atk[{atks}]  HP~{hp if hp is not None else '-'}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(to_yaml(miner, card_ids))
        print(f"\n下書きYAMLを書き出しました: {args.out}")
        print("→ 公式カードリストで検証し、config/deck.yaml に反映してください。")


if __name__ == "__main__":
    main()
