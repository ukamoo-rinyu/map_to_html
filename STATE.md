# STATE.md — 開発経緯の引き継ぎメモ

各変更について「何を」「なぜ」「どう変えたか」を新しい順に追記する
（v0.3.0 指示書 §0 の共通指示）。次のセッション・別モデルはまずここを読むこと。

---

## 2026-07-23: 実機フィードバックで判明した2件を修正（v0.3.0 タスク2-2見直し・2-4バグ）

**ブランチ**: `sonnet/v030-ux-fixes`（下記「UX改善・バグ修正5件」の直後）
**担当**: Claude Code標準（Sonnet）

実際のQGIS環境（本物のレイヤー構成）でプラグインを試したユーザーから2件の指摘：

### 1. 背景地図ON/OFFの仕様変更（2-2の再解釈）
最初の実装は「出力したHTMLのレイヤーパネルに背景地図トグルを追加する」という
ランタイム方式だった。ユーザーからのフィードバック: 「背景地図のオンオフは、
html上のレイヤーでの操作ではなく、出力前の背景地図（ベースマップ）で有り無しを
決めるようにして」＝ HTML側ではなく**プラグイン側（生成前）**で決める仕様に変更。

- `ui/display_tab.py`: 表示設定タブの「背景地図（ベースマップ）」グループに
  「背景地図を表示する」チェックボックス（デフォルトON）を追加。OFFの間は
  地図タイルのコンボボックスを無効化。`get_settings()`が`basemapEnabled`を返す。
- `core/config_builder.py`: `config.display.basemapEnabled`を追加。
- `template/js/map-core.js::initMap`: `display.basemapEnabled !== false`の
  場合のみタイルレイヤーを生成・追加するよう変更（無効時は一切生成しない）。
- `template/js/layer-control.js`: 追加していた`addBasemapToggleItem`と
  そのための`hasBasemap`早期return分岐を完全に削除し、元の
  `if (!layersConfig || !layersConfig.length) return;`に戻した。

ブラウザで`basemapEnabled: true/false`それぞれ生成し、trueでは
`L.TileLayer`が1つ地図に存在／falseでは0個であること、どちらの場合も
出力側レイヤーパネルに「背景地図」という項目が一切現れないことを確認済み。

### 2. レイヤー並び替え機能の実際のバグ（2-4）
ユーザー: 「レイヤーの上下に移動させるボタンが、動きが変。htmlのレイヤー表示も
おかしくなっている。」→ 実機の9レイヤー構成（グループ入り・ラスター混在）で
確認したところ、**`_move_selected`自体のインデックス計算は正しかったが、
`_sync_labels_from_table`と`_remove_layer`の2箇所が表示順反転（前回の2-4修正）に
追従できておらず、テーブル行番号をそのまま`self._entries`の添字として使って
いた**ため、以下が発生していた:

- `_sync_labels_from_table`（`_move_selected`/`_remove_layer`/`get_layers()`の
  すべてが呼び出し前に実行）が、行を編集した際に**別のレイヤーのラベルへ
  誤って書き込む**→ 移動・削除・エクスポートのたびにラベルが少しずつ
  入れ替わっていく（「動きが変」の正体）。
- `_remove_layer`が選択した行と**異なるレイヤー**を`self._entries`から
  削除していた（同じ理由）。

修正: 変換ロジックを1箇所（`_entry_index_for_row(row)`、
`len(self._entries) - 1 - row`、自己逆関数）にまとめ、
`_sync_labels_from_table`・`_move_selected`・`_remove_layer`の3箇所すべてを
これ経由に統一。実際の画面のレイアウト（9行、グループ・ラスター混在）を
手でトレースし、リネーム→上へ移動、削除の両方で正しいレイヤーが
操作対象になることを確認済み（QGIS非依存のため実機での自動テストは不可、
手動トレースのみ）。

**教訓**: テーブル表示順を反転させる変更（2-4）は、`_move_selected`だけでなく
「テーブル行番号→`self._entries`添字」という変換が必要な**すべての**箇所を
洗い出す必要があった。1回目の実装では`_move_selected`しか直さず、
同じ変換が必要な`_sync_labels_from_table`/`_remove_layer`を見落としていた。
今後同様の「表示順だけ反転」系の変更をする際は、`self.table.`の全使用箇所を
grepしてから着手すること。

---

