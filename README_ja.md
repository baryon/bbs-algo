# BBS-Algo

**行動制約署名：AIエージェントの安全性を暗号学で担保する**

[中文](README_zh.md) | 日本語 | [English](README.md)

---

BBS-Algoは、**行動制約署名（Behavior-Bounded Signatures, BBS）**の概念実証実装です。ソフトウェア層のガードレールに依存する従来のアプローチとは異なり、BBSはポリシー制約を署名メカニズム自体に組み込みます。ポリシー違反の操作は「コードでチェックされて拒否される」のではなく、**数学的に署名を生成することが不可能**になります。

## 課題

従来のAIエージェント認可アーキテクチャは、アイデンティティ検証と行動検証を分離しています：

```
秘密鍵 + 通常署名    →  「誰がこの操作を承認したか？」
ソフトウェア層 + ポリシーチェック  →  「この操作は承認されるべきか？」
```

エージェントが有効な鍵を保持している限り、その署名は暗号学的に有効です——操作がセキュリティポリシーに違反しているかどうかに関係なく。ポリシーチェックはソフトウェア層（ミドルウェア、ガードレール、プロンプト命令）に存在し、プロンプトインジェクション、コードの欠陥、サプライチェーン攻撃によってバイパスされる可能性があります。

BBSはこのギャップを解消します：**操作がポリシーに違反する場合、有効な署名は生成できません。**

## 動作原理

```
Agent → アクション → ポリシー制約署名器 → ポリシー充足？
                                          ├─ はい → 有効な署名を生成 → 検証器 → 実行
                                          └─ いいえ → 数学的に署名不可能 → 拒否
```

主要な特性：

- **アクションバインディング** — 署名は正規化されたアクション全体をカバーし、いかなるフィールドの改ざんも署名を無効化
- **ポリシーフィンガープリント** — 暗号学的ハッシュにより署名器と検証器が同一ポリシーバージョンを使用することを保証
- **リプレイ保護** — 各操作に一意のnonceをバインド
- **閉鎖実行パス** — 高リスク実行器は検証済み署名リクエストのみを受け付け、バックドアなし

## リポジトリ構成

```
.
├── paper/
│   ├── bbs.pdf                              # BBS原論文
│   └── behavior-constrained-agent-systems-paper.pdf
├── docs/
│   ├── bbs-paper-explained.md               # 論文解説
│   ├── bbs-application-memo.md              # エンジニアリング設計メモ
│   ├── bbs-engineering-implementation.md    # 実装ガイド
│   ├── behavior-constrained-agent-systems-paper.md
│   ├── ai-agent-safety-crisis-and-bbs-solution.md  # 業界背景とセキュリティ事例分析（中国語）
│   └── ai-agent-safety-crisis-and-bbs-solution-en.md  # 同記事の英語版
└── src/
    └── python/
        ├── bbs_payment_mvp.py               # 決済認可MVP
        ├── bbs_dev_guard_mvp.py             # 開発セーフティガードMVP
        ├── bbs_cybernetics_mvp.py           # 制御論フィードバックループMVP
        ├── run_payment_demo.py              # 決済デモランナー
        ├── run_dev_guard_demo.py            # 開発ガードデモランナー
        └── run_cybernetics_demo.py          # 制御論デモランナー
```

## クイックスタート

```bash
# 決済認可デモ
python3 src/python/run_payment_demo.py

# 開発セーフティガードデモ
python3 src/python/run_dev_guard_demo.py

# 制御論フィードバックループデモ
python3 src/python/run_cybernetics_demo.py
```

## MVPカバレッジ

### 決済認可

ポリシー：1回の取引上限200 USD、受取人はホワイトリスト内のみ。

| シナリオ | 結果 |
|---------|------|
| 有効な支払い（168.50 USD → vendor_123） | ✅ 承認 |
| 上限超過の支払い（243 USD） | ❌ 署名器が拒否 |
| ポリシーバイパス（攻撃者が直接署名） | ❌ 検証器がポリシー不一致を検出 |
| 不明な鍵 | ❌ 検証器が未登録公開鍵を拒否 |
| ペイロード改ざん（署名後に受取人を変更） | ❌ 署名検証失敗 |
| リプレイ攻撃（nonceの再利用） | ❌ 検証器がブロック |

