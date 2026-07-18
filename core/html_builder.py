# -*- coding: utf-8 -*-
"""Combine template/base.html with the CSS/JS modules and the
generated config/layers data (spec section 5.3). Uses plain string
replacement only (no Jinja2) so it works in restricted municipal QGIS
environments without extra packages.
"""
import json
import os

# Modules that this round actually ships; later phases append to this
# list (search.js, point-list.js, clustering.js, heatmap.js, ...).
JS_MODULE_ORDER = [
    'display-settings.js',
    'style-renderer.js',
    'map-core.js',
    'layer-control.js',
    'label-declutter.js',
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
    directly into the HTML rather than written to its own .js file."""
    return _compact_json(value).replace('</', '<\\/')


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
        config_script = '<script>const config = ' + _json_for_inline_script(config) + ';</script>'
        layers_script = (
            '<script>const layersData = ' + _json_for_inline_script(layers_data) +
            ';\nconst layersStyleData = ' + _json_for_inline_script(layers_style) + ';</script>'
        )

        html = html.replace('<!-- INJECT_CONFIG -->', config_script)
        html = html.replace('<!-- INJECT_LAYERS -->', layers_script)

        _write_text(output_target, html)
        written.append(output_target)

    else:
        raise ValueError(f'Unknown output_format: {output_format!r}')

    return written