## 2026-07-23: UX改善・バグ修正 5件（v0.3.0 タスク2-1〜2-5）

**ブランチ**: `sonnet/v030-ux-fixes`（`feature/canvas-label-layer` からの派生。
2-1がFable5のCanvasラベル層 `FAG_LABEL_PLACEMENTS` に依存するため、そちらの上に積んだ）
**担当**: Claude Code標準（Sonnet）

指示書の運用は本来「1機能1ブランチ・1PR」だが、今回はGitHubへのpushを行わない
セッション内作業だったため、5件を1ブランチ・5コミット（タスクごとに1コミット、
`git revert <sha>` で個別に戻せる）にまとめた。実際にpush/PRを作る際は、必要なら
コミット単位でcherry-pickして分割することを推奨する。

### 2-1. ラベルクリックでポップアップ表示
`template/js/label-layer.js` に `initLabelClickPopup(map)` を追加（`main.js` から
`initLabelLayer` の直後に呼び出し）。ラベルはpointer-events:noneのCanvasに描画されて
いるため自分ではクリックを拾えず、`map`の`click`イベントの`containerPoint`を
`FAG_LABEL_PLACEMENTS`（Fable5が1-1/1-2で公開済み）にヒットテストする方式。

実際のマーカーを直接クリックした場合に、たまたま別マーカーのラベル矩形とも
重なっていて誤ったポップアップに横取りされないよう、`popupopen`イベントが
「同じクリックの中で」既に発火済みかを見て判定している（Leafletは実際に
クリックされたレイヤー自身のclickリスナー→ポップアップを開く処理を、
mapレベルのclickリスナーより先に実行するため、地図click時点で
`popupOpenedThisClick`が立っていれば「本物の地物を直接クリックした」ケースと
判断してラベルのヒットテストをスキップする）。ブラウザで実際に
`MouseEvent('click')`を合成発火して、(a)ラベルだけの位置→正しいポップアップが開く、
(b)マーカー本体クリック→横取りされず本体のポップアップのまま、(c)何もない場所→
何も開かない、の3パターンを確認済み。

### 2-2. 背景地図のON/OFF切り替え
`template/js/map-core.js::initMap`が生成する背景タイルレイヤーを
`map.fagBasemapLayer`に保持するよう変更。`template/js/layer-control.js`の
`initLayerControl`が、レイヤーパネル最上部に常に「背景地図」トグル項目を追加する
（`addBasemapToggleItem`。既存の`.fag-legend-tile`市松模様スウォッチを流用、
新規CSS不要）。データレイヤーが1件も無くてもパネル自体は表示されるよう、
早期returnの条件を`!hasBasemap && !hasLayers`に変更。ブラウザでチェックを外すと
CARTOタイルだけが消え、他のタイルレイヤーは残ることを確認済み。

### 2-3. 地図追加時の透過率の継承
これまで`core/tile_layer.py::extract_tile_style`はラスター/XYZレイヤーの
透過率を一切読み取っておらず、Web出力は常に不透明描画になっていた（未実装の
バグという扱い）。修正: `tile_layer.py`に`read_native_opacity(layer)`
（`layer.renderer().opacity()`、失敗時1.0）を追加し、`extract_tile_style`は
オプション引数`opacity_override`があればそれを、無ければQGIS側のネイティブ値を
`tile.opacity`として書き出す。`template/js/layer-control.js`の`style.tile`分岐で
`L.tileLayer(...)`に`opacity`オプションとして適用。

指示書が「デフォルト継承＋個別変更可の両対応が望ましい」としていたため、
`ui/data_tab.py`のテーブルに列（`COL_OPACITY`、ラスター行のみ`QSpinBox`0-100%、
ベクター行は`—`）を追加。新規にラスターレイヤーを追加した際のデフォルト値は
`_last_raster_opacity()`（テーブル内で直前に追加されたラスター行の値を継承）→
無ければ`tile_layer.read_native_opacity()`（QGIS側の値）の順にフォールバック。
`dialog.py`が`entry.get('opacity')`を`extract_tile_style`に渡す。
`ui/data_tab.py`の列変更が大きいため`get_layers()`のdocstringも更新済み。
ブラウザ確認: `opacity: 0.35`で生成したタイルレイヤーが実際に
`L.TileLayer`の`options.opacity`に反映されていることを確認。QGIS実機での
`layer.renderer().opacity()`取得自体はQGIS非依存のテスト環境のため未検証
（次回QGIS実機での確認が必要）。

