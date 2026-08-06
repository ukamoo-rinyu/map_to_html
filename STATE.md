# STATE.md — 開発経緯の引き継ぎメモ

各変更について「何を」「なぜ」「どう変えたか」を新しい順に追記する
（v0.3.0 指示書 §0 の共通指示）。次のセッション・別モデルはまずここを読むこと。

---

## 2026-08-06: v0.4.1（最大ズームでタイルが消える不具合＋Bandit指摘）

**担当**: Claude Code（Opus）

v0.4.0 をplugins.qgis.orgに上げたところ **Banditのセキュリティチェックで
ブロック**された。あわせてユーザーから「最大ズームにすると単色地図や
Google航空写真が表示されなくなる」との報告。

### 1. 最大ズームでタイルレイヤーが消える（実バグ）

**原因**: `layer-control.js` のタイル分岐が `maxZoom: style.tile.maxNativeZoom`
としていた。Leafletのこの2つは意味がまったく違う:

| オプション | 意味 |
|---|---|
| `maxZoom` | **このズームを超えるとレイヤーが表示されなくなる** |
| `maxNativeZoom` | 実タイルが存在する最深ズーム。これを超えるとLeafletが拡大表示する |

QGISのXYZソースの `zmin`/`zmax` は「タイルが存在する範囲」なので
**Native側にしか入れてはいけない**。`maxZoom` に入れると、そのズームを
超えた瞬間にレイヤーごと消える（＝拡大表示にならない）。

**修正**: `minNativeZoom`/`maxNativeZoom` にソースのzmin/zmaxを入れ、
`minZoom`/`maxZoom` は地図自身の範囲（`map.getMinZoom()`/`getMaxZoom()`）に
合わせる。同じ問題が `map-core.js` の組み込みベースマップにもあった
（`Object.assign({maxZoom:...}, basemap.options)` の順序で
`basemap.options` 側が `maxZoom` を上書きできてしまう状態）ので、
順序を逆にして地図側の値が必ず勝つようにし、CARTO(20)/OSM(19)にも
`maxNativeZoom` を明示した。

**検証**: zmax18のXYZレイヤー＋最大ズーム21の地図で実測。
修正後は z19/20/21 でもタイルがDOMに存在（拡大表示）。同じレイヤーを
**旧設定（maxZoom:18）で作り直すと z21 でDOM上のタイルが0枚**になることも
確認し、原因が確定した。

### 2. Bandit指摘 2件

- `core/layer_utils.py` の `field_aliases`: `except Exception: continue`（B112）
- `dialog.py` の `_resize_to_fit_screen`: `except Exception: pass`（B110）

どちらも**try/exceptをやめて明示的なチェックに置き換えた**（`hasattr(layer,
'fields')` / `if screen is not None`）。抑制コメント（`# nosec`）は使っていない。
本当に握りつぶしていたのは「ラスターレイヤーにfieldsが無い」「ヘッドレス環境で
primaryScreen()がNone」という**事前に判定できる条件**だけだったので、
例外で受けるより明示チェックの方が正しい。

補足: 他の `except ValueError: pass` 等（`tile_layer.py`）は型付き例外なので
BanditのB110/B112は既定で検出しない（`check_typed_exception` が既定False）。
`python -m bandit -r . -x ./template` で **No issues identified** を確認済み。

---

## 2026-08-05: v0.4.0 第1弾（指示書の優先度A/B項目）

**ブランチ**: `feature/v0.4.0-fidelity-ux`（`main`から分岐、未マージ・未プッシュ）
**担当**: Claude Code（Opus）
**元資料**: `facility_app_generator_next_spec.md`（Downloads）

### 着手前の棚卸し（重要）

指示書は優先度Sに「8. 読み込み速度の改善」を置いていたが、実際のコードを
確認したところ**大半が実装済み**だった:

| 指示書の項目 | 実際の状態 |
|---|---|
| 8-① 座標桁数を6桁に丸める | 実装済（`geojson_writer.py` の `COORDINATE_PRECISION=6`） |
| 8-② 不要な属性を出力しない | 実装済（`field_config.py` のフィールドピッカー） |
| 8-③ ジオメトリ簡略化 | 実装済（`SIMPLIFY_TOLERANCE_DEG`） |
| 8-⑤ Canvas レンダリング | 実装済（`map-core.js` の `renderer: L.canvas()`） |
| 8-④ JSON.parse 方式 | **未実装** |
| 8-⑥ レイヤーの遅延読み込み | **未実装** |
| エスケープ処理 | 実装済（`escapeHtml` / `_json_for_inline_script`） |
| Qt6・QGIS4 対応 | v0.3.2 で実装済 |

そのため今回は優先度A・Bの項目から着手した。残りは下の「未着手」を参照。

### 2. ポリゴン透過率の反映（優先度A）

**問題**: QGISの透過が3か所に分散していて、そのうち**塗りつぶし色のアルファ値
しか読んでいなかった**ため、半透明のポリゴンがべた塗りで出力されていた。

最終不透明度 = 色のアルファ × `QgsSymbol.opacity()` × `QgsMapLayer.opacity()`
を掛け合わせるよう `style_extractor.py` を修正（`_color_alpha`/`_symbol_opacity`/
`_layer_opacity` を新設）。さらに:

- **塗りと枠線で独立した不透明度**を出力（`fillOpacity`/`strokeOpacity`、
  マーカーは `opacity`/`strokeOpacity`）。従来は1つの値を両方に使い回して
  いたので、塗りを透過させると枠線まで消えていた
- `Qt.NoBrush`→`hasFill:false`、`Qt.NoPen`→`hasStroke:false` を明示出力し、
  JS側で Leaflet の `fill:false`/`stroke:false` に対応付け
- **`dashArray` を Qt のペンスタイルから生成**（`_QT_DASH_PATTERNS`）。従来は
  `dashed` の真偽値だけで、破線・点線・一点鎖線がすべて同じ `'6,4'` だった。
  Qtの破線パターンは線幅の倍数で定義されるので px に換算している。
  カスタム破線パターン（`useCustomDashPattern`）にも対応
- 表示設定タブに**「塗りの透過率を上書きする」チェックボックス＋スライダー**を
  追加。**プラグイン側（生成前）の設定**で、出力HTMLにはトグルを増やさない
  （既存方針どおり）。枠線には適用しない＝形が読めなくなるのを避けるため

### 3. カテゴリ値による定義の反映（優先度A）

`byCategory` 自体は既存だったが、以下が欠けていたので追加:

- **`renderState()` が False のカテゴリ**（QGISでチェックを外した分類）の地物を
  **エクスポート自体から除外**。スタイル表から消すだけだと fallback スタイルで
  復活してしまうため、`build_render_filter()` を新設して
  `geojson_writer.py` の `feature_filter` で地物ごと落とす。検索・一覧表からも
  同時に消える
- **`cat.label()`（凡例ラベル）**を出力し、レイヤーパネルに**カテゴリ単位の凡例**を
  描画（`categoryLegend` → `buildCategoryLegendHtml`）。従来はカテゴリ分類の
  レイヤーでも凡例スウォッチが1個だけで、しかもそれは無関係な1カテゴリの色だった
- **「その他すべての値」（value=`''`）を明示的に fallback として採用**。従来の
  fallback は `renderer.symbols()[0]`＝たまたま先頭にあったカテゴリの
  スタイルで、QGISの実際の描画と一致していなかった
- QGISのNULL（`QVariant`）は `str()` すると `"NULL"` になるので `_is_null()` で
  判定。真偽値も Python の `True` ではなく JSON の `true` に揃える
