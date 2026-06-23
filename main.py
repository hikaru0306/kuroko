"""Kaggle 提出用エントリポイント（tar.gz の最上位に置く）。

cabt エンジンは各意思決定ごとに `agent(observation)` を呼ぶ。
- 最初の呼び出し(select=None) では 60枚のデッキ(idのリスト)を返す。
- 以降は option の index リストを返す。

エージェント本体は kuroko_ai パッケージにあり、調整は config/*.yaml と deck.csv で行う。
"""

import os
import sys

# 提出物を展開した場所をimport対象に加える（パッケージを同梱するため）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kuroko_ai import KurokoAgent  # noqa: E402

# 試合をまたいで状態を保つため、モジュール単位で1度だけ生成
_AGENT = KurokoAgent(base_dir=os.path.dirname(os.path.abspath(__file__)))


def agent(observation, configuration=None):
    """cabt が呼ぶ関数。observation は dict、戻り値は list[int]。"""
    # observation が dict 以外（稀な wrapper）でも落ちないよう保険
    obs = observation if isinstance(observation, dict) else getattr(observation, "__dict__", {})
    try:
        return _AGENT.act(obs)
    except Exception:
        # 例外で空を返すと不正手で即負け。最低限の合法手にフォールバックする。
        return _safe_fallback(obs)


def _safe_fallback(obs):
    sel = obs.get("select") if isinstance(obs, dict) else None
    if sel is None:
        # デッキ提出フェーズ: 既定デッキを返す
        try:
            return _AGENT.deck
        except Exception:
            return []
    options = sel.get("option") or []
    min_count = sel.get("minCount") or 0
    count = max(min_count, 1) if options else 0
    count = min(count, len(options))
    return list(range(count))