### 開発セーフティガード

**データベース更新** — staging環境のみ許可、ホワイトリストテーブル/フィールド、単一行操作：

| シナリオ | 結果 |
|---------|------|
| staging / feature_flags / enabled / 1行 | ✅ 承認 |
| production / users / role / 一括更新 | ❌ 拒否 |

**ファイル削除** — sandbox/tmpパスのみ許可：

| シナリオ | 結果 |
|---------|------|
| /workspace/sandbox/\*\* | ✅ 承認 |
| /etc/passwd | ❌ 拒否 |

### 制御論フィードバックループ

BBSループが負帰還制御システムとしてどのように機能するかを実証します。エージェントは検証器のフィードバックに導かれながら、多次元の受入基準（品質、コスト、レイテンシ、リスク）に向けて反復的に収束します。

| シナリオ | フィードバックモード | 結果 |
|---------|-------------------|------|
| 精密フィードバック + 到達可能な目標 | 各次元の正確な偏差値 | ✅ 3〜4ラウンドで収束 |
| 粗フィードバック + 同一目標 | 違反理由のみ、偏差値なし | ❌ 反復回数内で収束せず |
| 精密フィードバック + 到達不可能な目標 | 正確な偏差値 | ❌ アクチュエータ限界に到達、停止 |
| フィードバックチャネルなし | 情報なし | ❌ 修正不可能、即時停止 |

## 論文とドキュメント

| ドキュメント | 説明 |
|-------------|------|
| [paper/bbs.pdf](paper/bbs.pdf) | BBS原論文 — PS-CMAセキュリティモデルと行動制約署名方式の形式的定義。Zenodo: https://zenodo.org/records/18811273。DOI: `10.5281/zenodo.18811273` |
| [paper/behavior-constrained-agent-systems-paper.pdf](paper/behavior-constrained-agent-systems-paper.pdf) | 行動制約エージェントシステム拡張論文。Zenodo: https://zenodo.org/records/18952739。DOI: `10.5281/zenodo.18952739` |
| [docs/bbs-paper-explained.md](docs/bbs-paper-explained.md) | 論文の主要概念の解説 |
| [docs/bbs-application-memo.md](docs/bbs-application-memo.md) | エンジニアリング設計メモ — BBSを「ハードバウンダリコントローラ」として実装する理由と実用的な展開の考慮事項 |
| [docs/bbs-engineering-implementation.md](docs/bbs-engineering-implementation.md) | 実装ガイド — アーキテクチャ層、アクションモデリング、本番ロードマップ |
| [docs/behavior-constrained-agent-systems-paper.md](docs/behavior-constrained-agent-systems-paper.md) | 論文Markdown全文 |
| [docs/ai-agent-safety-crisis-and-bbs-solution-en.md](docs/ai-agent-safety-crisis-and-bbs-solution-en.md) | AIエージェントのセキュリティ危機とBBSソリューション（英語） |
| [docs/ai-agent-safety-crisis-and-bbs-solution.md](docs/ai-agent-safety-crisis-and-bbs-solution.md) | 同記事の中国語版 |

## プロジェクトスコープ

本リポジトリは**エンジニアリング概念実証**です。制御フローの明確性と監査可能性を維持するため、完全なゼロ知識証明ではなくEd25519署名を使用しています。MVPは、ポリシーバインディング、アクションバインディング、リプレイ保護、構造化拒否フィードバック、およびフィードバック精度に基づく制御論的収束のもとで `Agent → 署名器 → 検証器 → 実行器` ループのエンドツーエンドの実現可能性を検証しています。

未実装：ZK証明回路、オンチェーン検証、コンセンサスプロトコル、本番レベルの鍵管理、ネットワークサービスラッパー。

## ライセンス

MIT
