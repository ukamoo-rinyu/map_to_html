# -*- coding: utf-8 -*-
"""Combine template/base.html with the CSS/JS modules and the
generated config/layers data (spec section 5.3). Uses plain string
replacement only (no Jinja2) so it works in restricted municipal QGIS
environments without extra packages.
"""
import json
import os

# Modules that this round actually ships; later phases append to this
# list (clustering.js, heatmap.js, ...). search.js/point-list.js need
# layer-control.js's FAG_FEATURES_BY_LAYER/focusFeature to already
# exist, so they're ordered after it (and label-layer.js, unrelated
# but conceptually "map setup") and before main.js, which is what
# actually calls initSearch/initFeatureTable.
JS_MODULE_ORDER = [
    'display-settings.js',
    'style-renderer.js',
    'map-core.js',
    'layer-control.js',
    'label-layer.js',
    'search.js',
    'point-list.js',
    # Needs FAG_FEATURES_BY_LAYER (layer-control.js) and reuses
    # style-renderer.js's fagFeatureLatLng; point-list.js calls into it
    # for the two-way row/map selection sync. Everything is bundled into
    # one <script>, so function declarations hoist across module
    # boundaries and this ordering only matters for top-level `var`s.
    'selection.js',
    'main.js',
]


def _read_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def _json_for_inline_script(value):
    """json.dumps, but safe to embed inside a literal <script> block.
    A facility name/address/etc. containing the substring "</script>"
    would otherwise prematurely close the tag and corrupt the page -
    only relevant for single-file output, where the JSON is inlined
    directly into the HTML rather than written to its own .js file.

    The `<\\/` replacement keeps the payload valid JSON as well as valid
    JavaScript: JSON explicitly allows `\\/` as an escape for a solidus,
    so the same escaped text can be handed to JSON.parse unchanged
    (which is what the <script type="application/json"> blocks below
    rely on)."""
    return _compact_json(value).replace('</', '<\\/')


def _json_data_block(element_id, value):
    """A <script type="application/json"> block plus nothing else.

    The browser does NOT hand this to the JavaScript parser - it's inert
    text until something reads it - so for a large facility dataset the
    page-load cost of getting the bytes in is close to zero, and the
    later JSON.parse is substantially faster than having the JS parser
    work through the same data as an object literal. Only single-file
    output uses this; see build_output for why split output can't.
    """
    return (
        '<script type="application/json" id="' + element_id + '">'
        + _json_for_inline_script(value) + '</script>'
    )


def _parse_data_blocks(assignments):
    """The one real <script> that turns the inert JSON blocks above back
    into the globals the template modules expect. `assignments` is
    [(js_variable_name, element_id), ...]."""
    lines = [
        'const {0} = JSON.parse(document.getElementById("{1}").textContent);'.format(name, el_id)
        for name, el_id in assignments
    ]
    return '<script>\n' + '\n'.join(lines) + '\n</script>'


def _compact_json(value):
    """The layer/style data can be large (thousands of facilities), so
    drop json.dumps' default ", "/": " separators (qgis2web does the
    same size trim) - config.js stays pretty-printed separately since
    it's small and meant to be hand-editable (spec 5.0)."""
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _bundle_scripts(template_dir):
    parts = []
    for name in JS_MODULE_ORDER:
        path = os.path.join(template_dir, 'js', name)
        if os.path.exists(path):
            parts.append(f'/* ---- {name} ---- */\n' + _read_text(path))
    return '\n\n'.join(parts)


def build_output(template_dir, config, layers, output_format, output_target):
    """Render the final site.

    output_format: 'split' (default, spec 5.3 steps 3-7) or 'single'
        (spec 5.3 steps 3-6, everything inlined into one HTML file).
    output_target: for 'split', the destination folder; for 'single',
        the destination .html file path.
    layers: list of {'id': str, 'geojson_path': str, 'style': dict}
        (spec 4.2/4.3) - every layer the user added, each rendered
        with its own extracted QGIS symbology.

    Returns the list of file paths written.
    """
    base_html = _read_text(os.path.join(template_dir, 'base.html'))
    css_content = _read_text(os.path.join(template_dir, 'css', 'style.css'))
    scripts_content = _bundle_scripts(template_dir)

    layers_data = {}
    layers_style = {}
    for layer in layers:
        if layer.get('geojson_path'):
            layers_data[layer['id']] = _read_json(layer['geojson_path'])
        layers_style[layer['id']] = layer['style']

    html = base_html.replace('<!-- INJECT_CSS -->', f'<style>\n{css_content}\n</style>')
    html = html.replace('<!-- INJECT_SCRIPTS -->', f'<script>\n{scripts_content}\n</script>')

    written = []

    if output_format == 'split':
        out_dir = output_target
        os.makedirs(out_dir, exist_ok=True)

        config_js = 'const config = ' + json.dumps(config, ensure_ascii=False, indent=2) + ';\n'
        layers_js = (
            'const layersData = ' + _compact_json(layers_data) + ';\n'
            + 'const layersStyleData = ' + _compact_json(layers_style) + ';\n'
        )

        config_path = os.path.join(out_dir, 'config.js')
        layers_path = os.path.join(out_dir, 'layers.js')
        _write_text(config_path, config_js)
        _write_text(layers_path, layers_js)
        written += [config_path, layers_path]

        html = html.replace('<!-- INJECT_CONFIG -->', '<script src="config.js"></script>')
        html = html.replace('<!-- INJECT_LAYERS -->', '<script src="layers.js"></script>')

        html_path = os.path.join(out_dir, 'index.html')
        _write_text(html_path, html)
        written.append(html_path)

    elif output_format == 'single':
        # Inert JSON blocks + one JSON.parse pass, rather than embedding
        # the data as `const layersData = {...}` object literals. On a
        # large export the object-literal form makes the JavaScript
        # parser walk every byte of the dataset during page load, which
        # is the single biggest cost before anything is drawn.
        #
        # Split output deliberately keeps the object-literal form: its
        # config.js/layers.js are loaded with <script src>, and the same
        # trick there would mean either a fetch() (blocked by CORS on
        # file://, which is exactly how these exports get opened from a
        # shared folder) or double-encoding the JSON into a JS string
        # literal, which inflates the file by escaping every quote -
        # working against the size reduction that matters more there.
        config_script = _json_data_block('fag-config-data', config)
        layers_script = (
            _json_data_block('fag-layers-data', layers_data) + '\n'
            + _json_data_block('fag-layers-style-data', layers_style) + '\n'
            + _parse_data_blocks([
                ('config', 'fag-config-data'),
                ('layersData', 'fag-layers-data'),
                ('layersStyleData', 'fag-layers-style-data'),
            ])
        )

        html = html.replace('<!-- INJECT_CONFIG -->', config_script)
        html = html.replace('<!-- INJECT_LAYERS -->', layers_script)

        _write_text(output_target, html)
        written.append(output_target)

    else:
        raise ValueError(f'Unknown output_format: {output_format!r}')

    return written
