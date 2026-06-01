# DMPS ライブチャット分析ギャラリー

YouTubeライブ配信(アーカイブ)のチャットを取得・分析し、
リンク共有できるレポートとして GitHub Pages に公開する仕組み。

URLを入れるだけで、取得 → 解析 → レポート生成 → 公開 までが自動。

## 構成

| ファイル | 役割 |
|---|---|
| `run_report.py` | URL → チャット取得 → 解析 → `report_<id>.html` と `<id>.meta.json` を生成 |
| `build_index.py` | `*.meta.json` を集約して `reports.json` を作る |
| `index.html` | `reports.json` を読み、各レポートをタブ表示するギャラリー |
| `.github/workflows/generate-report.yml` | URLを入力するとActions上で上記を実行し自動コミット |

外部API・APIキー・クォータは一切不要(yt-dlpがチャットリプレイを取得)。

---

## セットアップ(初回のみ)

### 1. リポジトリを作る
GitHubで新規リポジトリ(例: `dmps-chat-gallery`)を **Public** で作成し、
この4ファイル + `.github/` をそのまま push する。

```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/<あなた>/dmps-chat-gallery.git
git push -u origin main
```

### 2. GitHub Pages を有効化
リポジトリの **Settings → Pages** で
Source = `Deploy from a branch`、Branch = `main` / `(root)` を選んで保存。
数分で `https://<あなた>.github.io/dmps-chat-gallery/` が公開される(これが共有リンク)。

### 3. Actions の書き込み権限を許可
**Settings → Actions → General → Workflow permissions** で
`Read and write permissions` を選んで保存。
(workflowが自動コミットするために必要)

---

## 使い方(レポート追加)

1. リポジトリの **Actions** タブを開く
2. 左の **Generate Chat Report** を選ぶ
3. **Run workflow** を押し、YouTubeのURLを貼って実行
4. 1〜数分で完了 → ギャラリーに新しいタブが自動追加される

公開リンクを開けば、誰でも全レポートをタブで閲覧できる。

---

## ローカルで作る場合(Actionsを使わない/確実な方法)

GitHubのクラウドIPはYouTube側のbotチェックに引っかかることがある。
その場合はローカルで生成して push すれば確実:

```bash
python3 -m pip install --user yt-dlp janome   # 初回のみ
python3 run_report.py "https://www.youtube.com/watch?v=XXXXXXXX"
python3 build_index.py
git add -A && git commit -m "add report" && git push
```

---

## 注意

- 対象は**配信終了後(アーカイブ)**のリプレイチャット。配信中のものは取れない。
- スクレイピングなので、短時間に大量実行するとIP単位で一時制限されることがある。
  月次で数本〜十数本なら問題なし。
- 公開リポジトリにすると、投稿者のYouTube表示名(公開情報)もレポートに含まれる点だけ留意。
