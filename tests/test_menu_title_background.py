"""Exercise Menu Title rendering without opening or changing an Anki collection."""
import ast
import html
import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


class MenuTitleBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.values = {}
        tree = ast.parse((ROOT / 'rendering/onigiri_renderer.py').read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == '_get_onigiri_stats_title_html')
        env = dict(html=html, os=os, re=re, quote_url_component=quote,
                   config=SimpleNamespace(DEFAULTS={'statsTitle': 'Welcome to Onigiri'}),
                   mw=SimpleNamespace(addonManager=SimpleNamespace(addonFromModule=lambda _: '1011095603')),
                   _col_conf_get=lambda key, default: self.values.get(key, default),
                   __name__='1011095603.onigiri_renderer')
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'rendering/onigiri_renderer.py', 'exec'), env)
        self.render = env[function.name]

    def test_fresh_install_keeps_phrase_without_background(self):
        markup = self.render()
        self.assertIn('Welcome to Onigiri', markup)
        self.assertNotIn('has-background', markup)
        self.assertIn('--menu-title-alignment:left', markup)

    def test_empty_phrase_without_background_is_hidden(self):
        for text in ('', '   '):
            self.values['modern_menu_statsTitle'] = text
            self.assertEqual(self.render(), '')

    def test_empty_phrase_keeps_only_selected_background(self):
        self.values.update(modern_menu_statsTitle='', modern_menu_title_background_enabled=True,
                           modern_menu_title_background_color='#123456')
        markup = self.render()
        self.assertIn('has-background', markup)
        self.assertIn('background-color:color-mix(in srgb, #123456 100.0%, transparent)', markup)
        self.assertNotIn('<h1', markup)
        self.assertNotIn('Welcome to Onigiri', markup)

    def test_image_url_encodes_filename_and_retains_background_when_blank(self):
        self.values.update(modern_menu_statsTitle='', modern_menu_title_background_enabled=True,
                           modern_menu_title_background_type='image',
                           modern_menu_title_background_image='sun & moon.png',
                           modern_menu_title_background_opacity=35, modern_menu_title_background_blur=12)
        markup = self.render()
        self.assertIn('/user_files/main_bg/sun%20%26%20moon.png', markup)
        self.assertIn('opacity:0.35', markup)
        self.assertIn('filter:blur(12.0px)', markup)
        self.assertNotIn('<h1', markup)

    def test_effects_belong_to_background_and_alignment_to_phrase(self):
        self.values.update(modern_menu_title_background_enabled=True,
                           modern_menu_title_background_opacity=45, modern_menu_title_background_blur=6)
        for alignment in ('left', 'center', 'right'):
            self.values['modern_menu_title_alignment'] = alignment
            markup = self.render()
            self.assertIn('--menu-title-alignment:' + alignment, markup)
            self.assertIn('backdrop-filter:blur(6.0px)', markup)
            self.assertIn('<h1 class="onigiri-widget-title">Welcome to Onigiri</h1>', markup)

    def test_toggle_off_preserves_selected_asset_and_phrase(self):
        self.values.update(modern_menu_title_background_enabled=False,
                           modern_menu_title_background_type='image', modern_menu_title_background_image='saved.png')
        self.assertNotIn('onigiri-menu-title-background', self.render())
        self.assertEqual(self.values['modern_menu_title_background_image'], 'saved.png')

    def test_color_opacity_leaves_the_blurred_backdrop_visible(self):
        self.values.update(modern_menu_title_background_enabled=True,
                           modern_menu_title_background_color='#2C401C',
                           modern_menu_title_background_blur=32)
        for opacity in (0, 62, 100):
            self.values['modern_menu_title_background_opacity'] = opacity
            markup = self.render()
            self.assertIn(f'background-color:color-mix(in srgb, #2C401C {float(opacity)}%, transparent)', markup)
            self.assertIn('opacity:1;', markup)
            self.assertIn('backdrop-filter:blur(32.0px)', markup)

    def test_widget_sync_uses_shared_surface_and_restores_custom_background(self):
        self.values.update(modern_menu_title_background_enabled=True,
                           modern_menu_title_sync_widgets=True,
                           modern_menu_title_background_type='image',
                           modern_menu_title_background_image='saved.png',
                           modern_menu_title_background_opacity=35,
                           modern_menu_title_background_blur=12)
        saved = self.values.copy()
        markup = self.render()
        self.assertIn('background-color:var(--canvas-inset)', markup)
        self.assertIn('backdrop-filter:blur(var(--onigiri-widget-blur, 0px))', markup)
        self.assertNotIn('saved.png', markup)
        self.assertEqual(self.values, saved)
        self.values['modern_menu_title_sync_widgets'] = False
        markup = self.render()
        self.assertIn('/main_bg/saved.png', markup)
        self.assertIn('opacity:0.35', markup)
        self.assertIn('filter:blur(12.0px)', markup)

    def test_invalid_values_fall_back_and_effects_are_bounded(self):
        self.values.update(modern_menu_title_background_enabled=True,
                           modern_menu_title_alignment='bad', modern_menu_title_background_color='red;position:fixed',
                           modern_menu_title_background_opacity=500, modern_menu_title_background_blur=-5)
        markup = self.render()
        self.assertIn('--menu-title-alignment:left', markup)
        self.assertIn('background-color:color-mix(in srgb, #FFFFFF 100.0%, transparent)', markup)
        self.assertIn('opacity:1;', markup)
        self.assertIn('blur(0px)', markup)

    def test_phrase_remains_plain_text(self):
        self.values['modern_menu_statsTitle'] = '<img src=x onerror=alert(1)> & hi'
        markup = self.render()
        self.assertIn('&lt;img', markup)
        self.assertNotIn('<img', markup)


if __name__ == '__main__':
    unittest.main()
