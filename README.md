# Map to HTML

A QGIS plugin that publishes any number of QGIS layers as a standalone Leaflet/HTML/JS web map, each layer keeping its own symbology and labels (qgis2web-style "show everything as-is").

Pick layers from the current project (vector layers with single/categorized symbology, or raster/XYZ tile layers already added to the project), configure popup fields, layer order, colors and fonts, then export a self-contained web map that runs in any browser without a server.

- QGIS >= 3.16
- License: GPL-3.0-or-later
- Plugin UI language: Japanese, or English for any other QGIS locale (see `i18n/`)

## 概要

現在開いているQGISプロジェクトから任意のレイヤーを選び、そのシンボロジ・ラベル設定をそのまま引き継いだ状態でLeaflet/HTML/JSベースのWeb地図として書き出すプラグインです。

- ベクタレイヤー（単一シンボル・分類シンボル）、ラスタ/XYZタイルレイヤーをレイヤーとして選択可能
- マップ単位（メートル）指定の線幅に対応：QGISと同様、ズームアウトすると線も細く表示される（道路幅を実寸で表現するレイヤーなど）
- クリックで表示するポップアップの項目・順序をプラグイン内で設定・保存可能
- レイヤーの表示順（凡例順）、タイトル文字色・ヘッダー色・フォントを設定可能
- 背景地図の表示有無、ラスタ/XYZタイルレイヤーの不透明度を設定可能
- 1,000件超のポイントでも滑らかに動作するCanvas描画・ラベル表示
- ラベルのテキスト部分をクリックしてもポップアップを表示
- タイトルバー内の検索バーで施設名などを横断検索、結果クリックでズーム＋ポップアップ表示
- 地図左下にレイヤーごとの地物一覧表（列ヘッダークリックで昇順・降順に並び替え、行クリックでズーム＋ポップアップ表示）
  - 検索・一覧表とも、レイヤーごとの「ポップアップ表示」設定がオフのレイヤーは対象外（クリックしても開くポップアップがないため）
- フィルターバー（表示設定タブでオン、既定はオフ）: ヘッダー下に項目ごとのチェックリスト（全選択／解除）を並べ、選んだ値の地物だけを表示。項目はデータ設定タブの「ポップアップ・フィルター項目」でレイヤーごとに選び、同じ項目名のレイヤーは1つのフィルターにまとまる。地図・ラベル・一覧表・検索・CSV/GeoJSON出力すべてが連動
- 出力前のラベル一括調整（ラベル設定タブ）: 黒文字＋レイヤー色のバッファなどWeb向けの設定を別スタイル「Web」に書き込み、作業用スタイルへいつでも戻せる
- 現在地ボタン: スマートフォンなどで今いる場所を地図に表示（https:// で公開したページか、端末上のファイルとして開いたときに利用可能）
- 半径検索: 地図のクリック・現在地・地図の中心を中心に、指定した半径内の地物を近い順に一覧表示（レイヤーの表示状態・フィルターに連動）
- リンク共有: 表示位置・レイヤー・絞り込み・半径検索の状態をURLに記録し、ボタンでコピー。開くと同じ表示を再現
- 出力HTMLの日本語／英語表示: 最初の言語（またはブラウザに合わせる）を選べ、ヘッダーに切り替えボタンも表示可能
- プラグインの設定（データ設定・表示設定・出力設定）はQGISプロジェクトに保存され、次回開いたときに復元。「今の設定を初期値に保存」で自分の初期値を全プロジェクト共通に登録でき、「初期値に戻す」でそれ（またはプラグイン標準）に戻せる
- 表示設定タブは左の分類（地図の基本／検索・絞り込み／地図上のボタン／ポップアップ／見た目／言語／データ出力）から選ぶ形式。項目にマウスを乗せると下の説明欄に詳しい説明が出る
- 出力形式は単一HTMLファイル、またはHTML+JS+GeoJSONの分割ファイル
- サーバー不要、ブラウザで開くだけで動作

## 使い方

1. QGISでプラグインツールバーの「Map to HTML」アイコンをクリック
2. 「データ設定」タブでレイヤーを追加し、ポップアップに表示する項目を選択
3. 「表示設定」タブでレイヤー順・タイトル・配色・フォントを設定
4. 「出力設定」タブで出力形式・出力先を指定して生成

## インストール

QGISの「プラグイン」→「プラグインの管理とインストール」からこのリポジトリを検索してインストールしてください（QGIS公式リポジトリ掲載後）。

## Issue / Bug reports

https://github.com/ukamoo-rinyu/map_to_html/issues

## Translations

The plugin dialog's source strings are Japanese; `i18n/map_to_html_en.qm` provides the
English translation loaded automatically when QGIS's locale isn't Japanese. After adding
or changing any `self.tr(...)` string in `dialog.py`/`ui/*.py`, regenerate and re-translate:

```
pylupdate5 dialog.py plugin.py ui/*.py -ts i18n/map_to_html_en.ts
# fill in any new/changed <translation> entries in the .ts file
lrelease i18n/map_to_html_en.ts -qm i18n/map_to_html_en.qm
```