### 2-4. レイヤー選択リストの並び順の分かりやすさ改善
内部のz-order/描画順ロジック（`self._entries`の並び＝`get_layers()`の順＝
`addTo(map)`呼び出し順）は一切変更せず、UI表示だけを反転。
- `ui/data_tab.py`: `_rebuild_table`が`reversed(self._entries)`でテーブル行を
  描画するように変更。`_move_selected(delta)`は表示行番号↔`self._entries`
  インデックスの変換式（`entry_index = n-1-row`、上へ移動＝`entry_index`を
  +1する方向）に書き換え。スタンドアロンのPythonスクリプトで
  2000パターンのランダム操作を検証し、選択追跡・重複/消失なしを確認済み
  （QGIS非依存、`test_harness`とは別にスクラッチパッドに作成、リポジトリ外）。
- `template/js/layer-control.js::renderLayerTree`: 各グループ階層内の
  `node.items`（葉レイヤー）の表示順のみ`.slice().reverse()`で反転。
  グループ自体の並び順（`node.order`）はQGISのレイヤーツリーのグループ順を
  意図的にミラーしている既存機能のため、あえて変更していない。

ブラウザで実際に3レイヤー（back/mid/front）を`self._entries`順で構成し、
生成されたパネルが「front, mid, back」の順（＝リスト上＝地図の最前面）で
表示されることを確認済み。

### 2-5. ポイントの縁線（アウトライン）が反映されないバグの修正
`core/style_extractor.py`側のストローク抽出自体は元から正しく動作していた
（`_extract_marker_style`が`strokeColor`/`strokeWidth`を取得できている）。
バグはJS側: `template/js/style-renderer.js::createStyledMarker`で、円形
（circle）マーカーは`L.circleMarker`の`color`/`weight`オプションで縁線が
描画されていたが、非円形（square/diamond/triangle/cross/star、CSSの
`clip-path`で切り抜くdivIcon方式）は塗り色の`<span>`を1つ描画するだけで、
縁線を描く仕組みが最初から存在しなかった。

修正: 非円形マーカーを「strokeColor色の全サイズ span」＋「fill色で
strokeWidth分だけ内側に縮めたspan」の2枚重ねに変更（`createStyledMarker`）。
2枚は`position:relative`な無変形の親要素の下に**兄弟要素**として置く
（`fag-shape-diamond`等のCSSクラス自身が`transform:rotate(45deg)`を持つため、
一方をもう一方の中にネストすると回転が二重にかかってしまう＝ひし形が
90度回転してしまうバグを避けるため）。中心座標が一致するよう
`innerOffset = (size - innerSize) / 2`で計算。`strokeWidth === 0`
（QGIS側でストロークなし設定）の場合は従来通りfill spanのみ。

ブラウザで実際に6形状（circle/square/diamond/triangle/cross/star）を
黄色地×赤縁（strokeWidth:4px）で生成し、全形状で縁線が視認できることを
スクリーンショットで確認済み。ホバーハイライト（`.fag-marker-hover`の
`transform:scale(1.3)`）が新しいネスト構造でも壊れていないことも確認済み。

### 検証方法・環境
`..\test_harness\gen_test_site.py`に加え、今回は小規模な手作り検証サイト
生成スクリプトをスクラッチパッドに作成（`verify_v030_ux.py` - 6形状マーカー・
ライン・半透明タイルレイヤーを持つ、目視確認しやすい構成）。1,530点データセットでも
再生成してズーム性能に回帰がないこと（1段あたり2.4〜6ms、Fable5の計測と同水準）、
ラベル配置数がz12で202件のまま変わらないことを確認済み。

**`.claude/launch.json`のdirectory変更はセッション中は反映されない**ことが
判明（`preview_start`は起動時にlaunch.jsonをキャッシュしている様子）。
実行中のプレビューサーバーに紐づくディレクトリを変えたい場合は
`preview_stop`→`preview_start`ではなく、**編集後に一度セッションが
launch.jsonを読み直すタイミング**（もしくは元のディレクトリ自体を更新）が
必要。次回同じ問題に遭遇したら、まず`preview_logs`やファイル内容の直接grepで
「サーバーが実際にどのファイルを返しているか」を疑うこと（本セッションでは
これに気づかず一時的に誤った検証結果を得た）。

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