- 「分類値→スタイル」を引く箇所を `_style_for_symbol()` に集約（指示書の
  「次の一手」＝Graduated 対応の布石）

### 7. ポップアップの表示調整（優先度A）

- **縦積みレイアウトに変更**（`.fag-popup-row` を `display:flex`→`block`、
  項目名は小さいグレーで上、値は通常サイズで下）。列名がどれだけ長くても
  崩れなくなる
- `max-width:320px; max-height:400px; overflow-y:auto; word-break:break-word`
- **フィールド別名（alias）を使用**（`layer_utils.field_aliases()` →
  `config.layers[].fieldAliases`）。別名が設定されている項目だけを出力するので
  config.js が無駄に膨らまない
- 空値の表示ON/OFF、`http`で始まる値のリンク化（画像URLは`<img>`）を
  表示設定タブに追加。リンク化は `^https?://` のみ＝データ中の
  `javascript:` がリンクにならないようにしている

### 11. Googleマップリンク（優先度B）

表示設定タブに親チェックボックス＋Googleマップ/ストリートビュー/経路/
施設名検索/地理院地図。既定は指示書どおりマップ・SVのみON。
面・線は**頂点座標の平均（重心）**を使用（`fagFeatureLatLng`）。
座標は6桁、`encodeURIComponent`、`target="_blank" rel="noopener noreferrer"`。
親チェックOFF時は**リンクのHTMLを一切出力しない**（DOMにも残さない）。

### 1. スケールバー（優先度B）

表示設定タブにチェックボックス＋表示位置（左下/右下）。OFF時は
`config.display.scaleBar` が `null` になり `applyScaleBar` が何もしない
＝コードごと出力されない。

### 5. 現在のQGIS画面範囲を初期表示に（優先度B）

初期表示のラジオボタンに3つ目を追加。`iface.mapCanvas()` の extent を
プロジェクトCRS→EPSG:4326 に変換して `initialView.mode='bounds'` として
出力し、Leaflet側は `fitBounds`（ズームが整数段階なので中心+ズームより
一致しやすい）。縦横比の違いはツールチップで注記。
extent が読めない場合は autoFit にフォールバック。

### 4. 書式設定の再読み込み（優先度B）

ダイアログは**すでにモードレス**だった（`plugin.py` が `show()` を使用）。
意図を明示するため `setModal(False)` を追加。

調べたところ、開いたまま古くなるのは指示書の想定より狭い:
**シンボル・ラベル・凡例はHTML生成時に毎回ライブのレイヤーから読み直して
いる**ので、QGISで色を変えただけなら再読み込みなしで反映される。
実際に固定化されているのは (1) フィールド一覧（ポップアップ項目の設定）、
(2) レイヤー名・グループ名、(3) レイヤーの増減。

`reload_from_project()` を新設し、**レイヤーIDをキーに**表示順・編集した
ラベル・ポップアップ項目の表示/並び順・ラスター透過率・両チェックボックスを
すべて保持したままマージする。ラベルは `auto_label` と比較して
「ユーザーが変更したか」を判定し、変更していなければQGIS側の改名に追従する。
削除されたレイヤーは除外、QGISで新たに表示にしたレイヤーは追加し、
結果をダイアログで要約表示する。

### 検証

QGIS非依存の検証サイト（scratchpad の `gen_v040_verify.py` → `html_builder.
build_output` を直接呼ぶ）を作り、ローカルサーバ＋`javascript_tool` で実測:

- 透過: ポリゴン `fillOpacity:0.3 / opacity(枠線):1.0 / dashArray:"12.0,6.0"`、
  ライン `opacity:0.45 / dashArray:"16.0,8.0"` が Leaflet のオプションに
  到達していることを確認（Canvasレンダラなので SVG 属性ではなく
  `map._layers[].options` を確認）
- カテゴリ凡例: 3行が正しいラベル（図書館／公民館（半透明）／その他すべての値）で
  描画され、半透明カテゴリのスウォッチが `rgba(...,0.35)` になることを確認
- divIcon（四角）マーカーが**塗り0.35・枠線1.0**の2スパン構成で描画されることを確認
- ポップアップ: 別名（`SISETU_MEI`→施設名称）が効く／空値が非表示／
  URLがリンク化／`& <b>` が `&amp; &lt;b&gt;` にエスケープされ `<b>` が
  0個（＝HTMLインジェクションなし）／日本語施設名が
  `encodeURIComponent` されることを確認
- 面のリンク座標が第1頂点ではなく**重心** (34.695,135.505) になること、
  名称フィールドを持たないレイヤーでは検索リンクが出ないことを確認
- スケールバーが `leaflet-bottom leaflet-left` に出ること
- `initialView.mode='bounds'` が要求範囲を包含すること（`containsRequested:true`,
  zoom 15）

**ハマりどころ**: 初回計測で `map.getSize()` が 0x0 を返し fitBounds が
minZoom に落ちた。`invalidateSize()` 後は正常。これはブラウザペインが
非表示のときの計測アーティファクトで、既存の autoFit も同じ経路なので
今回の変更由来ではない（両方を実測して同一結果になることを確認済み）。

### 実機テストで見つかった3件を修正（同日）

ユーザーが実際のQGIS（未利用地一覧.qgz、9レイヤー）で確認。
**優先確認をお願いした3点（透過率・非表示カテゴリ・再読み込み）はいずれもOK。**
一方、今回の追加が原因の表示崩れが3件あった:

1. **プラグインのウィンドウが縦に長すぎて下端が画面外**（移動もできない）。
   表示設定タブに5つのグループを足したことで、レイアウトの最小高さが
   1080pの画面を超えてしまった。QDialogはレイアウトの最小サイズより
   小さくできないため、生成ボタンと閉じるボタンに手が届かない状態に。
   → `display_tab.py` の中身を **QScrollArea** に入れ、ダイアログの最小高さと
   タブの内容の高さを切り離した。あわせて `dialog.py` に
   `_resize_to_fit_screen()` を追加し、初期サイズが画面の作業領域を
   超えないようにクランプ（今後さらに設定が増えても同じ事故が起きない）。
2. **スケールバーが一覧表と重なる**。どちらも左下が定位置だった。
   → `.fag-has-feature-table` クラス（`display-settings.js` が付与）で
   Leafletの左下コントロール枠を一覧表パネルの右隣（`margin-left:372px`）へ
   ずらす。**上へ逃がさなかった理由**: 一覧表は上方向に伸びるので、上に
   積むと開いた瞬間に隠れる。パネルの幅は360px固定なので横にどける方が安定。
   幅520px以下では横に置けないのでメディアクエリで上（`margin-bottom:44px`）に
   切り替える。
3. **カテゴリ分類レイヤーのチェックボックスがずれる**。`.fag-layer-item` を
   `flex-wrap:wrap` にしたせいで、長いレイヤー名が独自のflex行に折り返され、
   チェックボックスとスウォッチだけが上の行に取り残されていた。
   → チェックボックス＋スウォッチ＋レイヤー名を `.fag-layer-item-row` で
   1行にまとめ、`<li>` 自体は `display:block` に戻してカテゴリ一覧を
   その下の兄弟要素にした。あわせて、**凡例ラベルが空のカテゴリ**（QGISの
   「その他すべての値」は無名のことが多い）がスウォッチだけの空行に
   見えていたので、`label || value || '(other)'` でフォールバックするように。

