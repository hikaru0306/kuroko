# アーキテクチャ & cabt エンジン解析メモ

## 1. cabt エンジンの仕様（self-play で実測 / 公式ドキュメントで要確認）

提出物は `main.py`（最上位）+ `deck.csv` を含む `.tar.gz`。エンジンは意思決定の
たびに `agent(observation)` を呼ぶ。

### observation の構造

```text
obs = {
  "select": None もしくは {
      "type": int,          # 何を聞かれているか（下表）
      "context": int,
      "minCount", "maxCount": int,   # 選ぶ個数の範囲
      "option": [ {...}, ... ],      # 合法な選択肢。返すのはこの index
      "effect", "contextCard": {...},
      "remainDamageCounter", "remainEnergyCost": int,
  },
  "current": {
      "turn", "turnActionCount", "yourIndex", "firstPlayer",
      "supporterPlayed", "stadiumPlayed", "energyAttached", "retreated",
      "result",            # -1=継続, 0/1=勝者index, 2=引き分け
      "stadium", "looking",
      "players": [ P0, P1 ],   # 各 P = {active,bench,benchMax,deckCount,
                               #         discard,prize,handCount,hand,
                               #         poisoned,burned,asleep,paralyzed,confused}
  },                         # 自分の hand は中身が見え、相手は null（handCountのみ）
  "logs": [ {...} ],         # 直近の出来事
}
```

- 最初の呼び出し（`select=None` かつ `current=None`）→ **60枚のデッキ(idのリスト)** を返す。
- 以降 → **option の index リスト**（minCount..maxCount 個）を返す。
- 不正手・60枚でないデッキ・タイムアウト → その場で敗北。

### select.type（何を聞かれているか）

| type | 意味 |
|----|------|
| 0 | **行動メニュー**（1ターン中の主行動を1つ選ぶ）|
| 1 | 対象選択（場のポケモンを選ぶ）|
| 4 | ワザ/にげの**エネルギーコスト支払い** |
| 5 | カードを N 枚選ぶ（トラッシュ等）|
| 8 | 数値を選ぶ |
| 9 | はい/いいえ（マリガン等）|

### option.type（行動メニュー内の選択肢の正体）★重要な実測知見

| type | 意味 | 主なフィールド |
|----|------|----------------|
| 0  | 数値 | number |
| 1/2| はい / いいえ | — |
| 3  | 対象（場のポケモン）| area, index, playerIndex |
| 6  | エネコスト支払い | energyIndex, count |
| 7  | **手札のポケモン/トレーナーを出す・使う** | index(=手札index) |
| 8  | **手札のエネルギーを場へ付ける** | area, index, inPlayArea, inPlayIndex |
| 9  | **進化** | area, index, inPlayArea, inPlayIndex |
| 10 | 特性を使う | area, index |
| 12 | にげる | — |
| 13 | **ワザを使う** | attackId |
| 14 | **ターン終了** |（常に末尾に並ぶ）|

> 落とし穴: 当初 type 8 を「ベンチ展開」と誤解していた。実際は **type 8 = エネ付け**、
> ベンチ展開やトレーナーは **type 7**、進化は **type 9**。これを正したのが強さの分岐点。

### area コード（log type6 の from/to と current から推定）

`1=アクティブ, 2=手札, 3=トラッシュ, 4=ベンチ, 8=山札`（5,6 等は用途未確定）。

## 2. 設計（責務の分離）

```
main.py                    Kaggle エントリ。kuroko_ai を呼ぶだけ
kuroko_ai/
  engine_io.py   ★唯一「生dict」に触る層。obs⇄ドメイン型変換。SDK差異はここだけ直せばよい
  state.py        ドメイン型（GameState/Decision/Option/enum）
  config.py       設定ローダ（DEFAULTS を YAML が上書き）
  decklist.py     deck.csv / deck.yaml → 60枚のidリスト
  cards.py        カード知識ベース（HP/ワザ/役割）
  lines.py        理想のムーブ（strategy.yaml）
  evaluation.py   盤面評価（evaluation.yaml）
  reads.py        相手モデル（reads.yaml）
  policy.py       決定の統合。select.type ごとに最適 option を選ぶ
  agent.py        状態保持 + ループ安全弁 + フォールバック
```

意思決定の流れ:
`obs → engine_io.parse → policy.decide(state, decision) → engine_io.encode → list[int]`

## 3. なぜ engine_order が強いのか

行動メニュー(type 0)の選択肢は、エンジン側で
「特性・ドロー・展開・エネ・進化 …（中盤の手）… → ワザ → 終了」
の自然な順に並んでいる。各意思決定で**先頭(index 0)を選び続ける**と、
「やれることを全部やってから攻撃し、最後に終了」という一貫したプレイになる。

自前の優先度付け(`priority` モード)で並べ替えると、カードの実データが無い分だけ
判断を誤り、エンジン順より弱くなる。よって既定は `engine_order`。
**カードDB(deck.yaml)を正しく整備すれば** `priority` モードや `enable_ko_override`
が engine_order を上回る余地が生まれる ← ここが今後の伸びしろ。

## 4. ローカル検証ツール

- `tools/run_match.py` … 自己対戦・対baselineの勝率測定、HTML可視化
- `tests/test_agent_smoke.py` … 合法手・完走・60枚・main.py の健全性

## 5. 今後の改善候補

1. `config/deck.yaml` を公式カードリストで正確化（HP/ワザ打点/役割/進化ライン）。
2. それを土台に `enable_ko_override: true`（確実なKOを取る）を検証。
3. `reads.py` の相手モデルを、ログ(与ダメージ・展開速度)からより精緻に更新。
4. `evaluation.py` に「自分が次ターン倒される危険」の評価を追加（防御的撤退/壁）。
5. 持ち時間10分制約下での計算量管理（現状ほぼ定数時間で安全）。
