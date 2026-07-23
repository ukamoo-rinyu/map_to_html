# STATE.md — 開発経緯の引き継ぎメモ

各変更について「何を」「なぜ」「どう変えたか」を新しい順に追記する
（v0.3.0 指示書 §0 の共通指示）。次のセッション・別モデルはまずここを読むこと。

---

## 2026-07-23: ラベル描画をCanvas方式に全面変更（v0.3.0 タスク1-1・1-2）

**ブランチ**: `feature/canvas-label-layer`
**担当**: Claude Fable 5

### 何を
- `template/js/label-declutter.js`（DOMツールチップの間引き）を削除し、
  `template/js/label-layer.js`（単一Canvasへのラベル自前描画）を新設。
- `style-renderer.js` の `bindStyledLabel` はツールチップを bind せず、
  ラベル情報（marker / text / labelStyle / anchorGap）を
  `FAG_LABEL_REGISTRY` に登録するだけになった。
  `applyLabelTextStyle` / `buildHaloShadow` は不要になり削除。
- `style.css` の `.fag-label` ルール削除（DOMラベルが存在しなくなったため）。
- `core/html_builder.py` の `JS_MODULE_ORDER` を `label-layer.js` に更新。

### なぜ（実測データ）
1,530ポイントの合成データ（QGIS非依存で `html_builder.build_output` を直接
呼ぶテストハーネスで生成）で計測した結果:

| 指標 | 変更前 | 変更後 |
|---|---|---|
| ズーム1段の同期ブロック時間 | **約1,000〜1,230ms** | **3〜6ms** |
| ラベル配置パス（全域表示 z12） | 366ms | 4.8ms |
| 低ズーム(z12)で表示されるラベル数 | 86（厳密衝突判定） | 202（重なり許容） |

原因は Leaflet の permanent tooltip。ツールチップは1つずつが DOM ノードで、
`setZoom` の中で全数が同期的に再配置される。1,530個で毎ズーム約1.1秒の
ブロックになっていた（全ツールチップを unbind すると同じ操作が10〜40msに
なることを確認済み＝ボトルネックのほぼ100%がツールチップ）。

### どう変えたか
- 専用ペイン（zIndex 650 = markerPane より上、popupPane より下、
  pointer-events: none）に `<canvas>` を1枚置き、
  `zoomend / moveend / resize / layeradd / layerremove` で
  requestAnimationFrame にまとめて再描画。
- テキスト寸法は `ctx.measureText`（レイアウト読み取りなし）で計測し、
  ラベルごとに1回だけキャッシュ。ハローは `strokeText`（lineJoin: round、
  lineWidth = buffer.width × 2）で QGIS のバッファを再現。
- **タスク1-2（ラベル早期表示）**: 衝突判定は各ラベルの矩形を中心方向に
  縮めた矩形（`FAG_LABEL_COLLISION_INSET_X = 0.2` / `_Y = 0.25`）同士で
  行う。→ 多少の重なりを許容し、低ズームから約2.4倍のラベルが見える。
  0 に戻せば従来の厳密判定に戻る（調整ノブとしてファイル先頭に定数化）。
- 重複座標を円状に散らした点（`fagLabelMultiDirection`）の
  右/左/下への再配置ロジックは、キャッシュ済み寸法の算術のみで従来同様に動く。

### 互換性・確認済みの点
- ポップアップ（クリックで内容表示）、ホバーハイライト、レイヤーON/OFF
  （OFFでラベルも消えONで復帰）、重複座標スプレッドは全て動作確認済み。
- 最新パスで配置されたラベルの矩形は `FAG_LABEL_PLACEMENTS`
  （{marker, rect}、コンテナ座標px）に公開してある。
  **→ タスク2-1（ラベルクリックでポップアップ）はこの配列を
  map の click ハンドラでヒットテストすれば実装できる**（Sonnet向けメモ）。
- `zoomAnimation: false`（v0.2.0で導入）は維持。ツールチップ消滅により
  アニメーションを戻せる可能性はあるが、既知の安定状態を優先し未変更。
  戻す場合は多段ズーム連打で要再計測。

### テストハーネス
`..\test_harness\gen_test_site.py`（リポジトリ外、QGISwebgene フォルダ直下）で
1,530点＋ポリゴン6件の分割ファイル出力を QGIS 非依存で生成できる
（`html_builder.build_output` を直接呼ぶ）。生成先を `python -m http.server` で
配信し、ブラウザコンソールから `map.setZoom` 前後の `performance.now()` を
計測した。v0.3.0 の残タスク（検索・一覧表など）の検証にもこれを使うこと。

---

## それ以前（v0.2.0 まで）

STATE.md は v0.3.0 作業開始時に新設。過去の経緯は git log と
各ファイルのコメント（実測値付き）を参照。