検証: 検証サイトを長いレイヤー名＋無名の catch-all カテゴリで再生成し、
`getBoundingClientRect()` で実測 —
チェックボックス/スウォッチ/ラベルが同一行に収まる（ラベルは2行に
折り返しても垂直中央）、カテゴリ一覧はその下、スケールバー(left377-453)と
一覧表パネル(right=370)が非重複、375px幅ではメディアクエリでスケールバーが
パネルの上（bottom763 ≤ panel top768）に退避することを確認。
※ 1のQScrollAreaはQt側なのでブラウザでは検証不可、実機確認が必要。

### v0.4.0 第2弾: 8-④ / 進捗表示 / 項目9（2026-08-05、同日）

**8-④ `<script type="application/json">` + `JSON.parse`**
単一HTML出力を `const layersData = {...}` のオブジェクトリテラルから
`<script type="application/json">` ＋ `JSON.parse` に変更。既存の
`_json_for_inline_script`（`</` → `<\/`）はそのまま使える —
**JSONは `\/` をソリダスのエスケープとして明示的に許可している**ので、
同じ文字列がJSとしてもJSONとしても妥当。

**分割出力（config.js/layers.js）はあえて据え置き**。`<script src>` で
読むため同じ手を使うには (a) `fetch()`（file:// ではCORSで不可＝共有
フォルダから開く運用と真っ向から衝突）か (b) JSONをJS文字列リテラルに
二重エンコード（全ての `"` がエスケープされてファイルが膨らむ＝そちらで
効く転送量削減と逆行）のどちらかになる。コード内にも明記済み。

**進捗表示**: `base.html` に `#loading-overlay` を**初期マークアップとして
可視状態で**追加（スクリプトが動く前に描画される＝真っ白画面の解消）。
ただの飾りにしないため、`initLayerControl` を **1レイヤー＝1イベント
ループターン**（`setTimeout(step, 0)`）に変更した。`setTimeout` は
待ち時間ではなく**ブラウザに描画の機会を返すためのyield**。

→ これに伴い `initLayerControl` に `onComplete` コールバックを追加し、
`main.js` は `initLabelLayer`/`initLabelClickPopup`/`initSearch`/
`initFeatureTable`/`initSelection` をその中で呼ぶよう変更。
**理由**: レイヤー構築が複数ターンに分かれたので、`FAG_FEATURES_BY_LAYER`
（検索・一覧表）と `FAG_LABEL_REGISTRY`（ラベル）は次の行では
まだ埋まっていない。

**項目9: 選択モードとCSV/GeoJSON出力**（新規 `template/js/selection.js`）
- 選択状態は `FAG_SELECTION = {layerId: {fid: true}}`
- **強調表示は別オーバーレイレイヤーで描く**（元の地物を `setStyle` しない）。
  理由: `style-renderer.js` の `bindHoverHighlight` は各レイヤーの
  ベースライン options をスナップショットして mouseout で復元し、
  `fagUpdateMapUnitWeights` はズームごとに `weight` を書き換えるので、
  同じ options を触る選択表示はどちらにも黙って打ち消される
- クリック選択／Ctrl+クリックで追加・解除／矩形選択（面・線はバウンディング
  ボックスの交差判定＝指示書どおり）／一覧表の行クリックとの双方向同期
- CSV: **BOM付きUTF-8**、別名ヘッダ、`,`/`"`/改行のクォート、
  緯度経度列の自動付与（面・線は重心、ポップアップのGoogleリンクと同じ
  `fagFeatureLatLng` を共用するので値が食い違わない）、
  ゼロ始まりコードの `="0123"` 形式（設定でON/OFF）
- GeoJSON: `crs` メンバなし（RFC 7946）、整形の有無を設定可
- 5000件超で確認ダイアログ、ファイル名に日時
- **選択CSVはレイヤーごとに別ファイル**にした。選択は複数レイヤーに
  またがれるが列構成が違うので、1ファイルにまとめると全レイヤーの
  フィールドの和集合＋大量の空欄になり、ヘッダが意味をなさなくなる

**検証中に見つけて直した実バグ**: Leafletは地物クリック時に
**そのレイヤーの 'click' の後にマップの 'click' も発火**する。
そのため「空きマップのクリックで選択解除」ハンドラが、直前に地物
ハンドラが作った選択を即座に消していた（＝通常クリックでの選択が
まったく効かない）。`event.originalEvent` の同一性で「同じ物理クリック」を
判定して回避（フラグやタイマーと違い、propagationが止まってマップ
クリックが来なかった場合に状態が残らない）。

**検証**: 単一HTML出力をブラウザで実測 —
JSON.parse経路で3レイヤー読み込み・ローディングオーバーレイ除去を確認。
選択: 通常クリックで選択→Ctrl+クリックで解除→再クリックで選択→
本当に何もない場所のクリックで解除、の一連が正しく動くことを
canvas要素への合成MouseEventで確認（**マップコンテナではなくcanvas要素に
dispatchする必要がある** — Canvasレンダラのリスナはcanvas側にあり、
イベントは上へバブルするので親に投げても届かない）。
CSV: 別名ヘッダ・緯度経度列・`"A,B ""quoted"""`・改行含みセル・
`="0123"` を実出力で確認。面レイヤーの緯度経度が重心(34.695,135.505)に
なることも確認。GeoJSON: `crs`なし・`_fid`/`label_text`除去を確認。
一覧表の行ハイライトはハイライト適用を確認済み（ただし
**ブラウザペイン非表示時は `requestAnimationFrame` が発火せず**
`scheduleRowRender` の再入ガードが立ちっぱなしになるため、
rAFを同期実行にモンキーパッチして検証した）。

### v0.4.0 第3弾: 項目6 間引き表示（2026-08-05、同日）

ユーザーから「8-⑥は無理に対応しなくていい」との判断。残りの優先度C
（6・10）に着手。

**6-A レイヤーごとのズーム表示範囲**
`layer_utils.scale_visibility_zoom_range()` を新設し、QGISの
「縮尺に応じた表示設定」（`hasScaleBasedVisibility()`/`minimumScale()`/
`maximumScale()`）をLeafletのズームレベルに換算する。
**QGISと web地図で用語が逆なので注意**: QGISの `minimumScale` は
「最も引いた（分母が大きい）縮尺」＝レイヤーの**最小ズーム**に対応する。
ここを取り違えると、表示すべきズームでちょうど隠れる挙動になる。
換算はズーム0の縮尺分母 559082264.028 を基準（96dpi・赤道）。QGISは
画面中心緯度で縮尺を測るので厳密には一致しないが、「だいたいこの辺から
表示」の用途には十分で、レイヤーごとに手で上書きもできる。

データ設定タブに **最小ズーム列**（`COL_MIN_ZOOM`、0＝制限なし）を追加。
QGIS側に設定があれば換算値が初期値として入る。

**6-B 点データのグリッド間引き**
表示設定タブに「広域表示のときポイントを間引いて表示する」＋閾値ズーム＋
格子サイズ(px)。閾値未満のズームで、1マスにつき1件だけ描画する。

設計上のポイント2つ:
- **格子は画面px空間ではなく「現在ズームでの度数」で切る**。画面空間で
  切るとパンのたびに表示される点が入れ替わってチラつき、moveendごとに
  全件パスが走る。度数固定なら zoomend だけで済み、パンしても表示が動かない
- **間引くのは描画だけ**。`L.geoJSON` グループからマーカーを add/remove
  するだけなので `FAG_FEATURES_BY_LAYER` は無傷＝検索・一覧表・CSV出力には
  常に全件が入る（指示書が「避けるべき」と名指ししている点）。
  ラベルは `label-layer.js` が既に `if (!marker._map) return;` で
  地図上にないマーカーを飛ばすので、間引いた点のラベルも自動で消える

