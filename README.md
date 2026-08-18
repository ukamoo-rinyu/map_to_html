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
