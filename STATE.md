# STATE.md — 開発経緯の引き継ぎメモ

各変更について「何を」「なぜ」「どう変えたか」を新しい順に追記する
（v0.3.0 指示書 §0 の共通指示）。次のセッション・別モデルはまずここを読むこと。

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