**チェックボックスとズーム範囲の競合を1か所に集約**: `FAG_LAYER_VISIBILITY`
に「ユーザーの意思(checked)」を持たせ、`fagApplyLayerVisibility()` が
それとズーム範囲のANDで地図への出し入れを決める。これをやらないと
(a) ズーム変更がユーザーの外したチェックを復活させる、
(b) 範囲外でチェックを入れると強制的に表示される、の両方が起きる。
再表示時は設定順に `bringLayerToFront` を流し直してクリック優先順位を復元。

**「一部の地物のみ表示中」の表示は必須**（黙って消すとデータ欠損に見える）
→ `#thinning-notice` を上部中央に。`pointer-events:none` でクリックを
奪わない。

**検証**: 600点の密集レイヤー＋minZoom15のレイヤーで実測。
z11→9件 / z12→16件 / z13→63件 / z15→600件（間引き解除）と段階的に増え、
通知バナーの表示/非表示も一致。**全ズームで `FAG_FEATURES_BY_LAYER` は
600件のまま**であることを確認（＝検索・出力は無傷）。
6-Aのレイヤーは z15 でのみ地図に載り、チェックは入ったまま。
チェックとズームの競合も実測: z15でチェックを外す→ズーム往復しても
復活しない、範囲外でチェックし直しても即表示されない、範囲内に戻ると
表示される、を確認。

### v0.4.0 第4弾: 項目10 斜線（パターン）塗りつぶし（2026-08-05、同日）

**前提の設計変更: レンダラをレイヤーごとに選ぶ**
SVG `<pattern>` はCanvasレンダラでは使えない。`map-core.js` の
`renderer: L.canvas()`（マップ全体）はそのまま残し、**パターン塗りが必要な
レイヤーだけ** `L.svg()` を渡すようにした（`buildStyledLayer` に
`patternRenderer` 引数を追加）。斜線塗りのレイヤー（区域界・用途地域など）は
件数が少ないので、性能と見た目を両立できるという指示書の判断どおり。

**専用ペインに入れた理由（重要）**: SVGレイヤーと共有canvasを同じ
overlayPane に入れると、両者は兄弟要素なので**重なり順がDOMの生成順**に
なり、設定したレイヤー順に従わない。斜線の背景ポリゴンがポイントの上に
来てクリックを奪う事故が起きうる。`fagPatternPane`（zIndex 395、
overlayPaneの400の直下）に固定することで「斜線塗り＝背景」という
予測可能な結果にした。

**新規 `template/js/fill-pattern.js`**
- (A) Qtブラシスタイル: `_QT_BRUSH_PATTERNS`（Python側）で
  bdiag/fdiag/diagcross/hor/ver/cross/dense1〜7 に対応付け。
  角度は `patternTransform="rotate()"` で付ける
- (B) `QgsLinePatternFillSymbolLayer`: `lineAngle()`/`distance()`/
  `lineWidth()`/`color()` を読んで `<pattern>` を動的生成。
  **角度の符号**: QGISのlineAngleは水平から時計回り、SVGの
  patternTransform rotate() も画面座標系（y下向き）で時計回りなので、
  符号反転は不要（指示書の「要確認」項目）
- `patternUnits="userSpaceOnUse"` ＝ ズームしてもパターンの目が
  詰まったり広がったりしない
- **同じスタイルなら1つの定義を使い回す**（スタイル値をキーにした
  `FAG_PATTERN_IDS`）。地物ごとに作らない
- **Leafletの `_updateStyle` が `fill` 属性を上書きする**ので、
  `setStyle` をラップしてパターンを再適用している。これがないと
  ホバー効果やマップ単位の線幅再計算のたびに斜線がベタ塗りに戻る
- **凡例スウォッチは自前の `<defs>` を持つインラインSVG**。凡例は
  地図の `<svg>` の外にある通常のDOMなので、地図側の defs を参照できない
  （指示書が「忘れやすい」と書いている点）

**(C) 未対応パターンは警告する**: `QgsPointPatternFillSymbolLayer`/
`QgsSVGFillSymbolLayer`/`QgsRasterFillSymbolLayer`/
`QgsRandomMarkerFillSymbolLayer` はべた塗りにフォールバックし、
`extract_style(warnings=[])` に警告を積んで `dialog.py` の完了ダイアログに
「以下は見た目が変わっている可能性があります」として表示する
（黙って見た目が変わるのが一番困る＝指示書10-C）。

**既知の制限**: `symbolLayer(0)` しか読まないので、線パターン塗りの下に
別の輪郭シンボルレイヤーを重ねたポリゴンは、その輪郭が出力されない。

**検証**: Qtブラシ10種＋線パターン(30度/12px間隔)＋通常塗りの
12レイヤーで実測。
- `fagPatternPane` の zIndex 395 < overlayPane 400 を確認
- `<pattern>` 定義が11個、すべて `userSpaceOnUse`。bdiag=rotate(-45)、
  fdiag=rotate(45)、diagcross=rotate(45)+2本、hor/ver=1本・回転なし、
  dense1=3x3 → dense7=13x13 と間隔が広がることを確認
- 線パターンが 12x12 / rotate(30) / 1本 = 指定どおり
- 斜線11レイヤーのpathがすべて `fill="url(#...)"` を参照
- **通常塗りのポリゴンはCanvasのまま**（SVGペインに入っていない）＝
  レンダラの使い分けが効いている
- **`setStyle`・mouseover・mouseout の後もパターンが維持される**ことを確認
  （ラップが効いている）
- 同一スタイルで `fagEnsurePattern` を2回呼んでも定義が増えない（dedup）
- 未知のパターン種別は null を返す＝呼び出し側がべた塗りに落ちる
- 凡例スウォッチ11個がすべて `<pattern>` を内包し `url(#)` を参照

### 未着手（指示書の残り）

**指示書の11項目はすべて実装済み**（8-⑥ を除く。ユーザーが2026-08-05に
「8-⑥は無理に対応しなくていい」と明示的に見送り）。

- **8-⑥** レイヤーの遅延読み込み … ユーザー判断により見送り

**8-⑥ の設計上の注意（調査済み・将来やるなら要判断）**: 遅延読み込みは既存の3機能と
真正面から衝突する。着手前にこの3つの解決方針を決めること。
1. `spreadOverlappingPointsAcrossLayers` は**全マーカーレイヤーの地物を
   プールしてから**でないと重複座標を検出できない → Python側（エクスポート時）に
   移すのが筋。実行時コストも消えるので一石二鳥
2. `getCombinedBounds`（autoFit）は全レイヤーの座標を要求する →
   レイヤーごとのbboxをPython側で事前計算して config に入れれば解決
3. `search.js`/`point-list.js` は `FAG_FEATURES_BY_LAYER` を参照するため、
   未パースのレイヤーは検索・一覧表に出てこなくなる → 仕様として許容するか、
   要求時にパースするか要判断

**未検証**: 実際のQGISでの動作確認（`.py` を変更しているのでQGISの再起動が
必要）。特に (a) `symbol.opacity()`/`layer.opacity()` が期待どおりの値を
返すか（線幅で `widthUnit()` がシンボル層側にあった前科があるので要確認）、
(b) カテゴリのチェックを外した地物が本当に出力されないか、
(c) 再読み込みボタンが実プロジェクトで設定を保持するか。

---

## 2026-07-27: v0.3.2 リリース準備（Qt6/QGIS4対応・マップ単位ラベル・一覧表/レイヤーパネル修正）

**担当**: Claude Code（Sonnet）

