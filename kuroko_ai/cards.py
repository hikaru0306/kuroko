"""カード知識ベース。

cabt の observation には「カードid」しか入っておらず、各idが何をするカードかは
含まれない（= 公式の「指定カードリスト」を見て人が定義する必要がある）。
ここでは config/deck.yaml の `cards:` セクションから読み込む。未定義idは
безопな既定値（不明なポケモン扱い）にフォールバックする。

deck.yaml の cards エントリ例:
  1219:
    name: "メインアタッカーex"
    category: pokemon        # pokemon / basic_energy / item / supporter / tool / stadium
    role: main_attacker      # 任意ラベル（lines/evaluation から参照）
    hp: 330
    stage: 1                 # 0=たね,1=1進化,2=2進化
    evolves_from: 1145
    is_ex: true
    attacks:
      - {id: 1044, cost: 2, damage: 230}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# よく使う役割ラベル（自由に増やしてよい。文字列一致で参照されるだけ）
ROLE_MAIN_ATTACKER = "main_attacker"
ROLE_SUB_ATTACKER = "sub_attacker"
ROLE_STARTER = "starter"
ROLE_DRAW = "draw"
ROLE_SEARCH = "search"

CATEGORY_POKEMON = "pokemon"
CATEGORY_BASIC_ENERGY = "basic_energy"
CATEGORY_SUPPORTER = "supporter"
CATEGORY_ITEM = "item"
CATEGORY_TOOL = "tool"
CATEGORY_STADIUM = "stadium"


@dataclass
class Attack:
    id: int
    cost: int = 1
    damage: int = 0
    name: str = ""
    # --- 副作用（効率評価で使う。0/False が「効果なし」） -----------------
    self_damage: int = 0          # 反動: 自分のアクティブが受けるダメージ
    bench_damage: int = 0         # 相手ベンチ1体あたりに与えるダメージ
    bench_targets: int = 0        # ベンチに当たる体数
    attaches_energy: int = 0      # 攻撃しながら付けられるエネ枚数（加速）
    discards_energy: int = 0      # 自分のエネを捨てる枚数（次の攻撃に響く）
    cant_attack_next: bool = False  # 次ターン攻撃できない（反動ロック）
    heal: int = 0                 # 自分の回復量


@dataclass
class Card:
    id: int
    name: str = ""
    category: str = CATEGORY_POKEMON
    role: str = ""
    hp: int = 0
    stage: int = 0
    evolves_from: Optional[int] = None
    is_ex: bool = False
    attacks: list[Attack] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def is_pokemon(self) -> bool:
        return self.category == CATEGORY_POKEMON

    @property
    def is_basic(self) -> bool:
        return self.is_pokemon and self.stage == 0

    @property
    def is_energy(self) -> bool:
        return self.category == CATEGORY_BASIC_ENERGY

    @property
    def is_supporter(self) -> bool:
        return self.category == CATEGORY_SUPPORTER

    def best_attack(self) -> Optional[Attack]:
        return max(self.attacks, key=lambda a: a.damage) if self.attacks else None


class CardDB:
    """id -> Card。deck.yaml から構築。"""

    def __init__(self, cards: dict[int, Card], default_hp: int = 120):
        self._cards = cards
        self._default_hp = default_hp

    @classmethod
    def from_config(cls, deck_cfg: dict, default_hp: int = 120) -> "CardDB":
        cards: dict[int, Card] = {}
        for cid, c in (deck_cfg.get("cards") or {}).items():
            try:
                cid = int(cid)
            except (TypeError, ValueError):
                continue
            c = c or {}
            attacks = [
                Attack(
                    id=int(a.get("id", -1)),
                    cost=int(a.get("cost", 1)),
                    damage=int(a.get("damage", 0)),
                    name=str(a.get("name", "")),
                    self_damage=int(a.get("self_damage", 0)),
                    bench_damage=int(a.get("bench_damage", 0)),
                    bench_targets=int(a.get("bench_targets", 0)),
                    attaches_energy=int(a.get("attaches_energy", 0)),
                    discards_energy=int(a.get("discards_energy", 0)),
                    cant_attack_next=bool(a.get("cant_attack_next", False)),
                    heal=int(a.get("heal", 0)),
                )
                for a in (c.get("attacks") or [])
            ]
            cards[cid] = Card(
                id=cid,
                name=str(c.get("name", "")),
                category=str(c.get("category", CATEGORY_POKEMON)),
                role=str(c.get("role", "")),
                hp=int(c.get("hp", 0)),
                stage=int(c.get("stage", 0)),
                evolves_from=c.get("evolves_from"),
                is_ex=bool(c.get("is_ex", False)),
                attacks=attacks,
                raw=c,
            )
        return cls(cards, default_hp=default_hp)

    def get(self, card_id: int) -> Card:
        card = self._cards.get(int(card_id)) if card_id is not None else None
        if card is not None:
            return card
        # 未定義id: 不明ポケモン扱い（既定HP）。エネルギーidは別途 deck.yaml で定義推奨。
        return Card(id=int(card_id) if card_id is not None else -1, hp=self._default_hp)

    def hp_of(self, card_id: int) -> int:
        c = self.get(card_id)
        return c.hp if c.hp > 0 else self._default_hp

    def role_of(self, card_id: int) -> str:
        return self.get(card_id).role

    def attack_by_id(self, attack_id: int) -> Optional[Attack]:
        for c in self._cards.values():
            for a in c.attacks:
                if a.id == attack_id:
                    return a
        return None
