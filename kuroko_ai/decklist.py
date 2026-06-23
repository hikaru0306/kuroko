"""デッキ読み込み。

提出物の `deck.csv`（60行 = カードidを1行1枚）を真実の源とする。
deck.yaml の `deck:` リストがあればそちらを優先（人が編集しやすいため）。
最終的に「60個の int のリスト」を返す。
"""

from __future__ import annotations

import os


def _read_csv_ids(csv_path: str) -> list[int]:
    ids: list[int] = []
    if not os.path.exists(csv_path):
        return ids
    with open(csv_path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            # "id" 単独 or "id,枚数" or ヘッダ行を許容
            head = s.split(",")[0].strip()
            if not head.lstrip("-").isdigit():
                continue
            parts = s.split(",")
            if len(parts) >= 2 and parts[1].strip().lstrip("-").isdigit():
                cid, cnt = int(parts[0]), int(parts[1])
                ids.extend([cid] * max(0, cnt))
            else:
                ids.append(int(head))
    return ids


def load_deck(csv_path: str, deck_cfg: dict | None = None) -> list[int]:
    deck_cfg = deck_cfg or {}
    # 1) deck.yaml の deck: が最優先
    yaml_deck = deck_cfg.get("deck")
    ids: list[int] = []
    if isinstance(yaml_deck, list) and yaml_deck:
        for entry in yaml_deck:
            if isinstance(entry, dict):
                cid = int(entry.get("id"))
                cnt = int(entry.get("count", 1))
                ids.extend([cid] * cnt)
            else:
                ids.append(int(entry))
    # 2) なければ deck.csv
    if not ids:
        ids = _read_csv_ids(csv_path)
    return ids