公開済みのv0.3.1リリース（GitHub Release、コミット`4f048b4`時点）は英語UI対応のみを
含む内容だった。その後`main`には(1) PR #2のQt6/PyQt6互換性修正（`exec_()`→`exec()`、
Qt列挙型のフル修飾化＝QGIS4対応）、(2) マップ単位ラベルのフォントサイズ対応、
(3) 一覧表の列幅自動調整とドラッグリサイズ、レイヤーパネルのグループ表示修正・
一括表示切替チェックボックスが積まれており、`metadata.txt`の`version`は`0.3.1`の
ままだった（公開済みv0.3.1と中身が食い違っていた）。

既存のv0.3.1タグ/Releaseは公開済みのため上書きせず、`version`を`0.3.2`に上げて
changelogを「0.3.1で実際にリリースされた内容」と「0.3.2の新規内容」に分割した。

### リリース作業
`v0.3.2`タグを付けてGitHubへプッシュ、`git archive`で`map_to_html_v0.3.2.zip`を
作成（従来と同じ`facility_app_generator/`プレフィックス構成）。

---

## 2026-07-27: v0.3.1 リリース（プラグインUIの英語対応）

**ブランチ**: `claude/international-users-english-check-fmp7po` → `main`にマージ予定
**担当**: Claude Code標準（Sonnet）

ユーザーからの相談: 海外からのダウンロードが多いが、英語表記がちゃんと
なっているか不安。調査したところ、プラグインの操作画面（`dialog.py`/
`ui/*.py`）が`self.tr()`でラップされているのに翻訳カタログが一切存在せず、
QGISのロケールに関わらず常に日本語UIになっていた。出力側のHTML地図も
大部分は英語だったが、検索欄プレースホルダーやレイヤーパネルなど数箇所
だけ日本語が残っていた。

### 対応
- `TYPE_LABELS`（`data_tab.py`）と`BASEMAP_OPTIONS`（`display_tab.py`）が
  モジュールレベル変数経由で`tr()`に渡されていて翻訳抽出できない状態
  だったのを、メソッド内で直接リテラルを`tr()`に渡す形に修正
- `pylupdate5`/`lrelease`で`i18n/map_to_html_en.ts`・`.qm`を新規作成
  （102件、全て翻訳済み）。`plugin.py`でQGISロケールが`ja`以外なら
  自動でこの英語カタログを読み込むようにした（`ja`ロケールは従来通り
  日本語のまま）
- 出力HTML側の残っていた日本語（検索プレースホルダー、レイヤーパネル
  タイトル・aria-label、ラベル切替ボタン、検索結果/一覧表の件数表示）を
  英語に修正、`<html lang="ja">`も`lang="en"`に変更
- READMEに翻訳の仕組みと再生成手順を追記
- `metadata.txt`を0.3.1に更新、changelogに上記を追加

### リリース作業
`main`へマージ後、`v0.3.1`タグを付けてGitHubへプッシュ、`git archive`で
`map_to_html_v0.3.1.zip`を作成（従来と同じ`facility_app_generator/`
プレフィックス構成）。

---

## 2026-07-25: マップ単位のラベル文字サイズに対応（v0.3.1の一部）

**担当**: Claude Code（Opus）
**バージョン**: v0.3.1（`metadata.txt`を0.3.1に更新済み。リリース作業
＝タグ付け・zip作成は未実施、他の0.3.1項目が揃った時点で行う）

ユーザーからの相談: ラベルのサイズを「マップ単位」で設定したとき、
HTMLにもその大きさ（ズームで拡大縮小する実寸）を反映できないか。
線幅（2026-07-24の項）と同じ問題がラベルにも残っていた：
`_to_px`はマップ単位を換算できないので既定値12pxに落としており、
QGISで「20マップ単位」と指定しても出力は固定11〜12pxだった。

### 対応
- **Python側** (`core/style_extractor.py`):
  - `_extract_label_style(layer, meters_per_map_unit)`に換算値を渡し
    （`extract_style`が線幅用に算出済みのものを再利用）、
    `fmt.sizeUnit()`が`RenderMapUnits`/`RenderMetersInMapUnits`なら
    `_width_in_meters`で実メートル化して`fontSizeMeters`を追加出力。
    ハロー（バッファ）も同様に`buffer.widthMeters`。
  - 固定単位（mm/pt/px）は従来通り`fontSize`/`buffer.width`のpxのみ。
    px側の値は常に出力するので、JS側のフォールバックにもなる。
- **JS側**:
  - `style-renderer.js`: メートル→px換算を`fagMetersToPixels(map, m)`
    として切り出し、`fagMapUnitWeight`（線幅、下限0.5px）はその上に載せた。
  - `label-layer.js`: `fagLabelFontSize`/`fagLabelBufferWidth`が
    `fontSizeMeters`/`widthMeters`を現在ズームのpxへ換算。
    文字サイズは`FAG_LABEL_MIN_PX=6`〜`FAG_LABEL_MAX_PX=200`でクランプ
    （線のヘアライン下限と同じ考え方＝ズームアウトで潰れて読めなくなる
    より最小サイズで残す／ズームインで1件が画面を覆うのを防ぐ）、
    ハローは既存のpx側と同じく4px上限。
  - テキスト計測キャッシュ（`entry.metrics`）はこれまで「フォントは
    不変」前提で1回きりだったので、`entry.metricsFontSize`を併せて持ち
    **丸めたpxサイズが変わったときだけ**再計測するようにした
    （px指定ラベルは従来通り常時キャッシュヒット、マップ単位ラベルも
    パン中は再計測なし＝ズーム段階ごとに1回）。
  - 衝突判定・ラベルクリック判定は再計測後の`metrics`をそのまま使うので
    自動的に新サイズへ追従する。

### 検証
scratchpadの`gen_mapunit_label_test.py`で「20mラベル＋2mハロー」の
レイヤーと「固定11px」レイヤーを並べたテストサイトを生成しブラウザで確認:
z12→6px（下限）、z16→10px、z17→20px、z18→41px、z19→81px と
期待式（20m ÷ `156543.03392×cos(lat)/2^zoom`）に一致し、固定pxレイヤーは
全ズームで11pxのまま。ハローもz17で2.04px→z18以降4px上限で頭打ち。
ラベルの外接矩形も高さ7px→24px→97pxと再計測されていることを確認。
`node --check`・`flake8`通過。**QGIS実機での抽出**（`fmt.sizeUnit()`が
マップ単位を返すか）は線幅のときと同様、次回ユーザーテストで要確認。

---

## 2026-07-25: v0.3.0 リリース

**ブランチ**: `sonnet/search-and-feature-table` → `main`にマージ
**担当**: Claude Code標準（Sonnet）

ユーザーが実機（QGIS）で検索・一覧表・マップ単位線幅の挙動を確認、
v0.3.0としてリリース指示。`metadata.txt`を0.3.0に更新し、QGIS公式
リポジトリ向けの英語changelogを`changelog=`セクションとして追加
（公式リポジトリは0.2.0からの更新になるため、0.2.1の内容も0.3.0の
項目に含めて記載）。`about`の「Search/filter is planned」も実装済みの
記述に更新。`main`へマージ後、`v0.3.0`タグを付けてGitHubへプッシュ、
`git archive`で`map_to_html_v0.3.0.zip`を作成（従来と同じ
`facility_app_generator/`プレフィックス構成）。

---

## 2026-07-24: マップ単位（メートル）の線幅に対応

**ブランチ**: `sonnet/search-and-feature-table`
**担当**: Claude Code標準（Sonnet）

ユーザーからの相談: 道路レイヤーの線幅をmmではなくマップ単位にして
「ズームアウトしても拡大されない」ようにしたが、HTML出力では引き継がれず
太い線のまま出力される。マップ単位を維持できないか。

