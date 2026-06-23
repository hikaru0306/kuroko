"""設定ローダ。

調整のしやすさを最優先に、次の 4 つを分離している:

  deck       … 60枚のデッキ + 各カードの役割/メタ情報   (config/deck.yaml)
  strategy   … 理想のムーブ（ゲームプラン・優先順位）     (config/strategy.yaml)
  evaluation … 盤面評価の重み（チューニング用ノブ）        (config/evaluation.yaml)
  reads      … 読み合い（相手モデル・対面想定）            (config/reads.yaml)

挙動の堅牢性のため「組み込みデフォルト（このファイルの DEFAULTS）」を真実の源とし、
YAML が存在し PyYAML が使える場合だけ、その上に上書き(deep-merge)する。
こうすると Kaggle 上で PyYAML や YAML ファイルが無くても必ず動く。
"""

from __future__ import annotations

import os
from typing import Any

# --------------------------------------------------------------------------
# 組み込みデフォルト（YAML はこれを上書きするだけ）
# --------------------------------------------------------------------------
DEFAULTS: dict[str, Any] = {
    "strategy": {
        # 行動メニューの戦略モード:
        #   "engine_order" … エンジンの選択肢順(展開→攻撃→終了)を信頼し先頭を選ぶ。
        #                     ローカル実測で最も強い。推奨デフォルト。
        #   "priority"     … 下の action_priority + evaluation で完全に並べ替える(実験用)
        "action_menu_mode": "engine_order",
        # KO 上書き: 確実に倒せるワザを最優先。deck.yaml に実測ワザ打点が入ったため既定 ON。
        # （カードDBが不正確だと誤判定で逆効果になり得るので、デッキ差し替え時は要再検証）
        "enable_ko_override": True,
        # エネ付け先の加点（priority モード用）
        "attach_bonus": {"main_attacker": 0.0, "active": 0.0},
        # エネをメインアタッカー/アクティブへ集中させる。
        # ※サンプルデッキ(721/722/723の3アタッカー)では集中より分散の方が良く、
        #   ローカル実測で OFF の方が強かったため既定 OFF。1体集中型デッキでは ON 推奨。
        "concentrate_energy": False,
        # 場づくりで最低限欲しいベンチのたねポケモン数
        "desired_bench_pokemon": 3,
        # メインアタッカーに乗せたいエネルギー枚数（攻撃を始める目安）
        "attacker_energy_goal": 2,
        # ↓ action_menu_mode="priority" の時だけ使う基本優先度（高いほど先にやる）
        # 実際の点数は evaluation の重みと状況補正で上下する
        # 高いほど先に実行。原則「展開・進化 → 攻撃 → 終了」の順になるよう設計。
        # 攻撃は KO 可能なら evaluation の ko_opponent で大きく加点され跳ね上がる。
        "action_priority": {
            "ability": 90,        # 特性（基本ノーリスク → 先に）
            "draw_supporter": 85,  # ドロー/サーチ系サポート
            "evolve": 84,          # 進化（アタッカー育成 → 攻撃より優先）
            "put_basic": 78,       # たねをベンチに展開
            "play_item": 60,       # グッズ
            "attach_energy": 80,   # エネ付け（攻撃より先に行う最重要手）
            "attack": 45,          # ワザ（不明打点でも +unknown_attack_value で終了より上）
            "retreat": 20,         # にげる（基本は消極的）
            "end_turn": 0,         # 何も無ければ終了
        },
        # このしきい値未満の評価値の行動はやらず、ターンを終了する
        "min_action_value": 1.0,
        # マリガン/ハンド維持などの yes/no デフォルト（True=最初の選択肢を選ぶ）
        "default_yes": True,
    },

    "evaluation": {
        # 盤面特徴量の重み（KO/サイドが最重要）
        "weights": {
            "prize_taken": 100.0,        # 自分が取ったサイド差
            "ko_opponent": 120.0,        # 相手アクティブを倒せる行動
            "knocked_out_self": -110.0,  # 自分が倒される見込み
            "damage_dealt": 0.6,         # 与ダメージ1あたり
            "bench_pokemon": 8.0,        # 自分のベンチたね数
            "energy_on_attacker": 6.0,   # メインアタッカーのエネ
            "hand_size": 1.5,            # 手札枚数
            "active_hp_remaining": 0.2,  # 自アクティブ残HP
            "unknown_attack_value": 30.0,  # 打点不明なワザの暫定価値（攻撃を選ばせる）
        },
        # KO 判定に使うおおまかなHP（カードDBが無い時のフォールバック）
        "default_pokemon_hp": 120,
        # ワザ選択の効率スコア重み（最大打点一辺倒にしないための係数）
        "attack": {
            "ko_value": 1000.0,         # 相手アクティブをKOできる価値（最重要）
            "overkill": 0.05,           # KO時、打点が大きいほど僅かに減点（温存）
            "damage": 1.0,              # KO不可時の与ダメージ1あたり
            "bench_damage": 1.2,        # ベンチ1体への打点1あたり（将来のサイド）
            "energy_accel": 40.0,       # 攻撃しながらエネ加速1枚あたり（高評価）
            "heal": 0.3,                # 回復1あたり
            "recoil": 1.5,              # 反動ダメージ1あたりのペナルティ
            "energy_discard": 25.0,     # 自分のエネ捨て1枚のペナルティ（次が遅れる）
            "cant_attack_next": 150.0,  # 次ターン攻撃不可のペナルティ
            "unknown": 30.0,            # 打点不明ワザの暫定スコア
        },
    },

    "reads": {
        # 相手アーキタイプの事前分布（観測で更新していく土台）
        "archetype_prior": {
            "aggro": 0.34,
            "control": 0.33,
            "combo": 0.33,
        },
        # 相手の脅威を想定して残しておきたい自アクティブのHPバッファ
        "hp_buffer_vs_aggro": 30,
        # ベンチ枚数がこれ以下の相手は攻撃的とみなす等のヒューリスティクス
        "low_bench_threshold": 1,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_yaml(path: str):
    if not os.path.exists(path):
        return None
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


class Config:
    """4 領域の設定を保持する軽量コンテナ。"""

    def __init__(self, strategy: dict, evaluation: dict, reads: dict, deck: dict):
        self.strategy = strategy
        self.evaluation = evaluation
        self.reads = reads
        self.deck = deck

    @classmethod
    def load(cls, config_dir: str | None = None) -> "Config":
        strategy = dict(DEFAULTS["strategy"])
        evaluation = dict(DEFAULTS["evaluation"])
        reads = dict(DEFAULTS["reads"])
        deck: dict = {}

        if config_dir and os.path.isdir(config_dir):
            for name, target_key in (
                ("strategy", "strategy"),
                ("evaluation", "evaluation"),
                ("reads", "reads"),
            ):
                data = _load_yaml(os.path.join(config_dir, f"{name}.yaml"))
                if isinstance(data, dict):
                    merged = _deep_merge(DEFAULTS[target_key], data)
                    if target_key == "strategy":
                        strategy = merged
                    elif target_key == "evaluation":
                        evaluation = merged
                    else:
                        reads = merged
            deck_data = _load_yaml(os.path.join(config_dir, "deck.yaml"))
            if isinstance(deck_data, dict):
                deck = deck_data

        return cls(strategy=strategy, evaluation=evaluation, reads=reads, deck=deck)
