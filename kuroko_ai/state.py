"""ドメイン型（エンジン非依存）。

cabt エンジンが渡してくる生の dict を、ここで定義する型に `engine_io.py` が
変換します。ポリシー／評価／読み合い／ムーブの各モジュールは、生 dict ではなく
この型だけを触ります。こうしておくと、万一 SDK のフィールド名が変わっても
修正は `engine_io.py` の 1 ファイルだけで済みます。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# エンジンの数値コード（self-play で実測したもの。公式SDKドキュメントで要確認）
# ---------------------------------------------------------------------------
class SelectType(IntEnum):
    """`select.type` = いま何を聞かれているか。"""

    ACTION_MENU = 0      # メインの行動選択（1つ選ぶ）: 手札プレイ/進化/特性/にげる/ワザ/終了
    TARGET = 1           # 場のポケモンを対象に選ぶ
    ENERGY = 4           # エネルギーを付ける／動かす
    PICK_N = 5           # カードを N 枚選ぶ（トラッシュ等）
    NUMBER = 8           # 数値を選ぶ
    YES_NO = 9           # はい／いいえ（マリガン等）
    UNKNOWN = -1


class OptionType(IntEnum):
    """`option.type` = 各選択肢の正体。"""

    NUMBER = 0           # 数値
    YES = 1
    NO = 2
    TARGET = 3           # 場のポケモンを指す {area,index,playerIndex}
    ENERGY_COST = 6      # ワザ/にげのコスト支払い（どのエネを使うか） {energyIndex,count}
    PLAY_HAND = 7        # 手札のポケモン/トレーナーを出す/使う {index}
    ATTACH_ENERGY = 8    # 手札のエネルギーを場のポケモンへ付ける {area,index,inPlayArea,inPlayIndex}
    EVOLVE = 9           # 進化（手札の進化ポケモンを既存個体へ重ねる）
    ABILITY = 10         # 特性を使う {area,index}
    RETREAT = 12         # にげる
    ATTACK = 13          # ワザを使う {attackId}
    END_TURN = 14        # ターンを終了
    UNKNOWN = -1


class Area(IntEnum):
    """場所コード（log type6 の from/to と現状から推定）。"""

    ACTIVE = 1
    HAND = 2
    DISCARD = 3
    BENCH = 4
    SPECIAL = 5     # 用途未確定
    LOST_OR_TEMP = 6
    DECK = 8
    UNKNOWN = -1


@dataclass
class CardView:
    """場・手札にある 1 枚。"""

    id: int
    serial: int = -1
    player_index: int = -1
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_raw(cls, d: Optional[dict]) -> Optional["CardView"]:
        if not d:
            return None
        return cls(
            id=int(d.get("id", -1)),
            serial=int(d.get("serial", -1)),
            player_index=int(d.get("playerIndex", -1)),
            raw=d,
        )


@dataclass
class PlayerState:
    """片プレイヤーの公開情報。相手の hand は None（非公開）で handCount のみ。"""

    active: list[CardView]
    bench: list[CardView]
    bench_max: int
    deck_count: int
    discard: list[CardView]
    prize: list[CardView]
    hand_count: int
    hand: Optional[list[CardView]]      # 自分のみ中身が見える
    poisoned: bool = False
    burned: bool = False
    asleep: bool = False
    paralyzed: bool = False
    confused: bool = False
    raw: dict = field(default_factory=dict)

    @property
    def hand_visible(self) -> bool:
        return self.hand is not None


@dataclass
class Option:
    """1 つの合法手。`index` は engine に返すインデックス。"""

    index: int                 # この選択肢の位置（= エンジンに渡す番号）
    type: OptionType
    raw: dict
    # よく使うフィールドを取り出しておく
    area: Optional[int] = None
    target_index: Optional[int] = None
    player_index: Optional[int] = None
    in_play_area: Optional[int] = None
    in_play_index: Optional[int] = None
    attack_id: Optional[int] = None
    number: Optional[int] = None
    energy_index: Optional[int] = None
    count: Optional[int] = None


@dataclass
class Decision:
    """いま下すべき意思決定（select をラップ）。"""

    type: SelectType
    context: int
    min_count: int
    max_count: int
    options: list[Option]
    effect: Optional[dict] = None        # 効果の発生源カードなど
    context_card: Optional[dict] = None
    remain_damage_counter: int = 0
    remain_energy_cost: int = 0
    raw: dict = field(default_factory=dict)

    def options_of(self, *types: OptionType) -> list[Option]:
        s = set(types)
        return [o for o in self.options if o.type in s]


@dataclass
class GameState:
    """1 回の意思決定時点の全体像。"""

    turn: int
    turn_action_count: int
    your_index: int
    first_player: int
    supporter_played: bool
    stadium_played: bool
    energy_attached: bool
    retreated: bool
    result: int                          # -1=継続, 0/1=勝者index, 2=引き分け
    stadium: list[Any]
    players: list[PlayerState]
    logs: list[dict]
    raw: dict = field(default_factory=dict)

    @property
    def me(self) -> PlayerState:
        return self.players[self.your_index]

    @property
    def opp(self) -> PlayerState:
        return self.players[1 - self.your_index]

    @property
    def is_first_player(self) -> bool:
        return self.first_player == self.your_index