### 原因（2つの問題が重なっていた）
1. `style_extractor.py`の`_extract_line_style`が`symbol.widthUnit()`を
   読もうとしていたが、**このメソッドはQgsLineSymbolには存在しない**
   （単位はシンボルレイヤー`QgsSimpleLineSymbolLayer.widthUnit()`が持つ）。
   `hasattr`チェックが常にFalseになり**ミリメートルと誤判定**、
   「19.5マップ単位」→「19.5mm ≒ 74px」→上限20pxにクランプ、という
   固定太線がズーム無関係に描かれていた（スクリーンショットのオレンジの塊）。
2. そもそもマップ単位はズーム依存なので固定pxには変換できず、
   `_to_px`は対応外の単位をフォールバック値に落とす設計だった。

### 対応
- **Python側** (`core/style_extractor.py`):
  - 幅の単位をシンボルレイヤーから正しく読むよう修正。
  - `RenderMetersInMapUnits`（実メートル）と`RenderMapUnits`（マップ単位）を
    実世界メートルに換算して`widthMeters`（線）・`strokeWidthMeters`
    （ポリゴン輪郭、両ブランチ）としてエクスポート。マップ単位→実メートルの
    換算は`_meters_per_map_unit(layer)`：プロジェクトCRSがEPSG:3857なら
    メルカトルの緯度歪みを補正（×cos(レイヤー中心の緯度)）、その他の
    メートル系CRSなら1:1、度単位CRSなら換算不能としてpxフォールバック。
  - 固定単位（mm/pt/px）は従来通りpx変換。カテゴリ別スタイルにも適用
    （`_style_for_symbol`/`_extract_category_styles`にパラメータを伝搬）。
- **JS側**:
  - `style-renderer.js`: `FAG_MAPUNIT_PATHS`レジストリと
    `fagUpdateMapUnitWeights(map)`。px幅 = メートル ÷（地図中心緯度での
    1pxあたり実メートル数 `156543.03392×cos(lat)/2^zoom`）。下限0.5px
    （QGISがサブピクセル幅をヘアラインで描き続けるのに合わせ、
    ズームアウトで完全消滅はさせない）。
  - `layer-control.js`: line/fillの`onEachFeature`で`widthMeters`/
    `strokeWidthMeters`を持つパスをレジストリに登録。`initLayerControl`が
    全レイヤー構築後に初回計算＋`map.on('zoomend')`で再計算。
  - `bindHoverHighlight`（style-renderer.js）との干渉対策: ホバーの
    基準太さをバインド時スナップショットではなく`_fagBaseWeight`
    （`fagUpdateMapUnitWeights`がズームごとに更新）から読むようにし、
    ズーム後のマウスアウトで古いズームの太さに戻るバグを予防。

### 検証
`gen_mapunit_test.py`（scratchpad）で幅員区分4カテゴリ×12本の道路
（widthMeters: 19.5/13/5.5/3）＋50m輪郭ポリゴンのテストサイトを生成し
ブラウザで確認: z14で19.5m道路=2.48px、z17で19.86px（実寸通り）、
z10で0.5px下限、いずれも期待式と一致／`setZoom`の自然な`zoomend`でも
再計算される／ホバーで+2px→マウスアウトで現在ズームの太さに正しく復帰。
`node --check`・`flake8`通過。QGIS実機での抽出（単位の読み取り）は
次回ユーザーテストで要確認。

---

## 2026-07-24: 一覧表の列ソート・ポップアップ連動フィルタ・配置の再修正

**ブランチ**: `sonnet/search-and-feature-table`
**担当**: Claude Code標準（Sonnet）

前項（レイアウト見直し）の直後、さらにユーザーから3件のフィードバック。

### 変更
- **列ソート**: `point-list.js`の一覧表ヘッダーをクリックすると昇順⇔降順が
  トグルする（3クリック目で元の順序に戻る、という第三状態は無し。spec
  「昇順・降順のみでよい」）。数値として両辺がパースできれば数値比較、
  それ以外は`localeCompare(..., 'ja')`。列を切り替えると昇順から再スタート。
  レイヤー切替時はソート状態をリセット（別レイヤーには同名列が無いことが
  あるため）。ヘッダーセルにソート方向の矢印（▲/▼）を表示。
- **ポップアップ表示オフのレイヤーを検索・一覧表の対象外に**: `search.js`の
  `searchableLayers`・`point-list.js`の`tableLayers`どちらも
  `layerConfig.showPopup !== false`を追加条件にした。`showPopup:false`は
  データ設定タブの「ポップアップ表示」チェックボックスに連動し、
  `layer-control.js`がそのレイヤーをクリック/ホバー無効（`layerInteractive`）
  にしているのと同じフラグ - 検索結果や一覧表の行をクリックしても開く
  ポップアップが無いレイヤーを一覧に出しても意味がないため。両ファイルの
  冒頭コメントと`README.md`の機能一覧にこの挙動を明記。
- **一覧表パネルの配置を左下スタンバイに変更**: 前項で「地図左側」に
  移動したばかりだったが、「左下にスタンバイで、展開したときに上に広がる
  形に」という追加フィードバックを受け、`top:130px`アンカーから
  `bottom:10px`アンカーに変更。`flex-direction: column-reverse`で
  DOM順序（ヘッダー→スクロール領域）は変えずに見た目の重なりだけ反転させ、
  ヘッダーをパネル下端に固定・スクロール領域をその上に表示。`bottom`基準の
  絶対配置なので、展開して中身が増えるとパネルの上端だけが上に伸びる
  （＝下端は動かないまま上に広がる）。これにより左上のズーム/ラベル
  ON-OFFボタンとの衝突を気にする必要が無くなった（`top:130px`だった
  ときの実測値ベースの補正コメントは不要になり削除）。

### 検証
`search_table_test.html`（1,531件データセット）を再生成しブラウザで確認:
折りたたみ時は画面左下に高さ約34pxのバーとして待機／展開すると下端は
710px（画面高720pxの10px上）のまま上端が66pxまで伸びる（＝上に広がる）／
再度折りたたむと同じ位置の待機バーに戻る／列ヘッダークリックで
昇順→降順（▼表示）に切り替わり実際の行順も反転することを確認。
`showPopup !== false`の判定が実際に出力HTMLへ反映されていること（生成
HTML内に3箇所出現：layer-control.jsの`layerInteractive`・table・search）を
文字列検索で確認。`node --check`（point-list.js・search.js）通過。

---

## 2026-07-24: 検索バー・地物一覧表のレイアウトを見直し（実装直後のフィードバック）

**ブランチ**: `sonnet/search-and-feature-table`
**担当**: Claude Code標準（Sonnet）

3-1/3-2実装直後のユーザーフィードバック: 「検索バーは、上のタイトルバーの中に
配置」「一覧表は左側に寄せることはできる？」。

### 変更
- **検索バー**: 地図上のLeafletコントロール（左上、ズームボタンの下）から、
  `#app-header`（タイトルバー）内・タイトルの右側に移動。ヘッダーの背景色は
  出力設定タブでユーザーが自由に変更できるため、検索入力欄はヘッダー色に
  依存しない固定の明るい背景（`--panel-bg`）にして、どんな配色でも読める
  ようにした。結果リストは入力欄の下にドロップダウンとして表示（絶対配置、
  `#search-dropdown`でラップ）。地図上のコントロールでなくなったため
  `L.control`でのラップ・`disableClickPropagation`は不要になり削除。
  外側クリックで閉じる・結果クリック後に閉じる・キーワードが残っている
  状態で入力欄に再フォーカスすると再度開く、という一般的なドロップダウン
  UXを追加。
