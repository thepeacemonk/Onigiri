"""Render matched backgrounds without opening or writing an Anki collection."""
import ast
import json
import math
import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def load_functions(path, names, env):
    tree = ast.parse((ROOT / path).read_text())
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=body, type_ignores=[]), path, 'exec'), env)


class BackgroundMatchingTests(unittest.TestCase):
    def setUp(self):
        self.main = dict(modern_menu_background_mode='image_color', modern_menu_background_blur=35,
                         modern_menu_background_opacity=42, modern_menu_bg_color_light='#123456',
                         modern_menu_bg_color_dark='#654321', modern_menu_bg_image_theme_mode='separate',
                         modern_menu_background_image_light='day.png', modern_menu_background_image_dark='night.png')
        self.local = dict(onigiri_overview_bg_mode='main', onigiri_reviewer_bg_mode='main',
                          onigiri_overview_bg_main_blur=99, onigiri_overview_bg_main_opacity=99,
                          onigiri_reviewer_bg_main_blur=98, onigiri_reviewer_bg_main_opacity=98,
                          onigiri_reviewer_bottom_bar_match_main_blur=97,
                          onigiri_reviewer_bottom_bar_match_main_opacity=97)
        asset_env = {}
        load_functions('config.py', {'_dynamic_theme_enabled', 'themed_asset'}, asset_env)
        config = SimpleNamespace(get_config_readonly=lambda: self.local,
                                 get_collection_config=self.main.get,
                                 themed_asset=asset_env['themed_asset'],
                                 DEFAULTS={'colors': {'light': {'--bg': '#fff'}, 'dark': {'--bg': '#222'}}})
        self.env = dict(config=config, mw=SimpleNamespace(col=SimpleNamespace(conf=self.main)),
                        os=os, math=math, json=json,
                        _reviewer_bottom_bar_height_px=lambda _: 100,
                        _reviewer_background_viewport_height_px=lambda _: 800)
        load_functions('patcher.py', {'generate_reviewer_background_css', 'generate_overview_background_css',
                                     'generate_reviewer_bottom_bar_background_css', '_generate_outer_background_css',
                                     '_render_body_slideshow_background_css'}, self.env)

    def render(self, surface):
        return self.env['generate_' + surface + '_background_css'](str(ROOT))

    def assert_main_appearance(self, css):
        for fragment in ('#123456', '#654321', '/main_bg/day.png', '/main_bg/night.png', 'blur(7.0px)', 'opacity: 0.42'):
            self.assertIn(fragment, css)

    def test_match_widgets_ignores_stale_local_effects_images_and_border(self):
        self.main.update(modern_menu_sidebar_bg_mode='custom', modern_menu_sidebar_bg_type='image_color',
                         modern_menu_sidebar_bg_image='stale.png', modern_menu_sidebar_sync_box_effect=False,
                         modern_menu_sidebar_border_custom=True, modern_menu_sidebar_radius=55,
                         modern_menu_sidebar_stroke=9, modern_menu_sidebar_bg_blur=99,
                         modern_menu_sidebar_bg_opacity=99, onigiri_canvas_inset_effect_blur=35,
                         onigiri_canvas_inset_effect_opacity=42, onigiri_canvas_inset_border_radius=18,
                         onigiri_canvas_inset_border_width=2)
        self.local['colors'] = {'light': {'--canvas-inset': '#123456'}, 'dark': {'--canvas-inset': '#654321'}}
        for palette in self.env['config'].DEFAULTS['colors'].values():
            palette['--profile-page-bg'] = '#aaaaaa'
        self.env['_render_background_css'] = lambda *args: ''
        load_functions('patcher.py', {'generate_deck_browser_backgrounds', '_hex_to_rgba', '_mix_colors'}, self.env)
        css = self.env['generate_deck_browser_backgrounds'](str(ROOT))
        for fragment in ('rgba(18, 52, 86, 0.42)', 'blur(7.0px)', 'border-radius: 18px', 'border: 2px'):
            self.assertIn(fragment, css)
        self.assertNotIn('stale.png', css)


    def test_main_matches_ignore_stale_local_overrides(self):
        for surface in ('overview', 'reviewer', 'reviewer_bottom_bar'):
            with self.subTest(surface=surface):
                self.local['onigiri_reviewer_bottom_bar_bg_mode'] = 'main'
                self.assert_main_appearance(self.render(surface))

    def test_chained_matches_follow_subsequent_source_changes(self):
        for mode in ('match_overview_bg', 'match_reviewer_bg'):
            self.local['onigiri_reviewer_bottom_bar_bg_mode'] = mode
            self.assert_main_appearance(self.render('reviewer_bottom_bar'))
            self.main.update(modern_menu_background_blur=0, modern_menu_background_opacity=0)
            css = self.render('reviewer_bottom_bar')
            self.assertIn('blur(0.0px)', css)
            self.assertIn('opacity: 0.0;', css)
            self.main.update(modern_menu_background_blur=35, modern_menu_background_opacity=42)

    def test_custom_background_effects_are_retained(self):
        for surface in ('overview', 'reviewer'):
            self.local.update({f'onigiri_{surface}_bg_mode': 'image_color', f'onigiri_{surface}_bg_blur': 20,
                               f'onigiri_{surface}_bg_opacity': 70, f'onigiri_{surface}_bg_image_theme_mode': 'single',
                               f'onigiri_{surface}_bg_image': 'custom.png'})
            css = self.render(surface)
            self.assertIn('custom.png', css)
            self.assertIn('blur(4.0px)', css)
            self.assertIn('opacity: 0.7', css)

    def test_bottom_bar_inherits_source_theme_image_and_effects(self):
        for source in ('overview', 'reviewer'):
            self.local.update({f'onigiri_{source}_bg_mode': 'image_color', f'onigiri_{source}_bg_blur': 25,
                               f'onigiri_{source}_bg_opacity': 60, f'onigiri_{source}_bg_image_theme_mode': 'separate',
                               f'onigiri_{source}_bg_image_mode': 'single', f'onigiri_{source}_bg_image_light': 'source-day.png',
                               f'onigiri_{source}_bg_image_dark': 'source-night.png',
                               'onigiri_reviewer_bottom_bar_bg_mode': f'match_{source}_bg'})
            css = self.render('reviewer_bottom_bar')
            self.assertIn('source-day.png', css)
            self.assertIn('source-night.png', css)
            self.assertIn('blur(5.0px)', css)
            self.assertIn('opacity: 0.6;', css)

    def test_matching_recovers_shared_images_in_empty_theme_slots(self):
        for source in ('overview', 'reviewer'):
            self.local.update({f'onigiri_{source}_bg_mode': 'image_color',
                               f'onigiri_{source}_bg_image_theme_mode': 'separate',
                               f'onigiri_{source}_bg_image': 'shared.png',
                               'onigiri_reviewer_bottom_bar_bg_mode': f'match_{source}_bg'})
            self.assertIn('shared.png', self.render(source))
            self.assertIn('shared.png', self.render('reviewer_bottom_bar'))


    def test_solid_source_does_not_leak_saved_images(self):
        self.main['modern_menu_background_mode'] = 'color'
        for surface in ('overview', 'reviewer', 'reviewer_bottom_bar'):
            css = self.render(surface)
            self.assertIn('#123456', css)
            self.assertNotIn('day.png', css)

    def test_slideshow_source_list_interval_and_effects_propagate(self):
        self.main.update(modern_menu_background_mode='slideshow', modern_menu_slideshow_images=['one.png', 'two.png'],
                         modern_menu_slideshow_interval=17)
        for surface in ('overview', 'reviewer', 'reviewer_bottom_bar'):
            css = self.render(surface)
            for fragment in ('/main_bg/one.png', '/main_bg/two.png', '17000', 'blur(7.0px)', 'opacity: 0.42'):
                self.assertIn(fragment, css)
            for script in re.findall(r'<script>(.*?)</script>', css, re.S):
                import subprocess
                result = subprocess.run(['node', '--check'], input=script, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_bottom_bar_can_match_reviewer_slideshow(self):
        self.local.update(onigiri_reviewer_bg_mode='slideshow', onigiri_reviewer_slideshow_images=['r1.png', 'r2.png'],
                          onigiri_reviewer_slideshow_interval=23, onigiri_reviewer_bg_blur=15,
                          onigiri_reviewer_bg_opacity=80, onigiri_reviewer_bottom_bar_bg_mode='match_reviewer_bg')
        css = self.render('reviewer_bottom_bar')
        for fragment in ('/reviewer_bg/r1.png', '/reviewer_bg/r2.png', '23000', 'blur(3.0px)', 'opacity: 0.8'):
            self.assertIn(fragment, css)

    def test_empty_slideshow_falls_back_to_source_color(self):
        self.main['modern_menu_background_mode'] = 'slideshow'
        css = self.render('reviewer_bottom_bar')
        self.assertIn('#123456', css)
        self.assertNotIn('setInterval', css)


class WallpaperThemeIsolationTests(unittest.TestCase):
    def setUp(self):
        self.env = dict(os=os, math=math, json=json,
                        config=SimpleNamespace(get_config_readonly=lambda: {}),
                        _reviewer_bottom_bar_height_px=lambda _: 100,
                        _reviewer_background_viewport_height_px=lambda _: 800)
        load_functions('patcher.py', {'_render_background_css', '_generate_outer_background_css'}, self.env)

    def image_for_theme(self, css, selector, dark):
        """Apply the emitted background-image declarations in cascade order."""
        image = 'none'
        for selectors, declarations in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
            candidates = [part.strip() for part in selectors.split(',')]
            applies = selector in candidates or (dark and '.night-mode ' + selector in candidates)
            if applies:
                match = re.search(r'background-image:\s*([^;]+);', declarations)
                if match:
                    image = match.group(1).strip()
        return image

    def test_main_menu_renders_saved_theme_choices_independently(self):
        saved = dict(modern_menu_background_mode='image_color', modern_menu_bg_image_theme_mode='separate',
                     modern_menu_background_image='', modern_menu_background_blur=35,
                     modern_menu_background_opacity=42)
        load_functions('config.py', {'_dynamic_theme_enabled', 'themed_asset'}, self.env)
        self.env['config'].themed_asset = self.env['themed_asset']
        self.env['config'].DEFAULTS = {'colors': {'light': {'--bg': '#fff'}, 'dark': {'--bg': '#222'}}}
        self.env['mw'] = SimpleNamespace(col=SimpleNamespace(conf=saved))
        load_functions('patcher.py', {'generate_deck_browser_backgrounds', '_hex_to_rgba', '_mix_colors'}, self.env)
        for light, dark in (('day.png', ''), ('', 'night.png')):
            with self.subTest(light=light, dark=dark):
                saved.update(modern_menu_background_image_light=light, modern_menu_background_image_dark=dark)
                css = self.env['generate_deck_browser_backgrounds'](str(ROOT))
                for is_dark, expected in ((False, light), (True, dark)):
                    image = self.image_for_theme(css, '.container.modern-main-menu::before', is_dark)
                    if expected:
                        self.assertIn('/main_bg/' + expected, image)
                    else:
                        self.assertEqual(image, 'none')
                self.assertEqual(saved['modern_menu_background_image_light'], light)
                self.assertEqual(saved['modern_menu_background_image_dark'], dark)

    def test_wallpaper_is_drawn_only_in_its_selected_theme(self):
        for mode in ('image', 'image_color'):
            for light, dark in (('day.png', ''), ('', 'night.png'),
                                ('day.png', 'night.png'), ('shared.png', 'shared.png'), ('', '')):
                for surface in ('main', 'bottom_bar'):
                    with self.subTest(mode=mode, light=light, dark=dark, surface=surface):
                        if surface == 'main':
                            css = self.env['_render_background_css'](
                                '.container.modern-main-menu', mode, '#123456', '#654321',
                                light, dark, 35, str(ROOT), 'test', 42)
                            selector = '.container.modern-main-menu::before'
                        else:
                            css = self.env['_generate_outer_background_css'](
                                mode, '#123456', '#654321', light, dark, 35, 42, str(ROOT), 'center')
                            selector = '#outer::before'
                        for is_dark, expected in ((False, light), (True, dark)):
                            image = self.image_for_theme(css, selector, is_dark)
                            if expected:
                                self.assertIn('/user_files/' + expected, image)
                                self.assertIn('blur(7.0px)', css)
                                self.assertIn('opacity: 0.42', css)
                            else:
                                self.assertEqual(image, 'none')
                        if mode == 'image_color':
                            self.assertIn('#123456', css)
                            self.assertIn('#654321', css)


if __name__ == '__main__':
    unittest.main()
