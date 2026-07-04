# kuroko

裏方リポジトリ。

## Fable 5 スキルパック

Claude Code で Fable 5 流の使い方(長時間自律実行・段階的計画・サブエージェント検証・外部メモリ)を再現するスキル集。`.claude/skills/` に配置されており、このリポジトリを開くと自動で読み込まれる。

| コマンド | 用途 |
| --- | --- |
| `/fable-run <タスク>` | ゴール・成功基準・検証付きチェックポイントで完了まで自律実行 |
| `/fable-plan <タスク>` | 検証可能なフェーズ計画を作成して `memory/` に保存 |
| `/fable-verify [対象]` | 別コンテキストのサブエージェントで成果物を検証 |
| `/fable-delegate [タスク]` | 独立サブタスクを並列サブエージェントに委譲 |
| `/fable-memory record\|recall\|bootstrap` | セッションをまたぐ教訓ノートの記録・参照 |
| `/fable-report [対象]` | 証拠に基づく読みやすい完了報告を生成 |
| `fable-style` | 動作原則の背景知識(Claudeが自動参照、コマンドなし) |

典型的な流れ: `/fable-plan` で計画 → `/fable-run` で実行(内部で `/fable-verify` と `/fable-memory` を活用)→ `/fable-report` で報告。

設計根拠と出典は [docs/fable5-usage-guide.md](docs/fable5-usage-guide.md) を参照。
