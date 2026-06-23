"""エンジン入出力アダプタ（唯一の「生 dict に触る」場所）。

役割:
  parse_observation(obs) -> (GameState | None, Decision | None)
      cabt の observation を読みやすいドメイン型へ変換する。
  is_deck_request(obs) -> bool
      最初の「デッキ提出」要求かどうか。
  encode_action(decision, chosen_options) -> list[int]
      選んだ Option を、エンジンが期待する index のリストへ変換する。

cabt の observation 仕様（self-play で実測 / 公式ドキュメントで要確認）:
  obs = {
    "select": None もしくは {
        "type": int, "context": int,
        "minCount": int, "maxCount": int,
        "option": [ {...}, ... ],
        "effect": {...}, "contextCard": {...},
        "remainDamageCounter": int, "remainEnergyCost": int,
    },
    "current": {
        "turn", "turnActionCount", "yourIndex", "firstPlayer",
        "supporterPlayed", "stadiumPlayed", "energyAttached", "retreated",
        "result", "stadium", "looking",
        "players": [ {active,bench,benchMax,deckCount,discard,prize,
                      handCount,hand,poisoned,burned,asleep,paralyzed,confused}, x2 ],
    },
    "logs": [ {...}, ... ],
  }
  - select が None かつ未対戦 → デッキ(60枚の id リスト)を返す。
  - それ以外 → option の index リストを返す（minCount..maxCount 枚）。
"""

from __future__ import annotations

from typing import Optional

from .state import (
    Area,
    CardView,
    Decision,
    GameState,
    Option,
    OptionType,
    PlayerState,
    SelectType,
)


def is_deck_request(obs: dict) -> bool:
    """デッキ提出を求められている最初の呼び出しかどうか。"""
    return obs.get("select") is None and obs.get("current") is None


def _safe_enum(enum_cls, value, default):
    try:
        return enum_cls(value)
    except (ValueError, TypeError):
        return default


def _cards(raw_list) -> list[CardView]:
    return [CardView.from_raw(c) for c in (raw_list or []) if c]


def _parse_player(d: dict) -> PlayerState:
    d = d or {}
    return PlayerState(
        active=_cards(d.get("active")),
        bench=_cards(d.get("bench")),
        bench_max=int(d.get("benchMax", 5)),
        deck_count=int(d.get("deckCount", 0)),
        discard=_cards(d.get("discard")),
        prize=_cards(d.get("prize")),
        hand_count=int(d.get("handCount", 0)),
        hand=(_cards(d.get("hand")) if d.get("hand") is not None else None),
        poisoned=bool(d.get("poisoned", False)),
        burned=bool(d.get("burned", False)),
        asleep=bool(d.get("asleep", False)),
        paralyzed=bool(d.get("paralyzed", False)),
        confused=bool(d.get("confused", False)),
        raw=d,
    )


def _parse_option(index: int, d: dict) -> Option:
    d = d or {}
    otype = _safe_enum(OptionType, d.get("type"), OptionType.UNKNOWN)
    return Option(
        index=index,
        type=otype,
        raw=d,
        area=d.get("area"),
        target_index=d.get("index"),
        player_index=d.get("playerIndex"),
        in_play_area=d.get("inPlayArea"),
        in_play_index=d.get("inPlayIndex"),
        attack_id=d.get("attackId"),
        number=d.get("number"),
        energy_index=d.get("energyIndex"),
        count=d.get("count"),
    )


def _parse_decision(sel: dict) -> Decision:
    options = [_parse_option(i, o) for i, o in enumerate(sel.get("option") or [])]
    return Decision(
        type=_safe_enum(SelectType, sel.get("type"), SelectType.UNKNOWN),
        context=int(sel.get("context", -1)),
        min_count=int(sel.get("minCount", 0)),
        max_count=int(sel.get("maxCount", 1)),
        options=options,
        effect=sel.get("effect"),
        context_card=sel.get("contextCard"),
        remain_damage_counter=int(sel.get("remainDamageCounter", 0)),
        remain_energy_cost=int(sel.get("remainEnergyCost", 0)),
        raw=sel,
    )


def _parse_state(cur: dict, logs) -> GameState:
    cur = cur or {}
    players = [_parse_player(p) for p in (cur.get("players") or [{}, {}])]
    return GameState(
        turn=int(cur.get("turn", 0)),
        turn_action_count=int(cur.get("turnActionCount", 0)),
        your_index=int(cur.get("yourIndex", 0)),
        first_player=int(cur.get("firstPlayer", -1)),
        supporter_played=bool(cur.get("supporterPlayed", False)),
        stadium_played=bool(cur.get("stadiumPlayed", False)),
        energy_attached=bool(cur.get("energyAttached", False)),
        retreated=bool(cur.get("retreated", False)),
        result=int(cur.get("result", -1)),
        stadium=cur.get("stadium") or [],
        players=players,
        logs=logs or [],
        raw=cur,
    )


def parse_observation(obs: dict):
    """(GameState|None, Decision|None) を返す。

    select が None（デッキ提出 or 対戦終了）の場合 Decision は None。
    """
    cur = obs.get("current")
    state = _parse_state(cur, obs.get("logs")) if cur is not None else None
    sel = obs.get("select")
    decision = _parse_decision(sel) if sel is not None else None
    return state, decision


def encode_action(decision: Optional[Decision], chosen: list[Option]) -> list[int]:
    """選んだ Option を index リストへ。決定が無ければ空リスト。"""
    if decision is None:
        return []
    return [o.index for o in chosen]


__all__ = [
    "Area",
    "is_deck_request",
    "parse_observation",
    "encode_action",
]