- **地物一覧表**: 画面下部の全幅ドロワーから、地図左側の縦長パネルに変更
  （`#layer-panel`は右側にあるので左右対称のレイアウトに）。Leafletの
  ズームコントロール＋ラベルON/OFFボタン（どちらも左上、合計約118px）の
  下に来るよう`top: 130px`で配置（実測して確定、コメントに根拠を記載）。
  `max-height: calc(100vh - 206px)`でビューポート下端に収まるようにした。

### 検証
Single-file出力の検証サイトをブラウザで再確認: 検索パネルが`#app-header`
内に実際に配置されていること、地物一覧表パネルがラベルON/OFFボタンと
重ならないこと（実測座標で確認）、展開時にビューポート下端に収まること
（720pxウィンドウで514px高・下端700px、20pxの余白）、検索ドロップダウンの
開閉（入力・外側クリック・結果クリック後・再フォーカス）が正しく動作する
ことを確認済み。

---

## 2026-07-24: v0.3.0 タスク3-1（検索）・3-2（地物一覧表）を実装

**ブランチ**: `sonnet/search-and-feature-table`（`sonnet/misc-fixes`の直後）
**担当**: Claude Code標準（Sonnet）。設計・実装とも本セッションで実施
（本来Fable 5が設計担当だったが今回は不参加のため）。詳細な設計判断は
`C:\Users\ukawa\.claude\plans\proud-orbiting-melody.md`（承認済みプラン）を参照。

### 前提として発見した問題
`template/js/search.js`・`template/js/point-list.js`は元々存在したが、
`core/html_builder.py`のJS_MODULE_ORDERに含まれておらず`main.js`からも
呼ばれていない**未使用の死んだコード**だった。中身は`FAG.markersById`・
`config.fields.idField`等、v0.2.0以前の「単一sitesレイヤー」時代の設計を
前提にしており、現行の「レイヤーごとに独立したシンボロジ/フィールド設定を
持つ複数レイヤー」アーキテクチャとは噛み合わない。両ファイルとも全面書き直し。

### 実装内容
- **設計方針**: 検索（3-1）はレイヤー横断・表示中レイヤーのみ対象。
  一覧表（3-2）は選択した1レイヤーのみ・非表示レイヤーも選択可（選ぶと
  自動でそのレイヤーを表示状態にする）。どちらも新しいフィールド選択UIは
  追加せず、`ui/field_dialog.py`のポップアップ項目 設定…で既に選ばれている
  フィールド（`core/geojson_writer.py`が実際にGeoJSONへ書き出す属性）を
  そのまま検索対象・表示列として再利用。
- `template/js/layer-control.js`に`FAG_FEATURES_BY_LAYER`
  （`{layerId: {fid: {feature, layer}}}`、`_fid`はgeojson_writer.pyが
  常に付与する安定連番）と`focusFeature(map, layerId, entry)`
  （ズーム＋`openPopup()`、非表示レイヤーなら`#layer-panel`のチェックボックスを
  自動でONにしてから）を追加。`buildStyledLayer`のmarker/line/fill
  各分岐で`registerFeature`を呼ぶよう変更。
- `template/js/search.js`: デバウンス付き入力、表示中レイヤーのみ対象に
  全文字列検索、結果は上位50件のみ描画（残りは件数表示）、結果クリックで
  `focusFeature`。パネルはLeaflet純正コントロールとして左上
  （ズームボタン・ラベルON/OFFボタンの下）にスタック。
- `template/js/point-list.js`: `initFeatureTable`。レイヤー選択
  プルダウン、選択レイヤーの列（GeoJSON属性のキー順）、**自前実装の
  固定行高仮想スクロール**（スクロール位置から表示範囲のみDOMに存在させる。
  ヘッダー行は`position:sticky`で同一スクロールコンテナ内に置き、横スクロールを
  ボディと共有）。1,530件（実データ想定）でスクロール位置→描画行の対応を
  実機相当のブラウザテストで確認済み（後述）。
- `ui/display_tab.py` / `core/config_builder.py`: 「検索バーを表示する」
  「レイヤー内地物の一覧表を表示する」チェックボックス（デフォルト両方ON）→
  `config.display.searchEnabled`/`featureTableEnabled`。
- `core/html_builder.py`のJS_MODULE_ORDERに`search.js`・`point-list.js`を
  `layer-control.js`/`label-layer.js`の後・`main.js`の前に追加。

### 検証（ブラウザ、1,531件データセット、Single-file出力）
検索: キーワードで正しく絞り込み／50件超で「ほか◯件」表示／結果クリックで
ズーム＋ポップアップ／非表示レイヤーの地物は検索にヒットしないことを確認。
一覧表: レイヤー切替で列・行が正しく差し替わる／1,531件で仮想スクロールが
正しい範囲の行を描画（スクロール位置→行番号の対応を複数ポイントで確認）／
行クリックでズーム＋ポップアップ（`showPopup:false`のレイヤーはズームのみ、
ポップアップ開かず）／`searchEnabled`/`featureTableEnabled`を`false`にすると
両パネルとも非表示になることを確認。

**テスト時のハマりどころ（次回セッション向け）**: `split`出力
（`config.js`/`layers.js`を別ファイルで参照）だと、このBrowserツール環境では
regenerate後も**別ファイルの`<script src>`が古い内容のままキャッシュされ続ける**
（`location.reload()`・Ctrl+Shift+R・新規タブでも直らない。手動`fetch(...,
{cache:'no-store'})`は最新を取得できるのに、ブラウザの通常のスクリプト読み込み
だけ古いまま）。原因不明だが再現性あり。回避策: 検証には`single`出力
（HTML1ファイルに全部インライン）を使うこと - こちらは`location.reload()`で
正しく最新化される。加えて、Browserペインが実際に画面表示されていない
（`document.visibilityState==='hidden'`）ときは`requestAnimationFrame`が
発火しないため、rAFに依存する再描画ロジックの検証は
`window.requestAnimationFrame`を同期実行に一時差し替えてテストすること
（本セッションでは`initFeatureTable`を再実行して確認した）。

---

## 2026-07-23: ホバーのbringToFrontが重なり順優先度を恒久的に壊していた問題を修正

**ブランチ**: `sonnet/v030-ux-fixes`
**担当**: Claude Code標準（Sonnet）

前項（クリック優先度修正）を実機で試したユーザーから：「ラベルクリックは
スムーズに表示されるようになった。けど、ホバーは周辺のポリゴンデータ
（2000ｍ円）が優先されて太線になっている。ポイントにフォーカスされるように
してほしい」。

### 原因

`style-renderer.js`の`bindHoverHighlight`が、マウスオーバー時に
`target.bringToFront()`を呼んでいた（隣接図形に隠れないよう、強調表示中の
太い線を前面に出す目的）。`L.Canvas.prototype._onClick`と`_handleMouseHover`
は**同じ**`_drawFirst`/`.next`連結リストを辿って最後にマッチしたものを採用する
ため、直前のコミットで`layer-control.js`に追加した`bringLayerToFront()`
（初期化時に一度だけ、設定順で正しく並べる処理）が、**ホバーのたびに
その場限りで書き換えられ、しかもmouseoutで元に戻らない**まま残っていた。
つまり、一度でも背面設定のポリゴン（2000m円）にマウスが乗ると、それ以降
ページを再読み込みするまでずっと、そのポリゴンが同じ場所のポイントより
優先されるようになっていた。

