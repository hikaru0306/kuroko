---
name: video-edit
description: 動画編集の技術知識とffmpeg実務レシピ。カット・結合・字幕・エンコード設定(H.264/H.265/AV1)・音声処理・配信向け書き出し、編集理論(カット技法・テンポ)。動画の加工・変換・自動化の依頼で使う。
argument-hint: [やりたいこと(例: 動画を結合して字幕焼き込み)]
---

# 動画編集

依頼: $ARGUMENTS

作業前に `ffmpeg -version` と `ffprobe <入力>` で環境と素材(コーデック・解像度・fps・音声)を必ず確認する。処理後は出力を ffprobe と(可能なら)再生確認で検証する。

## エンコードの選定(2026年時点)

| コーデック | 用途 | 品質設定の目安 |
| --- | --- | --- |
| **H.264 (libx264)** | 互換性最優先・共有用 | CRF 18–22, `-preset slow`, `-pix_fmt yuv420p` |
| **H.265 (libx265)** | 容量効率(H.264比約半分) | CRF 20–26。Apple系互換に `-tag:v hvc1` |
| **AV1 (libsvtav1)** | 将来性・アーカイブ・配信 | CRF 24–30, `-preset 6`, `-svtav1-params tune=0:keyint=10s`。libaomより2–5倍速い |

音声: MP4→AAC(`-c:a aac -b:a 192k`)、WebM/MKV→Opus(`-c:a libopus -b:a 128k`)。
迷ったら H.264 CRF 20 + AAC のMP4。エンコード速度: H.264 ≫ H.265 > AV1。

## 実務レシピ

```bash
# 無劣化カット(再エンコードなし。カット点はキーフレームに丸められる)
ffmpeg -ss 00:01:00 -to 00:02:30 -i in.mp4 -c copy out.mp4
# フレーム精度カット(再エンコード)
ffmpeg -ss 00:01:00 -to 00:02:30 -i in.mp4 -c:v libx264 -crf 20 -c:a aac out.mp4

# 結合(同一コーデック・無劣化): list.txt に file 'a.mp4' を列挙
ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4
# 結合(異種素材): 解像度・fpsを揃えて再エンコード
ffmpeg -i a.mp4 -i b.mp4 -filter_complex "[0:v]scale=1920:1080,fps=30[v0];[1:v]scale=1920:1080,fps=30[v1];[v0][0:a][v1][1:a]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" out.mp4

# クロスフェード(映像xfade + 音声acrossfade、1秒)
ffmpeg -i a.mp4 -i b.mp4 -filter_complex "[0:v][1:v]xfade=transition=fade:duration=1:offset=<Aの長さ-1>[v];[0:a][1:a]acrossfade=d=1[a]" -map "[v]" -map "[a]" out.mp4

# 字幕: ソフト字幕(切替可能) / 焼き込み
ffmpeg -i in.mp4 -i subs.srt -c copy -c:s mov_text out.mp4
ffmpeg -i in.mp4 -vf "subtitles=subs.srt:force_style='FontSize=24,OutlineColour=&H80000000,BorderStyle=4'" -c:a copy out.mp4

# 音量正規化(配信標準 -14 LUFS: 2パスのloudnormが正確。簡易は1パス)
ffmpeg -i in.mp4 -af loudnorm=I=-14:TP=-1.5:LRA=11 -c:v copy out.mp4

# 速度変更(2倍速: 映像PTSと音声atempoを両方)
ffmpeg -i in.mp4 -vf "setpts=0.5*PTS" -af "atempo=2.0" out.mp4

# GIF(パレット2パスで高品質) / サムネイル / 音声抽出
ffmpeg -i in.mp4 -vf "fps=12,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" out.gif
ffmpeg -ss 00:00:05 -i in.mp4 -frames:v 1 -q:v 2 thumb.jpg
ffmpeg -i in.mp4 -vn -c:a libmp3lame -q:a 2 out.mp3
```

## 配信向けプリセット

- **YouTube**: H.264 CRF 18–20 / H.265、AAC 192k以上、`-movflags +faststart`。1080p30なら8Mbps相当で十分。
- **X/SNS**: H.264 + AAC、`yuv420p` 必須、短尺は解像度720pで容量優先。
- **Web埋め込み**: 720pなら2.5Mbps程度から。品質判定はVMAFで機械的に(90以上が目安)。
- **アーカイブ**: SVT-AV1 CRF 24–26 か、元素材の `-c copy` 保管。

## 編集理論(構成を頼まれたら)

- **冒頭3秒**: 結論・最良の瞬間を先に見せる(コールドオープン)。視聴維持は冒頭で決まる。
- **J/Lカット**: 音声を映像より先行/後行させると会話が自然につながる。
- **テンポ**: 無音・停滞は容赦なくカット(ジャンプカット)。BPMに合わせたカット割りはそれだけで気持ちいい。
- **音が7割**: 音量の均一化(上のloudnorm)、SEの付加、BGMのダッキング(`sidechaincompress`)で体感品質が大きく上がる。

## 自動化

大量処理はシェルループ+ffmpegで。失敗検出のため `-xerror` と終了コードを確認し、処理後に ffprobe で長さ・ストリーム構成を元素材と突き合わせる。
