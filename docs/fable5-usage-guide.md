# Claude Fable 5 の使い方ガイド(調査まとめ)

このリポジトリの `.claude/skills/fable-*` スキルパックの設計根拠。2026年7月時点のネット調査に基づく。

## Fable 5 とは

- Anthropicの最上位公開モデル(モデルID: `claude-fable-5`)。Mythos 5と同時に2026年6月発表。
- ほぼ全ベンチマークでSOTA。タスクが長く複雑であるほど他モデルとの差が広がる。
- 1Mトークンコンテキスト、最大128k出力。$10/M入力・$50/M出力。
- Claude CodeやManaged Agentsのようなエージェントハーネスで動かすと、段階的な計画・サブエージェントへの委譲・自己検証をしながら数日単位で自律稼働できる。

## Fable 5流の使い方(公式プロンプティングガイドの要点)

1. **難しいタスクをそのまま渡す** — 従来モデルより難しいタスクを渡し、スコープ確認・質問・実行までやらせる。簡単なタスクだけでは実力を過小評価する。
2. **手順書ではなくゴールと成功基準を渡す** — 細かいステップ指示より、明確なゴール・成功基準・自己検証の手段を与える。旧モデル向けの過剰な指示はかえって品質を下げる。
3. **チェックポイント設計** — 各フェーズが「次に進む前に検証できる成果物」を生むようにパイプラインを設計する。
4. **サブエージェント検証** — 「一定間隔でサブエージェントに検証させろ」と明示する。別コンテキストの検証者は自己批判より正確。
5. **外部メモリ** — 計画・決定・発見をファイルに永続化して参照させる。ファイルベースのメモリはFable 5で特に効果が大きい(Opus 4.8比で改善幅3倍という発表時の結果あり)。
6. **並列サブエージェント** — 独立サブタスクは並列委譲し、ブロックせずに自分の作業を続けさせる。
7. **進捗の虚偽報告対策** — 「報告前に各主張をツール実行結果と突き合わせろ」と指示すると、捏造ステータス報告がほぼ消える(Anthropicのテスト結果)。
8. **長いターンを前提にする** — 高effort設定では1リクエストが数分〜、自律実行は数時間に及ぶ。タイムアウトや進捗表示を先に整える。
9. **推論の書き写しをさせない** — 思考過程を応答に転記させる指示は `reasoning_extraction` 拒否を誘発し、Opus 4.8へのフォールバックが増える。
10. **effortで調整** — 通常は `high`、最重要タスクは `xhigh`、定型作業は `medium`/`low`。Fable 5の低effortでも旧モデルの `xhigh` を上回ることが多い。

## このリポジトリのスキルパック

| スキル | 役割 | 対応する原則 |
| --- | --- | --- |
| `/fable-run` | 長時間自律実行ハーネス | 1, 2, 3, 7, 8 |
| `/fable-plan` | 検証可能なチェックポイント計画 | 3 |
| `/fable-verify` | フレッシュコンテキスト検証 | 4 |
| `/fable-delegate` | 並列サブエージェント委譲 | 6 |
| `/fable-memory` | 外部メモリ(教訓ノート) | 5 |
| `/fable-report` | 証拠ベースの再グラウンディング報告 | 7 |
| `/fable-boost` | 他モデルでのFable 5ギャップ補正(生成回数と検証回数で品質を買う) | 2, 4 |
| `/fable-intent` | 意図予測・先回り(「なぜ頼まれたか」の明示的推定) | 2 |
| `fable-style` | 動作原則の背景知識(自動参照) | 2, 7, 9 |

ドメインスキルとして `/game-dev`(エンジン選定・コアループ・ゲームフィール)と `/video-edit`(ffmpegレシピ・エンコード設定・編集理論)も収録。

Fable 5以外のモデル(Opus 4.8など)で使っても、同じワークフローを再現できるように書いてある。

### Opus 4.8とのギャップについて

スキルはモデルの素の能力(初回正答率、長期一貫性、曖昧さの処理)そのものを変えることはできない。`/fable-boost` はその差を「追加の調査・複数候補生成・別コンテキスト検証・ファイルベースメモリ」という追加計算で補う設計。知識系スキル(`/game-dev`、`/video-edit`)は、どのモデルでも同じ知識ベース・同じ手順で作業させることで出力の再現性を揃える。

## 注意点

- Fable 5は攻撃的サイバーセキュリティと生物・生命科学の一部トピックで安全クラシファイアが作動し、Opus 4.8からの応答に切り替わることがある(セッションの5%未満)。
- 米国の輸出規制の影響で一時提供停止ののち、2026年7月に再提供された。

## 出典

- [Claude Fable 5 and Claude Mythos 5 — Anthropic](https://www.anthropic.com/news/claude-fable-5-mythos-5)
- [Introducing Claude Fable 5 and Claude Mythos 5 — Claude Platform Docs](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5)
- [Prompting Claude Fable 5 — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5)
- [Claude Fable — Anthropic](https://www.anthropic.com/claude/fable)
- [Redeploying Claude Fable 5 — Anthropic](https://www.anthropic.com/news/redeploying-fable-5)
- [Claude Fable 5 brings Mythos to the masses — Tom's Hardware](https://www.tomshardware.com/tech-industry/artificial-intelligence/claude-fable-5-brings-mythos-to-the-masses-anthropics-next-frontier-model-is-state-of-the-art-on-nearly-all-tested-benchmarks)
- [Anthropic's Claude Fable 5 is a version of Mythos the public can access today — TechCrunch](https://techcrunch.com/2026/06/09/anthropic-released-claude-fable-5-its-most-powerful-model-publicly-days-after-warning-ai-is-getting-too-dangerous/)
- [Extend Claude with skills — Claude Code Docs](https://code.claude.com/docs/en/skills)
- [Godot vs Unity in 2026 — DEV Community](https://dev.to/linou518/godot-vs-unity-in-2026-which-engine-should-indie-developers-choose-50g4)
- [Best Game Development Engines in 2026](https://phantomcave.com/blog/best-game-development-engines/)
- [AV1 encoder guide — ffmpeg.party](https://ffmpeg.party/guides/av1/)
- [FFmpeg in Production — getstream.io](https://getstream.io/blog/ffmpeg/)