7レイヤー再現サイトで確認：ポリゴンをホバー→ポイントをホバーすると、
`renderer._hoveredLayer`が引き続きポリゴンのまま（ポイントのホバーが
効かなくなる）。修正後は正しくポイント側に切り替わることを確認。

### 修正

`bindHoverHighlight`のmouseoverハンドラから`target.bringToFront()`の呼び出しを
削除。強調表示自体（線を太く・塗りを濃く）は残るため、見た目上どの図形に
カーソルが乗っているかは引き続き分かる。

---

## 2026-07-23: ポリゴンレイヤーが手前のポイントのクリックを奪う問題を修正

**ブランチ**: `sonnet/v030-ux-fixes`
**担当**: Claude Code標準（Sonnet）

実機フィードバック：「ポリゴンのデータ（2000ｍ円など）のポップアップ表示が
オンのままだと、他のポイントに被さってポイントをクリックしてもポップアップが
表示されない。レイヤーの重なりの順番でポップアップの優先度をつけてほしい」。

### 調査

直前の`_populate_visible_layers`修正でレイヤー取り込み順序自体は正しくなった
（`layersConfig`が正しく「奥→手前」の順になった）が、それでもクリック優先度が
狂うケースがあった。原因を実ブラウザで`L.Canvas.prototype._onClick`のソースを
直接確認して特定：

```js
for (o=this._drawFirst; o; o=o.next)
  (e=o.layer).options.interactive && e._containsPoint(n) && (i=e);
```

Canvasレンダラーの`_onClick`は`this._layers`（挿入順や`leaflet_id`順）ではなく、
**`_drawFirst`/`.next`という別管理の描画順連結リスト**を辿って、最後にマッチした
ものを採用する。この連結リストへの登録順は、`layersConfig.forEach(...).addTo(map)`
の呼び出し順と**必ずしも一致しない**（7レイヤーの再現テストで実測：
CircleMarker系（ポイント）がまとめて連結リストの前半に来て、Polygon系
（区境界線・2000m円）が呼び出し順に関係なく後ろに固まった）。よってポリゴンが
`layersConfig`上でポイントより奥（前に追加）でも、実際のクリック優先度では
ポイントより勝ってしまうことがあった。

### 修正

`layer-control.js`に`bringLayerToFront(layer)`を追加。`L.LayerGroup`/
`L.FeatureGroup`なら`.eachLayer()`で再帰し、`L.Path`系（circleMarker/
Polygon/Polyline）なら`.bringToFront()`を呼ぶ（非circleの`L.marker`は
`.eachLayer`も`.bringToFront`も持たないので黙ってスキップ＝別経路のDOM
スタッキングで既に正しく動く）。`initLayerControl`のメインループで各レイヤーを
`addTo(map)`した直後に、`layersConfig`の順（＝奥→手前）でこれを呼ぶことで、
Leafletの内部登録順に関わらず、こちらが意図した重なり順を`_drawFirst`
連結リストに強制的に反映させる。`defaultVisible:false`（初期非表示）の
レイヤーでも`bringToFront()`は安全にno-op（`_renderer`未設定時は何もしない
ガードがLeaflet側にある）。

7レイヤー・地理的に重なる構成（ポイント5層＋ポリゴン2層、実機のQGISパネル
構成を模した順序）で再現・修正確認済み：修正前は最前面設定のポイントで
クリックしても奥のポリゴンのポップアップが開いていたが、修正後は正しく
最前面のポイントが開くことをブラウザで確認。既存の1,530件パフォーマンス
データセットでも再ロード・ズーム速度に劣化なし（8〜19ms/ズーム）。

**未確認**: 実際のQGISプロジェクトでの動作確認（次回QGIS実機で要確認）。

---

## 2026-07-23: レイヤー取り込み時の順序が逆だったバグを修正（既存バグ、今回発覚）

**ブランチ**: `sonnet/v030-ux-fixes`
**担当**: Claude Code標準（Sonnet）

実機（未利用地一覧.qgz、9レイヤー中7件がチェック済み）でユーザーから3件同時報告：
1. 「レイヤーの順番が、読み込んだ後に反転している」（QGISパネルとプラグインの
   テーブルを見比べると逆順）
2. 「順番を上に持ってきてもレイヤーが上に移動している感じがしない」
3. 「施設のポイントをクリックできない。ポップアップが出ない」

### 根本原因（今回のセッションより前から存在した既存バグ）
`ui/data_tab.py::_populate_visible_layers`（ダイアログを開いた時にQGISで
チェック済みのレイヤーを自動で表に取り込む処理、round2＝2026-07-18に実装）が、
`layer_utils.list_visible_layer_ids()`の返す順序（QGISレイヤーパネルの
**上から下＝手前から奥**の順）を**反転せずにそのまま**`self._entries`へ
appendしていた。

一方`self._entries`の意味は（このファイル自身のdocstring、および
`layer-control.js`の`layersConfig.forEach(...).addTo(map)`の実際の挙動）
「index0＝地図の一番奥（最初にLeafletへaddされる）、index-1＝一番手前
（最後にaddされる）」。つまりQGISパネルの「手前（上）」のレイヤーは、
自動取り込み直後から**常に**`self._entries[0]`＝出力の一番奥に配置されて
いた＝**QGISでの重なり順と出力の重なり順が最初から逆**になっていた
（v0.3.0着手前から存在していたバグ）。

前回（2-4）のテーブル表示反転修正は、この誤った前提を元に「テーブル最上段＝
出力の最前面」を実現するものだったため、それ自体は正しく機能していたが、
結果として**テーブルの見た目もQGISパネルと逆順**になり、ユーザーが両パネルを
見比べたときに「読み込んだ後に反転している」と気づきやすくなった
（症状1）。上へ移動ボタンで「テーブル上」に動かしても、それがQGISでの
直感（＝パネル上に来るほど手前）と逆の見た目になるため「移動している感じが
しない」（症状2）。そして本来QGISパネルの最上段（＝クリックしたい対象、
今回は「福祉」773件のポイント）に置かれていたレイヤーが、出力では
**一番奥**に配置され、後から追加された「区境界線」や「備考_公園・スポーツ_
児童遊園・広場」（ポリゴン、ポップアップ表示ON）が代わりにクリックを
奪っていたと考えられる（症状3）。

### 修正
`_populate_visible_layers`が`reversed(layer_utils.list_visible_layer_ids())`を
イテレートするよう変更。これにより自動取り込み直後から
`self._entries[-1]`＝QGISパネル最上段（手前）となり、
- テーブル表示（reversed(self._entries)）がQGISパネルと同じ並びになる
- 出力でもQGISパネル最上段のレイヤーが最後にaddされて最前面になる
の両方が同時に満たされる。手動の「＋追加」ボタン（1件ずつ追加）は元々の
挙動のまま（新規追加＝末尾＝最前面、変更なし）。

QGIS非依存のため、実際のスクリーンショットのレイヤー構成（福祉・2000m円・
未利用地グループ3件・区境界線・備考2件、計7件チェック済み想定）を
そのまま使ったPythonトレーススクリプトで、(a)テーブル表示がQGISパネル順と
一致すること、(b)「福祉」が出力の最前面（最後にadd）になること、
(c)既に最前面のレイヤーで「上へ移動」を押しても範囲外で無視されること、
の3点をassertで確認済み（スクラッチパッド、リポジトリ外）。

**未確認（次回QGIS実機で要確認）**: この修正で実際に「福祉」のポイントが
クリックできるようになったか。z-order起因という仮説の裏付けは取れているが、
それでもクリックできない場合は、生成された`config.js`/`layers.js`または
ブラウザのコンソールエラーを見せてもらう必要がある。

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
