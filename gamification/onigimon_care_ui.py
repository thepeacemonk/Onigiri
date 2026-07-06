from __future__ import annotations

import json
import time
from html import escape
from typing import Any, Dict, Iterable, Optional

from PyQt6.QtCore import QEvent, QTimer, QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QDialog, QVBoxLayout
from aqt import mw
from aqt.webview import AnkiWebView

from .onigimon import (
    FOOD_ITEM_KEYS,
    HAPPINESS_ITEM_KEYS,
    HYGIENE_ITEM_KEYS,
    ITEMS,
    MEDICINE_ITEM_KEYS,
    TRAINING_ITEM_KEYS,
    _addon_asset_url,
    _item_asset_url,
    _onigimon_scene_background_layer,
    _onigimon_scene_style_attr,
    _sprite_img_html,
    manager,
)
from ..translations import tr


POKESPRITE_RAW_BASE = "https://raw.githubusercontent.com/msikma/pokesprite/master/items"
COMET_SHOP_URL = "https://buymeacoffee.com/peacemonk/extras"


STATUS_DEFS = {
    "health": {
        "metric": "health",
        "icon": "system_files/system_icons/unavailable_for_users/heart.svg",
        "color": "#08c46b",
        "items": MEDICINE_ITEM_KEYS,
    },
    "happiness": {
        "metric": "happiness",
        "icon": "system_files/system_icons/unavailable_for_users/happy.svg",
        "color": "#ffbd55",
        "items": HAPPINESS_ITEM_KEYS,
    },
    "hygiene": {
        "metric": "hygiene",
        "icon": "system_files/system_icons/unavailable_for_users/soap.svg",
        "color": "#21b7d6",
        "items": HYGIENE_ITEM_KEYS,
    },
    "training": {
        "metric": "training",
        "icon": "system_files/system_icons/unavailable_for_users/bolt.svg",
        "color": "#c866e5",
        "items": TRAINING_ITEM_KEYS,
    },
    "hunger": {
        "metric": "hunger",
        "icon": "system_files/system_icons/unavailable_for_users/hamburger.svg",
        "color": "#f45bb3",
        "items": FOOD_ITEM_KEYS,
    },
}

STATUS_ORDER = ("health", "happiness", "hygiene", "training", "hunger")


def _translated_item_label(item_key: str) -> str:
    item = ITEMS.get(item_key, {})
    fallback = str(item.get("label") or item_key)
    return tr(f"onigimon_item_{item_key}", fallback)


class OnigimonCareDialog(QDialog):
    MAX_WIDTH = 980
    MAX_HEIGHT = 720

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("onigimon_care_window_title"))
        self.resize(900, 650)
        self.setMaximumSize(self.MAX_WIDTH, self.MAX_HEIGHT)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint)
        self._view = "care"
        self._selected_status = None
        self._last_clicked_status = None
        self._refresh_pending = False
        self.live_status_message = ""
        self._active_action_item = None
        self._action_item_visible_until = 0.0
        self._active_gift_reveal: Optional[Dict[str, Any]] = None

        self.web = AnkiWebView(self)
        self.web.set_bridge_command(self._on_bridge_cmd, self)

        # Allow sub-10px CSS font sizes by disabling the WebEngine minimum.
        # Without this, Anki's WebEngine clamps all font-sizes to ~12–16px,
        # making small Silkscreen labels appear enormous.
        try:
            from PyQt6.QtWebEngineCore import QWebEngineSettings
            _s = self.web.settings()
            _s.setFontSize(QWebEngineSettings.FontSize.MinimumFontSize, 0)
            _s.setFontSize(QWebEngineSettings.FontSize.MinimumLogicalFontSize, 0)
        except Exception:
            pass

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        self.render_page()

    def closeEvent(self, event):
        self._refresh_deck_browser()
        super().closeEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            blocked_state = Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen
            if self.windowState() & blocked_state:
                self.setWindowState(self.windowState() & ~blocked_state)
                self.resize(
                    min(self.width(), self.MAX_WIDTH),
                    min(self.height(), self.MAX_HEIGHT),
                )
        super().changeEvent(event)

    def _on_bridge_cmd(self, cmd: str) -> bool:
        if cmd.startswith("onigimon_status:"):
            target_status = self._normalize_status(cmd.split(":", 1)[1])
            self._selected_status = target_status
            self._last_clicked_status = target_status
            self._clear_action_item()
            self.live_status_message = ""
            self._schedule_render()
            return True
        if cmd.startswith("onigimon_feed:"):
            item_key = cmd.split(":", 1)[1]
            self._defer_action(lambda: self._use_item_and_render(item_key))
            return True
        if cmd.startswith("onigimon_interact:"):
            target_status = self._normalize_status(cmd.split(":", 1)[1])
            self._selected_status = target_status
            self._defer_action(lambda: self._interact_and_render(target_status))
            return True
        if cmd.startswith("onigimon_buy:"):
            self._clear_action_item()
            self.live_status_message = self._shorten_message(manager.purchase_market_item(cmd.split(":", 1)[1]) or "")
            self._schedule_render(160)
            return True
        if cmd == "onigimon_market_gift":
            self._clear_action_item()
            message = manager.claim_market_gift() or ""
            self.live_status_message = self._shorten_message(message)
            self._maybe_set_gift_reveal(message)
            self._schedule_render(260)
            return True
        if cmd == "onigimon_daily_gift":
            self._clear_action_item()
            message = manager.claim_daily_gift() or ""
            self.live_status_message = self._shorten_message(message)
            self._maybe_set_gift_reveal(message)
            self._schedule_render(260)
            return True
        if cmd == "onigimon_comet_shop":
            from .reward_redemption import open_reward_redeem_dialog

            self._clear_action_item()
            open_reward_redeem_dialog(self, context="onigimon")
            self._schedule_render(120)
            return True
        return False

    def _refresh_deck_browser(self) -> None:
        try:
            from .onigimon import render_widget_html
            import json
            
            new_html = render_widget_html()
            js_code = f"""
            (function() {{
                var widget = document.querySelector('.onigimon-widget');
                if (widget) {{
                    widget.outerHTML = {json.dumps(new_html)};
                }}
            }})();
            """
            
            web = getattr(mw, 'web', None)
            if web is None and getattr(mw, 'deckBrowser', None):
                web = getattr(mw.deckBrowser, 'web', None)
                
            if web:
                web.eval(js_code)
                
            # Note: We specifically DO NOT call refresh_deck_tree_state here,
            # as it freezes the UI. The JS evaluation above is enough to update
            # the background widget instantly without blocking.
                
        except Exception as e:
            print(f"Onigimon: Error refreshing deck browser: {e}")

    def _schedule_render(self, delay_ms: int = 0) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True

        def refresh() -> None:
            self._refresh_pending = False
            self.render_page()

        QTimer.singleShot(delay_ms, refresh)

    def _normalize_status(self, status: str) -> str:
        return status if status in STATUS_DEFS else "health"

    def _shorten_message(self, msg: str) -> str:
        if not msg:
            return ""
        companion = manager.active_companion()
        name = manager.companion_display_name(companion) if companion else ""
        if name and msg.startswith(name):
            msg = msg[len(name):].lstrip(" 's,.")
        msg_lower = msg.lower()
        if "daily surprise" in msg_lower or "daily gift revealed" in msg_lower:
            gift = getattr(manager, "last_gift", None) or {}
            if gift:
                amount = int(gift.get("amount") or 1)
                item_key = str(gift.get("item_key") or "")
                return f"{tr('onigimon_category_gift')}: {amount} {_translated_item_label(item_key)}"
            if "daily surprise" in msg_lower:
                parts = msg.split(":")
                if len(parts) > 1:
                    return f"{tr('onigimon_category_gift')}: {parts[1].strip().rstrip('.')}"
            return tr("onigimon_daily_gift_opened")
        if "already full" in msg_lower:
            return tr("onigimon_already_full")
        if "already purchased" in msg_lower:
            return tr("onigimon_market_already_purchased")
        if "no longer available" in msg_lower:
            return tr("onigimon_market_offer_unavailable")
        if "not have enough coins" in msg_lower:
            return tr("onigimon_market_not_enough_coins")
        if "purchased" in msg_lower:
            for key, item in ITEMS.items():
                label = item.get("label", "").lower()
                if label and label in msg_lower:
                    return tr("onigimon_market_bought_item").format(item=_translated_item_label(key))
            return tr("onigimon_market_item_purchased")
        if "enjoyed a" in msg_lower or "loved the curry" in msg_lower or "munched on" in msg_lower or "looks happier" in msg_lower:
            for key, item in ITEMS.items():
                label = item.get("label", "").lower()
                if label and label in msg_lower:
                    return tr("onigimon_ate_item").format(item=_translated_item_label(key))
            if "curry" in msg_lower:
                return tr("onigimon_ate_curry")
            if "candy" in msg_lower:
                return tr("onigimon_ate_candy")
            return tr("onigimon_ate_food")
        if "smells fresh" in msg_lower or "feels clean" in msg_lower:
            return tr("onigimon_cleaned")
        if "recovered with" in msg_lower:
            for key, item in ITEMS.items():
                label = item.get("label", "").lower()
                if label and label in msg_lower:
                    return tr("onigimon_used_item_healed").format(item=_translated_item_label(key))
            return tr("onigimon_healed")
        if "trained with" in msg_lower:
            for key, item in ITEMS.items():
                label = item.get("label", "").lower()
                if label and label in msg_lower:
                    return tr("onigimon_trained_with_item").format(item=_translated_item_label(key))
            return tr("onigimon_trained")
        if "played with" in msg_lower:
            for key, item in ITEMS.items():
                label = item.get("label", "").lower()
                if label and label in msg_lower:
                    return tr("onigimon_played_with_item").format(item=_translated_item_label(key))
            return tr("onigimon_played")
        if "gained onigimon bond xp" in msg_lower:
            return tr("onigimon_used_exp_candy")
        if "played with you" in msg_lower:
            return tr("onigimon_played_together")
        if "trained with you" in msg_lower:
            return tr("onigimon_trained_together")
        if "trained hard" in msg_lower:
            return tr("onigimon_trained_together")
        if "not in your backpack" in msg_lower:
            return tr("onigimon_item_not_backpack")
        if "study 10 cards" in msg_lower:
            return tr("onigimon_answer_10_cards")
        if "needs a little rest" in msg_lower:
            return tr("onigimon_needs_rest")
        if "too tired to train" in msg_lower:
            return tr("onigimon_too_tired_train")
        if "already opened" in msg_lower:
            return tr("onigimon_gift_opened")
        if "no" in msg_lower and "backpack" in msg_lower:
            return tr("onigimon_no_backpack_items")
        return msg

    def _defer_action(self, callback) -> None:
        QTimer.singleShot(0, callback)

    def _use_item_and_render(self, item_key: str) -> None:
        self._set_action_item(item_key)
        message = manager.use_item(item_key) or ""
        if self._item_was_rejected(message):
            self._clear_action_item()
        elif item_key == "daily_gift_action":
            self._maybe_set_gift_reveal(message)
        self.live_status_message = self._shorten_message(message)
        self._schedule_render()

    def _interact_and_render(self, status: str) -> None:
        self.live_status_message = self._shorten_message(manager.interact_with_status(status) or "")
        self._schedule_render()

    def _item_was_rejected(self, message: str) -> bool:
        msg = (message or "").lower()
        return (
            not msg
            or "already full" in msg
            or "not in your backpack" in msg
            or ("no" in msg and "backpack" in msg)
        )

    def _set_action_item(self, item_key: str) -> None:
        item = ITEMS.get(item_key, {})
        label = str(item.get("label") or item_key).strip()
        icon = _item_asset_url(item)
        self._active_action_item = {
            "key": item_key,
            "label": label,
            "icon": icon,
        }
        self._action_item_visible_until = time.monotonic() + 2.4

    def _clear_action_item(self) -> None:
        self._active_action_item = None
        self._action_item_visible_until = 0.0

    def _maybe_set_gift_reveal(self, message: str) -> None:
        if not message or "already opened" in message.lower():
            return
        gift = getattr(manager, "last_gift", None)
        if not gift:
            return
        item_key = str(gift.get("item_key") or "")
        self._active_gift_reveal = {
            "amount": int(gift.get("amount") or 1),
            "label": _translated_item_label(item_key),
            "icon": _item_asset_url(ITEMS.get(item_key, {})),
        }

    def _gift_reveal_html(self) -> str:
        gift = self._active_gift_reveal
        self._active_gift_reveal = None
        if not gift:
            return ""
        icon = str(gift.get("icon") or "")
        img = f'<img src="{escape(icon)}" alt="">' if icon else ""
        amount = int(gift.get("amount") or 1)
        label = escape(str(gift.get("label") or ""))
        return f"""
        <div class="onigimon-gift-modal-backdrop" onclick="this.remove()">
            <div class="onigimon-gift-modal" onclick="event.stopPropagation()">
                <div class="onigimon-gift-modal-icon">{img}</div>
                <div class="onigimon-gift-modal-title">{escape(tr("onigimon_daily_gift_modal_title"))}</div>
                <div class="onigimon-gift-modal-body">{escape(tr("onigimon_gift_modal_received"))}: <b>+{amount} {label}</b></div>
                <button class="onigimon-gift-modal-ok" onclick="this.closest('.onigimon-gift-modal-backdrop').remove()">{escape(tr("onigimon_word_okay"))}</button>
            </div>
        </div>
        """

    def refresh(self) -> None:
        self.render_page()

    def render_page(self):
        payload = manager.widget_payload(refresh_bridge=not getattr(self, "_first_render_done", False))
        companion = payload.get("companion")
        if not companion:
            self.web.stdHtml(f"<body><p>{escape(tr('onigimon_no_companion'))}</p></body>")
            return

        name = manager.companion_display_name(companion)
        self.setWindowTitle(f"{tr('onigimon_care_window_title')} - {name}")

        last_msg = payload.get("lastMessage")
        if last_msg:
            self.live_status_message = self._shorten_message(last_msg)

        if not self.live_status_message:
            values = payload.get("needs", {})
            lowest_metric = min(STATUS_ORDER, key=lambda k: int(values.get(k, 100)), default="health")
            lowest_val = int(values.get(lowest_metric, 100))
            if lowest_val < 50:
                if lowest_metric == "health":
                    self.live_status_message = tr("onigimon_live_hurt")
                elif lowest_metric == "hunger":
                    self.live_status_message = tr("onigimon_live_hungry")
                elif lowest_metric == "happiness":
                    self.live_status_message = tr("onigimon_live_sad")
                elif lowest_metric == "hygiene":
                    self.live_status_message = tr("onigimon_live_dirty")
                elif lowest_metric == "training":
                    self.live_status_message = tr("onigimon_live_tired")
                else:
                    self.live_status_message = tr("onigimon_live_okay")
            else:
                self.live_status_message = tr("onigimon_live_healthy")
        else:
            self.live_status_message = self._shorten_message(self.live_status_message)

        from ..patcher import generate_profile_page_background_css

        base_css = generate_profile_page_background_css()
        html = self._generate_html(payload, companion)
        night_class = "night-mode" if mw.pm.night_mode() else ""

        font_url = _addon_asset_url("system_files/fonts/system_fonts/Silkscreen.ttf")
        heart_fx_url = _addon_asset_url("system_files/system_icons/available_for_users/heart.svg")
        star_fx_url = _addon_asset_url("system_files/system_icons/unavailable_for_users/star_outline.svg")
        full_html = f"""
        <html>
        <head>
            {base_css}
            <style>
                @font-face {{
                    font-family: 'Silkscreen';
                    src: url('{font_url}') format('truetype');
                }}
                {self._style()}
            </style>
            <script>
            window._audioCtx = window._audioCtx || new (window.AudioContext || window.webkitAudioContext)();
            window._onigimonActionBusy = false;
            window._onigimonHeartFxUrl = {json.dumps(heart_fx_url)};
            window._onigimonStarFxUrl = {json.dumps(star_fx_url)};
            window._onigimonIdleItemLabel = {json.dumps(tr("onigimon_idle_item"))};
            window._onigimonFxReadyAt = ((window.performance && performance.now) ? performance.now() : Date.now()) + 520;
            window._onigimonImageCache = window._onigimonImageCache || {{}};

            function _playOscillator(type, freqs, duration, type2) {{
                if (window._audioCtx.state === 'suspended') window._audioCtx.resume();
                var t = window._audioCtx.currentTime;
                
                freqs.forEach(function(f) {{
                    var osc = window._audioCtx.createOscillator();
                    var gain = window._audioCtx.createGain();
                    osc.type = type2 || type;
                    osc.frequency.setValueAtTime(f[0], t + f[1]);
                    if (f[2]) osc.frequency.exponentialRampToValueAtTime(f[2], t + f[1] + f[3]);
                    
                    gain.gain.setValueAtTime(0, t + f[1]);
                    gain.gain.linearRampToValueAtTime(0.1, t + f[1] + 0.05);
                    gain.gain.exponentialRampToValueAtTime(0.001, t + f[1] + duration);
                    
                    osc.connect(gain);
                    gain.connect(window._audioCtx.destination);
                    osc.start(t + f[1]);
                    osc.stop(t + f[1] + duration);
                }});
            }}

            window.playSoftSound = function(effect) {{
                if (effect === 'feed') {{
                    _playOscillator('sine', [[600, 0, 800, 0.1]], 0.3);
                }} else if (effect === 'play') {{
                    _playOscillator('sine', [[800, 0], [1000, 0.1]], 0.3);
                }} else if (effect === 'clean') {{
                    _playOscillator('sine', [[300, 0, 600, 0.2]], 0.4);
                }} else if (effect === 'train') {{
                    _playOscillator('sine', [[500, 0, 1000, 0.25]], 0.3);
                }} else if (effect === 'heal') {{
                    _playOscillator('sine', [[523.25, 0], [659.25, 0.05], [783.99, 0.1]], 0.8);
                }} else {{
                    _playOscillator('sine', [[900, 0, 1200, 0.1]], 0.2);
                }}
            }};

            function _oniLayer() {{
                return document.querySelector('.onigimon-fx-layer');
            }}

            function _oniSprite() {{
                return document.querySelector('.onigimon-pokemon > img');
            }}

            function _rand(min, max) {{
                return min + Math.random() * (max - min);
            }}

            function _nowMs() {{
                return (window.performance && performance.now) ? performance.now() : Date.now();
            }}

            function _preloadFxImages(urls, done) {{
                var queue = [];
                (urls || []).forEach(function(url) {{
                    if (url && queue.indexOf(url) < 0) queue.push(url);
                }});
                if (!queue.length) {{
                    done();
                    return;
                }}
                var left = queue.length;
                var settled = false;
                function oneDone() {{
                    if (settled) return;
                    left -= 1;
                    if (left <= 0) {{
                        settled = true;
                        done();
                    }}
                }}
                window.setTimeout(function() {{
                    if (!settled) {{
                        settled = true;
                        done();
                    }}
                }}, 420);
                queue.forEach(function(url) {{
                    var img = window._onigimonImageCache[url];
                    if (img && img.complete) {{
                        oneDone();
                        return;
                    }}
                    img = new Image();
                    window._onigimonImageCache[url] = img;
                    img.onload = oneDone;
                    img.onerror = oneDone;
                    img.src = url;
                }});
            }}

            function _afterFxWarmup(urls, callback) {{
                _preloadFxImages(urls, function() {{
                    var wait = Math.max(0, window._onigimonFxReadyAt - _nowMs());
                    window.setTimeout(function() {{
                        var layer = _oniLayer();
                        if (layer) void layer.offsetWidth;
                        window.requestAnimationFrame(function() {{
                            window.requestAnimationFrame(callback);
                        }});
                    }}, wait);
                }});
            }}

            function _setActionItem(label, iconUrl) {{
                var box = document.querySelector('.onigimon-action-item');
                if (!box) return;
                var img = box.querySelector('img');
                var text = box.querySelector('.onigimon-action-item-label');
                box.classList.remove('is-idle');
                if (!label) {{
                    box.classList.add('is-idle');
                    if (img) {{
                        img.removeAttribute('src');
                        img.style.display = 'none';
                    }}
                    if (text) text.textContent = window._onigimonIdleItemLabel || 'Yawn...';
                    return;
                }}
                if (img) {{
                    if (iconUrl) {{
                        img.src = iconUrl;
                        img.style.display = '';
                    }} else {{
                        img.removeAttribute('src');
                        img.style.display = 'none';
                    }}
                }}
                if (text) text.textContent = label;
                box.classList.remove('is-idle');
                void box.offsetWidth;
            }}

            function _spawnFx(cls, duration, styles, iconUrl) {{
                var layer = _oniLayer();
                if (!layer) return null;
                while (layer.children.length > 70) layer.removeChild(layer.firstChild);
                var el = document.createElement('span');
                el.className = 'onigimon-fx ' + cls;
                if (iconUrl) {{
                    el.style.backgroundImage = 'url("' + String(iconUrl).replace(/"/g, '%22') + '")';
                }}
                Object.keys(styles || {{}}).forEach(function(key) {{
                    el.style.setProperty(key, styles[key]);
                }});
                layer.appendChild(el);
                window.setTimeout(function() {{
                    if (el.parentNode) el.parentNode.removeChild(el);
                }}, duration + 80);
                return el;
            }}

            function _pulseSprite(effect) {{
                var sprite = _oniSprite();
                if (!sprite) return;
                var cls = 'is-oni-anim-' + effect;
                ['feed', 'clean', 'train', 'play', 'heal', 'sparkle'].forEach(function(name) {{
                    sprite.classList.remove('is-oni-anim-' + name);
                }});
                void sprite.offsetWidth;
                sprite.classList.add(cls);
                window.setTimeout(function() {{
                    sprite.classList.remove(cls);
                }}, 700);
            }}

            window.onigimonSelectStatus = function(cmd, statusKey) {{
                if (window._onigimonActionBusy) return;
                document.querySelectorAll('.onigimon-bar-row').forEach(function(row) {{
                    row.classList.toggle('is-selected', row.getAttribute('data-status') === statusKey);
                }});
                _setActionItem('', '');
                window.requestAnimationFrame(function() {{
                    window.setTimeout(function() {{
                        pycmd(cmd);
                    }}, 16);
                }});
            }};

            window.playAnimation = function(effect, color, itemIcon) {{
                color = color || '#ffbd55';
                effect = effect || 'sparkle';
                _pulseSprite(effect);

                if (effect === 'feed') {{
                    var foodClass = itemIcon ? 'oni-fx-food-sprite oni-fx-feed' : 'oni-fx-fruit oni-fx-feed';
                    _spawnFx(foodClass, 840, {{
                        '--fx-color': color,
                        '--x-start': _rand(108, 150) + 'px',
                        '--y-start': _rand(-22, 26) + 'px',
                        '--x-mid': _rand(46, 82) + 'px',
                        '--y-mid': _rand(-132, -92) + 'px',
                        '--x-end': _rand(-18, 18) + 'px',
                        '--y-end': _rand(-78, -42) + 'px'
                    }}, itemIcon || '');
                    for (var heart = 0; heart < 6; heart++) {{
                        _spawnFx('oni-fx-heart-icon', _rand(920, 1240), {{
                            '--x': _rand(-126, 126) + 'px',
                            '--y-start': _rand(18, 70) + 'px',
                            '--y-end': _rand(-128, -74) + 'px',
                            '--sway': _rand(-34, 34) + 'px',
                            '--heart-size': _rand(20, 32) + 'px',
                            'animation-delay': _rand(0, 220) + 'ms'
                        }}, window._onigimonHeartFxUrl);
                    }}
                    return;
                }}

                if (effect === 'clean') {{
                    for (var b = 0; b < 22; b++) {{
                        var size = _rand(14, 32);
                        _spawnFx('oni-fx-bubble', _rand(950, 1550), {{
                            '--x': _rand(-140, 140) + 'px',
                            '--fx-size': size + 'px',
                            '--fx-color': color,
                            'animation-delay': _rand(0, 340) + 'ms'
                        }});
                    }}
                    return;
                }}

                if (effect === 'train') {{
                    for (var t = 0; t < 18; t++) {{
                        _spawnFx('oni-fx-aura', _rand(720, 1080), {{
                            '--x': _rand(-130, 130) + 'px',
                            '--y-start': _rand(42, 92) + 'px',
                            '--y-end': _rand(-142, -72) + 'px',
                            '--fx-color': color,
                            'animation-delay': _rand(0, 210) + 'ms'
                        }});
                    }}
                    return;
                }}

                if (effect === 'play') {{
                    for (var p = 0; p < 18; p++) {{
                        _spawnFx('oni-fx-star-icon', _rand(760, 1120), {{
                            '--x-end': _rand(-165, 165) + 'px',
                            '--y-end': _rand(-150, -28) + 'px',
                            '--rot': _rand(-420, 420) + 'deg',
                            '--star-size': _rand(18, 30) + 'px',
                            '--fx-color': color,
                            'animation-delay': _rand(0, 190) + 'ms'
                        }}, window._onigimonStarFxUrl);
                    }}
                    return;
                }}

                if (effect === 'heal') {{
                    for (var h = 0; h < 16; h++) {{
                        _spawnFx('oni-fx-heal', _rand(860, 1280), {{
                            '--x': _rand(-128, 128) + 'px',
                            '--y-start': _rand(42, 86) + 'px',
                            '--y-end': _rand(-148, -82) + 'px',
                            '--sway': _rand(-32, 32) + 'px',
                            '--fx-color': color,
                            'animation-delay': _rand(0, 230) + 'ms'
                        }});
                    }}
                    return;
                }}

                for (var s = 0; s < 18; s++) {{
                    _spawnFx('oni-fx-sparkle', _rand(640, 980), {{
                        '--x': _rand(-155, 155) + 'px',
                        '--y': _rand(-145, 45) + 'px',
                        '--fx-color': color,
                        'animation-delay': _rand(0, 180) + 'ms'
                    }});
                }}
            }};

            function _commitDelayForEffect(effect) {{
                if (effect === 'clean') return 1500;
                if (effect === 'heal') return 1180;
                if (effect === 'train') return 1080;
                if (effect === 'play') return 1080;
                if (effect === 'feed') return 1250;
                return 920;
            }}

            window.onigimonDoAction = function(btn, cmd, effect, color, statusKey, itemLabel, itemIcon) {{
                if (window._onigimonActionBusy) return;
                window._onigimonActionBusy = true;
                document.querySelectorAll('.onigimon-bag-item').forEach(function(itemBtn) {{
                    itemBtn.disabled = true;
                }});
                if (btn) btn.classList.add('is-pending');

                if (btn) {{
                    var countSpan = btn.querySelector('span');
                    if (countSpan) {{
                        var cnt = parseInt(countSpan.textContent) || 0;
                        if (cnt > 0) countSpan.textContent = cnt - 1;
                    }}
                }}
                
                var barRow = null;
                document.querySelectorAll('.onigimon-bar-row').forEach(function(row) {{
                    var isTarget = row.getAttribute('data-status') === statusKey;
                    row.classList.toggle('is-selected', isTarget);
                    if (isTarget) barRow = row;
                }});
                if (barRow) {{
                    var track = barRow.querySelector('.onigimon-bar-track i');
                    if (track) {{
                        var w = parseFloat(track.style.width) || 0;
                        track.style.width = Math.min(100, w + 15) + '%';
                    }}
                }}
                
                _setActionItem(itemLabel || '', itemIcon || '');
                var delay = _commitDelayForEffect(effect);
                var preloadUrls = [itemIcon || '', window._onigimonHeartFxUrl, window._onigimonStarFxUrl];
                _afterFxWarmup(preloadUrls, function() {{
                        playSoftSound(effect);
                        playAnimation(effect, color, itemIcon || '');
                        window.setTimeout(function() {{
                            pycmd(cmd);
                            window.setTimeout(function() {{
                                window._onigimonActionBusy = false;
                                document.querySelectorAll('.onigimon-bag-item').forEach(function(itemBtn) {{
                                    itemBtn.disabled = false;
                                    itemBtn.classList.remove('is-pending');
                                }});
                            }}, 2600);
                        }}, delay);
                }});
            }};
            </script>
        </head>
        <body class="{night_class}">
            {html}
        </body>
        </html>
        """
        
        if not getattr(self, '_first_render_done', False):
            self.web.stdHtml(full_html, context=self)
            self._first_render_done = True
        else:
            js_code = f"""
            (function() {{
                var htmlStr = {json.dumps(html)};
                var parser = new DOMParser();
                var newDoc = parser.parseFromString(htmlStr, 'text/html');
                window._onigimonActionBusy = false;
                
                // 1. Live status text
                var oldStatus = document.querySelector('.onigimon-live-status');
                var newStatus = newDoc.querySelector('.onigimon-live-status');
                if (oldStatus && newStatus && oldStatus.innerHTML !== newStatus.innerHTML) {{
                    oldStatus.innerHTML = newStatus.innerHTML;
                }}
                var oldActionItem = document.querySelector('.onigimon-action-item');
                var newActionItem = newDoc.querySelector('.onigimon-action-item');
                if (oldActionItem && newActionItem) {{
                    var oldActionImg = oldActionItem.querySelector('img');
                    var newActionImg = newActionItem.querySelector('img');
                    var oldActionLabel = oldActionItem.querySelector('.onigimon-action-item-label');
                    var newActionLabel = newActionItem.querySelector('.onigimon-action-item-label');
                    if (oldActionImg && newActionImg) {{
                        var nextSrc = newActionImg.getAttribute('src') || '';
                        if ((oldActionImg.getAttribute('src') || '') !== nextSrc) {{
                            if (nextSrc) {{
                                oldActionImg.src = nextSrc;
                                oldActionImg.style.display = '';
                            }} else {{
                                oldActionImg.removeAttribute('src');
                                oldActionImg.style.display = 'none';
                            }}
                        }}
                    }}
                    if (oldActionLabel && newActionLabel && oldActionLabel.textContent !== newActionLabel.textContent) {{
                        oldActionLabel.textContent = newActionLabel.textContent;
                    }}
                    oldActionItem.setAttribute('aria-hidden', 'false');
                    oldActionItem.classList.toggle('is-idle', newActionItem.classList.contains('is-idle'));
                }}
                
                // 2. Status Bars
                var oldBars = document.querySelectorAll('.onigimon-bar-row');
                var newBars = newDoc.querySelectorAll('.onigimon-bar-row');
                for(var i=0; i<oldBars.length && i<newBars.length; i++) {{
                    if (oldBars[i].className !== newBars[i].className) {{
                        oldBars[i].className = newBars[i].className;
                    }}
                    var oldTrack = oldBars[i].querySelector('.onigimon-bar-track i');
                    var newTrack = newBars[i].querySelector('.onigimon-bar-track i');
                    if (oldTrack && newTrack && oldTrack.style.width !== newTrack.style.width) {{
                        oldTrack.style.width = newTrack.style.width;
                        oldTrack.style.background = newTrack.style.background;
                    }}
                    var oldDetail = oldBars[i].querySelector('.onigimon-bar-detail');
                    var newDetail = newBars[i].querySelector('.onigimon-bar-detail');
                    if (oldDetail && newDetail && oldDetail.innerHTML !== newDetail.innerHTML) {{
                        oldDetail.innerHTML = newDetail.innerHTML;
                    }}
                }}
                
                // 3. Backpack
                var oldBag = document.querySelector('.onigimon-backpack');
                var newBag = newDoc.querySelector('.onigimon-backpack');
                if (oldBag && newBag && oldBag.innerHTML !== newBag.innerHTML) {{
                    oldBag.outerHTML = newBag.outerHTML;
                }}
                
                // 4. Story / Market
                var oldStory = document.querySelector('.onigimon-story-wrap');
                var newStory = newDoc.querySelector('.onigimon-story-wrap');
                if (oldStory && newStory && oldStory.innerHTML !== newStory.innerHTML) {{
                    oldStory.outerHTML = newStory.outerHTML;
                }}
                
                // 5. Hero status
                var oldHero = document.querySelector('.onigimon-hero');
                var newHero = newDoc.querySelector('.onigimon-hero');
                if (oldHero && newHero && oldHero.className !== newHero.className) {{
                    oldHero.className = newHero.className;
                }}
                document.querySelectorAll('.onigimon-bag-item').forEach(function(itemBtn) {{
                    itemBtn.disabled = false;
                    itemBtn.classList.remove('is-pending');
                }});

                // 6. Gift reveal modal (one-shot popup, not patched in-place like the rest)
                var newGift = newDoc.querySelector('.onigimon-gift-modal-backdrop');
                if (newGift) {{
                    document.body.appendChild(newGift);
                }}
            }})();
            """
            self.web.eval(js_code)

    def _generate_html(self, payload: Dict[str, Any], companion: Dict[str, Any]) -> str:
        values = payload.get("needs", {})
        if self._selected_status not in STATUS_DEFS:
            self._selected_status = self._lowest_status(values)

        name = escape(manager.companion_display_name(companion))
        sprite = _sprite_img_html(manager.sprite_urls_for_companion(companion), name)
        level = int(companion.get("level") or 1)

        health_value = int(values.get("health", 100))
        happiness_value = int(values.get("happiness", 100))
        hygiene_value = int(values.get("hygiene", 100))
        training_value = int(values.get("training", 100))
        hunger_value = int(values.get("hunger", 100))

        sprite_classes = []
        if health_value < 30:
            sprite_classes.append("low-hp")
        if happiness_value < 30:
            sprite_classes.append("low-happy")
        if hygiene_value < 30:
            sprite_classes.append("low-hygiene")
        if training_value < 30:
            sprite_classes.append("low-training")
        if hunger_value < 30:
            sprite_classes.append("low-hunger")

        sprite_class_attr = " " + " ".join(sprite_classes) if sprite_classes else ""
        sick_class = " is-low-health" if health_value < 30 else ""

        return f"""
        <main class="onigimon-shell">
            <section class="onigimon-hero{escape(sick_class)}" {_onigimon_scene_style_attr()}>
                {_onigimon_scene_background_layer("onigimon-hero-bg")}
                <div class="onigimon-pokemon{escape(sprite_class_attr)}">
                    {sprite}
                    <div class="onigimon-fx-layer" aria-hidden="true"></div>
                    <div class="onigimon-live-status">{escape(self.live_status_message)}</div>
                    {self._action_item_html()}
                </div>
                <div class="onigimon-bars">
                    <div class="onigimon-pill-row">
                        <div class="onigimon-pill onigimon-name onigimon-stats-btn">
                            {name}
                        </div>
                        <div class="onigimon-pill onigimon-level">{escape(tr("onigimon_level"))} {level}</div>
                    </div>
                    {self._status_bar_column(values, companion)}
                </div>
            </section>
            <section class="onigimon-bottom">
                <div class="onigimon-story-wrap">
                    {self._story_panel(payload, companion)}
                </div>
                <aside class="onigimon-backpack">
                    {self._backpack_panel(payload, companion)}
                </aside>
            </section>
            {self._gift_reveal_html()}
        </main>
        """

    def _status_value_text(self, key: str, values: Dict[str, int], companion: Dict[str, Any]) -> str:
        if key == "health":
            value = int(values.get("health", 0))
            return tr("onigimon_word_healthy") if value >= 66 else tr("onigimon_word_good") if value >= 35 else tr("onigimon_word_injured")
        return self._status_word(key, int(values.get(key, 0)))

    def _status_bar_column(self, values: Dict[str, int], companion: Dict[str, Any]) -> str:
        bits = []
        for key in STATUS_ORDER:
            definition = STATUS_DEFS[key]
            value = max(0, min(100, int(values.get(key, 0))))
            icon_url = _addon_asset_url(definition["icon"])
            selected = " is-selected" if key == self._selected_status else ""

            label = {
                "health": tr("onigimon_status_health"),
                "happiness": tr("onigimon_status_happiness"),
                "hygiene": tr("onigimon_status_hygiene"),
                "training": tr("onigimon_status_training"),
                "hunger": tr("onigimon_status_hunger"),
            }.get(key, key.title())

            if key == "health":
                detail = f"{int(companion.get('hp', 0))}"
            elif key == "happiness":
                detail = str(int(companion.get("happiness", 0) or 0))
            elif key == "hygiene":
                detail = str(int(companion.get("cleanliness", 0) or 0))
            elif key == "training":
                detail = str(int(companion.get("training", 0) or 0))
            elif key == "hunger":
                detail = str(int(companion.get("hunger", 0) or 0))
            else:
                detail = ""

            bits.append(
                f"""
                <div class="onigimon-bar-row{selected}" data-status="{escape(key)}" style="--status-color:{definition["color"]};" onclick="{escape(self._select_onclick(f'onigimon_status:{key}', key), quote=True)}">
                    <span class="onigimon-bar-label">{escape(label)}</span>
                    <b class="onigimon-bar-detail">{escape(detail)}</b>
                    <div class="onigimon-bar-track">
                        <i style="width:{value}%; background:{definition["color"]};"></i>
                    </div>
                    <button class="onigimon-action-icon" type="button" style="--status-icon:url('{escape(icon_url)}');" onclick="{escape(self._select_onclick(f'onigimon_status:{key}', key, 'event.stopPropagation();'), quote=True)}">
                        <img src="{escape(icon_url)}" alt="">
                    </button>
                </div>
                """
            )
        return "".join(bits)

    def _story_panel(self, payload: Dict[str, Any], companion: Dict[str, Any]) -> str:
        return self._market_panel(payload)

    def _backpack_panel(self, payload: Dict[str, Any], companion: Dict[str, Any]) -> str:
        status = self._selected_status
        definition = STATUS_DEFS[status]
        inventory = payload.get("inventory", {})
        items = [key for key in definition["items"] if int(inventory.get(key, 0) or 0) > 0]
        poke_icon = self._pokesprite_item_url("ball", "poke", local_key="pokeballs")
        trunk_icon = _addon_asset_url("system_files/pokesprite/items/key-item-travel-trunk.png") or self._pokesprite_item_url("key-item", "travel-trunk")
        if not items:
            item_html = (
                '<div class="onigimon-empty-backpack">'
                f'<img class="onigimon-empty-backpack-icon" src="{escape(poke_icon)}" alt="">'
                f'<span>{escape(self._empty_backpack_text(status))}</span>'
                '</div>'
            )
        else:
            item_html = "".join(self._backpack_item(key, int(inventory.get(key, 0) or 0)) for key in items)

        return f"""
        <div class="onigimon-backpack-head">
            <button class="onigimon-backpack-title">
                <img class="onigimon-backpack-title-icon" src="{escape(trunk_icon)}" alt="">
                <span>{escape(tr("onigimon_backpack"))}</span>
            </button>
        </div>
        <div class="onigimon-backpack-grid">{item_html}</div>
        """

    def _backpack_item(self, item_key: str, count: int) -> str:
        item = ITEMS.get(item_key, {})
        label = _translated_item_label(item_key)
        icon = _item_asset_url(item)
        image = f'<img src="{escape(icon)}" alt="{escape(label)}">' if icon else f"<b>{escape(label[:1])}</b>"
        effect = self._effect_for_item(item_key, self._selected_status)
        color = STATUS_DEFS.get(self._selected_status, {}).get("color", "#ffbd55")
        action_item = self._action_item_details(item_key)
        return f"""
        <button class="onigimon-bag-item" type="button" onclick="{escape(self._action_onclick(None, f'onigimon_feed:{item_key}', effect, color, self._selected_status, action_item), quote=True)}">
            {image}
            <span>{count}</span>
        </button>
        """

    def _market_panel(self, payload: Dict[str, Any]) -> str:
        wallet = payload.get("wallet", {})
        market_items = payload.get("marketItems", [])
        purchased = set(payload.get("marketPurchased", []))
        gift_ready = bool(payload.get("marketGiftReady"))
        comet_icon = _item_asset_url(ITEMS.get("valuable_comet_shard", {}))
        star_icon = _item_asset_url(ITEMS.get("valuable_star_piece", {}))
        mart_icon = _addon_asset_url("system_files/gamification_images/Mart.png")
        rows = "".join(self._market_item(item, purchased) for item in market_items)
        gift_disabled = "disabled" if not gift_ready else ""
        gift_text = tr("onigimon_daily_gift") if gift_ready else tr("onigimon_gift_opened")

        return f"""
        <div class="onigimon-market">
            <header class="onigimon-market-head">
                <div class="onigimon-market-title">
                    <img class="onigimon-market-shop-icon" src="{escape(mart_icon)}" alt="">
                    <strong>{escape(tr("onigimon_daily_market"))}</strong>
                </div>
                <div class="onigimon-wallet">
                    <span><img src="{escape(comet_icon)}" alt=""> {int(wallet.get("comet_shards", 0))}</span>
                    <span><img src="{escape(star_icon)}" alt=""> {int(wallet.get("star_pieces", 0))}</span>
                </div>
                <button class="onigimon-comet-shop-btn" type="button" onclick="event.stopPropagation(); pycmd('onigimon_comet_shop')">Redeem</button>
            </header>
            <button class="onigimon-daily-gift" {gift_disabled} onclick="pycmd('onigimon_market_gift')">{escape(gift_text)}</button>
            <div class="onigimon-market-grid">{rows}</div>
        </div>
        """

    def _market_item(self, offer: Dict[str, Any], purchased: Iterable[str]) -> str:
        item_key = str(offer.get("item_key") or "")
        item = ITEMS.get(item_key, {})
        label = _translated_item_label(item_key)
        icon = _item_asset_url(item)
        currency = str(offer.get("currency") or "comet_shards")
        coin_key = "valuable_star_piece" if currency == "star_pieces" else "valuable_comet_shard"
        coin_icon = _item_asset_url(ITEMS.get(coin_key, {}))
        slot = str(offer.get("slot") or "")
        disabled = "disabled" if slot in purchased else ""
        bought = " is-bought" if slot in purchased else ""
        amount = int(offer.get("amount") or 1)
        return f"""
        <button class="onigimon-market-card{bought}" {disabled} onclick="pycmd('onigimon_buy:{escape(slot)}')">
            <span class="onigimon-market-item-img">{self._img(icon, label)}</span>
            <span class="onigimon-market-line"></span>
            <span class="onigimon-market-price"><img src="{escape(coin_icon)}" alt=""> {int(offer.get("price") or 0)}</span>
            <small>x{amount}</small>
        </button>
        """

    def _effect_for_status(self, status: str) -> str:
        return {
            "health": "heal",
            "happiness": "play",
            "hygiene": "clean",
            "training": "train",
            "hunger": "feed",
        }.get(status, "sparkle")

    def _action_item_details(self, item_key: str) -> Dict[str, str]:
        if not item_key:
            return {}
        item = ITEMS.get(item_key, {})
        return {
            "key": item_key,
            "label": _translated_item_label(item_key),
            "icon": _item_asset_url(item),
        }

    def _action_item_html(self) -> str:
        item = self._active_action_item or {}
        if item and time.monotonic() > self._action_item_visible_until:
            self._active_action_item = None
            self._action_item_visible_until = 0.0
            item = {}
        label = str(item.get("label") or "")
        icon = str(item.get("icon") or "")
        idle = "" if label else " is-idle"
        display_label = label if label else tr("onigimon_idle_item")
        img = f'<img src="{escape(icon)}" alt="">' if icon else '<img alt="" style="display:none;">'
        return f"""
        <div class="onigimon-action-item{idle}" aria-hidden="false">
            <span class="onigimon-action-item-icon">{img}</span>
            <span class="onigimon-action-item-label">{escape(display_label)}</span>
        </div>
        """

    def _js(self, value: Any) -> str:
        return json.dumps("" if value is None else str(value))

    def _select_onclick(self, cmd: str, status_key: str, prefix: Any = None) -> str:
        before = f"{prefix} " if prefix else ""
        return f"{before}onigimonSelectStatus({self._js(cmd)}, {self._js(status_key)})"

    def _action_onclick(
        self,
        prefix: Any,
        cmd: str,
        effect: str,
        color: str,
        status_key: str,
        action_item: Optional[Dict[str, str]] = None,
    ) -> str:
        item = action_item or {}
        before = f"{prefix} " if prefix else ""
        return (
            f"{before}onigimonDoAction(this, {self._js(cmd)}, {self._js(effect)}, "
            f"{self._js(color)}, {self._js(status_key)}, "
            f"{self._js(item.get('label', ''))}, {self._js(item.get('icon', ''))})"
        )

    def _effect_for_item(self, item_key: str, status: str = "") -> str:
        if status in {"health", "hygiene", "training", "happiness", "hunger"}:
            return self._effect_for_status(status)
        if item_key in FOOD_ITEM_KEYS:
            return "feed"
        if item_key in HYGIENE_ITEM_KEYS:
            return "clean"
        if item_key in TRAINING_ITEM_KEYS:
            return "train"
        if item_key in HAPPINESS_ITEM_KEYS:
            return "play"
        if item_key in MEDICINE_ITEM_KEYS:
            return "heal"
        return "sparkle"



    def _lowest_status(self, values: Dict[str, int]) -> str:
        if not values:
            return "health"
        return min(STATUS_ORDER, key=lambda key: int(values.get(key, 0)))

    def _status_word(self, key: str, value: int) -> str:
        if key == "health":
            return tr("onigimon_word_healthy") if value >= 66 else tr("onigimon_word_healing") if value >= 35 else tr("onigimon_word_hurt")
        if key == "happiness":
            return tr("onigimon_word_happy") if value >= 66 else tr("onigimon_word_okay") if value >= 35 else tr("onigimon_word_sad")
        if key == "hygiene":
            return tr("onigimon_word_clean") if value >= 66 else tr("onigimon_word_tidy") if value >= 35 else tr("onigimon_word_dirty")
        if key == "training":
            return tr("onigimon_word_trained") if value >= 66 else tr("onigimon_word_ready") if value >= 35 else tr("onigimon_word_tired")
        if key == "hunger":
            return tr("onigimon_word_full") if value >= 66 else tr("onigimon_word_peckish") if value >= 35 else tr("onigimon_word_hungry")
        return key.title()

    def _empty_backpack_text(self, status: str) -> str:
        return {
            "health": tr("onigimon_empty_health"),
            "happiness": tr("onigimon_empty_happiness"),
            "hygiene": tr("onigimon_empty_hygiene"),
            "training": tr("onigimon_empty_training"),
            "hunger": tr("onigimon_empty_hunger"),
        }.get(status, tr("onigimon_empty_generic"))

    def _pokesprite_item_url(self, group: str, name: str, local_key: str = "") -> str:
        if local_key:
            local_url = _item_asset_url(ITEMS.get(local_key, {}))
            if local_url:
                return local_url
        return f"{POKESPRITE_RAW_BASE}/{group}/{name}.png"

    def _item_circle_colors(self, item_key: str) -> tuple[str, str]:
        colors = {
            "medicine": ("#08c46b", "#ffffff"),
            "petal_red": ("#c866e5", "#ffffff"),
            "mints": ("#21b7d6", "#ffffff"),
            "pokeballs": ("#4f9ee8", "#ffffff"),
            "poke_candies": ("#f45bb3", "#ffffff"),
            "exp_candy": ("#4f9ee8", "#ffffff"),
            "held_macho_brace": ("#c866e5", "#ffffff"),
            "held_power_weight": ("#4f9ee8", "#ffffff"),
            "play_fluffy_tail": ("#ffbd55", "#111111"),
            "battle_x_attack": ("#ffbd55", "#111111"),
            "ball_great": ("#08c46b", "#ffffff"),
        }
        if item_key.startswith("berry_"):
            return ("#08c46b", "#ffffff")
        return colors.get(item_key, ("#ffbd55", "#111111"))

    def _img(self, url: str, label: str) -> str:
        return f'<img src="{escape(url)}" alt="{escape(label)}">' if url else f"<b>{escape(label[:1])}</b>"

    def _style(self) -> str:
        return """
        * { box-sizing: border-box; }
        :root {
            --oni-bg: #ffffff;
            --oni-fg: #111111;
            --oni-panel: #eeeeee;
            --oni-panel-2: #f5f4f2;
            --oni-pill: #ffffff;
            --oni-border: #d8d5d1;
            --oni-shadow: rgba(0, 0, 0, 0.16);
            --oni-muted: #6d6d6d;
            --oni-market-premium: #efd48e;
            --oni-glass-bg: rgba(255, 255, 255, 0.22);
            --oni-glass-border: rgba(255, 255, 255, 0.35);
        }
        body.night-mode,
        .night-mode {
            --oni-bg: #171717;
            --oni-fg: #f2f2f2;
            --oni-panel: #262626;
            --oni-panel-2: #202020;
            --oni-pill: #f7f7f7;
            --oni-border: #3a3a3a;
            --oni-shadow: rgba(0, 0, 0, 0.42);
            --oni-muted: #b8b8b8;
            --oni-market-premium: #9a7a34;
            --oni-glass-bg: rgba(0, 0, 0, 0.25);
            --oni-glass-border: rgba(255, 255, 255, 0.12);
        }
        body {
            margin: 0;
            width: 100vw;
            height: 100vh;
            background: var(--oni-bg);
            color: var(--oni-fg);
            font-family: Silkscreen, Montserrat, Nunito, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 10px;
            overflow: hidden;
        }
        button {
            font-family: inherit;
            font-size: inherit;
            border: 0;
            padding: 0;
            cursor: pointer;
            -webkit-tap-highlight-color: transparent;
        }
        button:disabled {
            cursor: default;
            opacity: 0.45;
        }
        .onigimon-shell {
            width: min(100vw, 1000px);
            height: 100vh;
            margin: 0 auto;
            padding: 16px;
            display: grid;
            grid-template-rows: 260px minmax(0, 1fr);
            gap: 16px;
            background: var(--oni-bg);
            min-height: 0;
        }
        .onigimon-hero {
            position: relative;
            overflow: hidden;
            border-radius: 26px;
            border: 0;
            display: grid;
            grid-template-columns: 1fr 290px;
            gap: 16px;
            align-items: center;
            padding: 14px 18px;
            isolation: isolate;
            background: var(--oni-scene-base, #e89a36);
        }
        .onigimon-hero-bg {
            position: absolute;
            inset: -10px;
            z-index: 0;
            transform: scale(1.03);
            pointer-events: none;
        }
        .onigimon-hero::after {
            content: "";
            position: absolute;
            inset: 0;
            z-index: 1;
            background: transparent;
            pointer-events: none;
        }
        .onigimon-bars,
        .onigimon-pokemon {
            position: relative;
            z-index: 2;
        }
        .onigimon-bars {
            display: grid;
            grid-template-rows: auto repeat(5, 28px);
            gap: 8px;
            align-content: center;
            justify-self: end;
            width: 290px;
            padding: 12px;
            border-radius: 20px;
            background: var(--oni-bg);
            border: 2px solid var(--oni-border);
            box-shadow: 0 4px 16px var(--oni-shadow);
        }
        .onigimon-pill-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            width: 100%;
            margin-bottom: 4px;
        }
        .onigimon-pill {
            height: 24px;
            min-height: 24px;
            border-radius: 12px;
            background: var(--oni-bg);
            color: var(--oni-fg);
            display: grid;
            place-items: center;
            text-align: center;
            font-weight: 800;
            font-size: 10px;
            line-height: 1;
            padding: 2px 6px;
            border: 1px solid var(--oni-border);
            box-shadow: 0 2px 6px var(--oni-shadow);
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        .onigimon-pill:hover,
        .onigimon-pill:focus,
        .onigimon-pill:focus-visible,
        .onigimon-pill:active,
        .onigimon-bar-shell:hover,
        .onigimon-bar-shell:focus,
        .onigimon-bar-shell:focus-visible,
        .onigimon-bar-shell:active {
            background: var(--oni-bg);
            filter: none;
            outline: none;
            box-shadow: 0 2px 6px var(--oni-shadow);
        }
        .onigimon-name,
        .onigimon-level {
            color: var(--oni-fg);
            font-size: 10px;
        }
        .onigimon-pokemon {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 8px;
            height: 100%;
        }
        .onigimon-pokemon > img {
            max-width: 320px;
            max-height: 320px;
            object-fit: contain;
            image-rendering: pixelated;
            filter: drop-shadow(0 5px 0 rgba(0, 0, 0, 0.18));
            position: relative;
            z-index: 2;
        }
        .onigimon-live-status {
            background: var(--oni-bg);
            color: var(--oni-fg);
            padding: 6px 12px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: 800;
            text-align: center;
            max-width: 95%;
            box-shadow: 0 2px 6px var(--oni-shadow);
            border: 1px solid var(--oni-border);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            z-index: 10;
        }
        .onigimon-action-item {
            min-width: 150px;
            height: 34px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 4px 10px;
            border-radius: 12px;
            background: var(--oni-bg);
            color: var(--oni-fg);
            border: 1px solid var(--oni-border);
            box-shadow: 0 2px 6px var(--oni-shadow);
            font-size: 10px;
            font-weight: 900;
            opacity: 1;
            transform: translateY(0) scale(1);
            transition: transform 140ms ease;
            pointer-events: none;
            z-index: 10;
        }
        .onigimon-action-item:not(.is-idle) {
            transform: scale(1.02);
        }
        .onigimon-action-item.is-idle {
            color: var(--oni-muted);
        }
        .onigimon-action-item-icon {
            width: 24px;
            height: 24px;
            display: grid;
            place-items: center;
            flex: 0 0 auto;
        }
        .onigimon-action-item.is-idle .onigimon-action-item-icon {
            display: none;
        }
        .onigimon-action-item-icon img {
            width: 24px;
            height: 24px;
            object-fit: contain;
            image-rendering: pixelated;
        }
        .onigimon-action-item-label {
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .onigimon-pokemon.low-hp > img {
            filter: grayscale(100%) brightness(0.9) contrast(1.1) drop-shadow(0 5px 0 rgba(0, 0, 0, 0.18)) !important;
        }
        .onigimon-pokemon.low-happy:not(.low-hp) > img {
            filter: sepia(0.65) hue-rotate(-50deg) saturate(2.8) drop-shadow(0 0 12px rgba(220, 20, 20, 0.75)) drop-shadow(0 5px 0 rgba(0, 0, 0, 0.18)) !important;
        }
        .onigimon-pokemon.low-hygiene:not(.low-hp):not(.low-happy) > img {
            filter: sepia(0.8) hue-rotate(85deg) saturate(2.4) drop-shadow(0 0 12px rgba(46, 204, 113, 0.65)) drop-shadow(0 5px 0 rgba(0, 0, 0, 0.18)) !important;
        }
        .onigimon-pokemon.low-hunger:not(.low-hp):not(.low-happy):not(.low-hygiene) > img {
            filter: sepia(0.5) hue-rotate(185deg) saturate(2) opacity(0.72) drop-shadow(0 0 10px rgba(52, 152, 219, 0.6)) drop-shadow(0 5px 0 rgba(0, 0, 0, 0.18)) !important;
        }
        .onigimon-pokemon.low-training:not(.low-hp):not(.low-happy):not(.low-hygiene):not(.low-hunger) > img {
            filter: grayscale(30%) sepia(45%) brightness(0.8) contrast(0.9) drop-shadow(0 5px 0 rgba(0, 0, 0, 0.18)) !important;
        }
        .onigimon-pokemon > img.is-oni-anim-feed {
            animation: oni-nom 520ms cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        .onigimon-pokemon > img.is-oni-anim-clean {
            animation: oni-clean 620ms ease-in-out;
        }
        .onigimon-pokemon > img.is-oni-anim-train {
            animation: oni-train 620ms cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        .onigimon-pokemon > img.is-oni-anim-play {
            animation: oni-play 640ms ease-in-out;
        }
        .onigimon-pokemon > img.is-oni-anim-heal,
        .onigimon-pokemon > img.is-oni-anim-sparkle {
            animation: oni-heal 680ms ease-in-out;
        }
        .onigimon-fx-layer {
            position: absolute;
            left: 50%;
            top: 47%;
            width: min(340px, 92%);
            height: 245px;
            transform: translate(-50%, -50%);
            pointer-events: none;
            overflow: visible;
            z-index: 8;
        }
        .onigimon-fx {
            position: absolute;
            left: 50%;
            top: 50%;
            pointer-events: none;
            will-change: transform, opacity;
            --fx-color: #ffbd55;
        }
        .oni-fx-fruit {
            width: 40px;
            height: 40px;
            border-radius: 45% 55% 50% 50%;
            background: radial-gradient(circle at 35% 30%, #ffffff 0 13%, var(--fx-color) 14% 72%, rgba(60, 0, 30, 0.92) 100%);
            border: 2px solid rgba(255, 255, 255, 0.75);
            box-shadow: inset -5px -6px 0 rgba(0, 0, 0, 0.16), 0 0 16px var(--fx-color), 0 5px 0 rgba(0, 0, 0, 0.18);
        }
        .oni-fx-fruit::before {
            content: "";
            position: absolute;
            width: 15px;
            height: 8px;
            left: 16px;
            top: -6px;
            border-radius: 80% 20%;
            background: #3fc46b;
            transform: rotate(-24deg);
        }
        .oni-fx-food-sprite {
            width: 54px;
            height: 54px;
            background-position: center;
            background-repeat: no-repeat;
            background-size: contain;
            image-rendering: pixelated;
            filter: drop-shadow(0 0 14px var(--fx-color)) drop-shadow(0 5px 0 rgba(0, 0, 0, 0.2));
        }
        .oni-fx-feed {
            animation: oni-feed-throw 840ms cubic-bezier(0.25, 0.8, 0.25, 1) both;
        }
        .oni-fx-heart-icon {
            width: var(--heart-size, 20px);
            height: var(--heart-size, 20px);
            background-position: center;
            background-repeat: no-repeat;
            background-size: contain;
            filter: brightness(0) saturate(100%) invert(57%) sepia(96%) saturate(1905%) hue-rotate(292deg) brightness(101%) contrast(91%) drop-shadow(0 0 8px rgba(244, 91, 179, 0.75)) drop-shadow(0 2px 0 rgba(0, 0, 0, 0.16));
            animation: oni-heart-float 1100ms ease-out both;
        }
        .oni-fx-bubble {
            width: var(--fx-size, 16px);
            height: var(--fx-size, 16px);
            border-radius: 999px;
            border: 2px solid var(--fx-color);
            background: radial-gradient(circle at 35% 30%, rgba(255,255,255,0.96), rgba(255,255,255,0.32) 34%, rgba(255,255,255,0.1) 100%);
            box-shadow: inset -2px -3px 0 rgba(255,255,255,0.22), 0 0 14px var(--fx-color);
            animation: oni-bubble-rise 1200ms ease-out both;
        }
        .oni-fx-aura {
            width: 22px;
            height: 40px;
            background: var(--fx-color);
            clip-path: polygon(52% 0, 100% 0, 66% 40%, 100% 40%, 26% 100%, 42% 55%, 0 55%);
            filter: drop-shadow(0 0 12px var(--fx-color)) drop-shadow(0 0 4px #ffffff);
            animation: oni-train-aura 760ms ease-out both;
        }
        .oni-fx-star-icon {
            width: var(--star-size, 24px);
            height: var(--star-size, 24px);
            background-position: center;
            background-repeat: no-repeat;
            background-size: contain;
            filter: brightness(0) saturate(100%) invert(79%) sepia(66%) saturate(1053%) hue-rotate(320deg) brightness(104%) contrast(101%) drop-shadow(0 0 12px var(--fx-color)) drop-shadow(0 0 3px #ffffff);
            animation: oni-play-burst 820ms cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .oni-fx-heal {
            width: 32px;
            height: 32px;
            filter: drop-shadow(0 0 13px var(--fx-color)) drop-shadow(0 0 4px #ffffff);
            animation: oni-heal-rise 980ms ease-out both;
        }
        .oni-fx-heal::before,
        .oni-fx-heal::after {
            content: "";
            position: absolute;
            inset: 12px 3px;
            border-radius: 3px;
            background: var(--fx-color);
        }
        .oni-fx-heal::after {
            transform: rotate(90deg);
        }
        .oni-fx-sparkle {
            width: 20px;
            height: 20px;
            background: var(--fx-color);
            clip-path: polygon(50% 0, 62% 36%, 100% 50%, 62% 64%, 50% 100%, 38% 64%, 0 50%, 38% 36%);
            filter: drop-shadow(0 0 12px var(--fx-color)) drop-shadow(0 0 3px #ffffff);
            animation: oni-sparkle 680ms ease-out both;
        }
        .onigimon-bar-row {
            display: grid;
            grid-template-columns: 80px 40px minmax(0, 1fr) 24px;
            gap: 8px;
            align-items: center;
            height: 28px;
            cursor: pointer;
            border-radius: 8px;
            padding: 2px 6px;
        }
        .onigimon-bar-label {
            font-family: var(--font-main), Nunito, system-ui, sans-serif;
            font-weight: 700;
            font-size: 11px;
            color: var(--oni-fg);
            text-align: left;
        }
        .onigimon-bar-detail {
            font-family: var(--font-main), Nunito, system-ui, sans-serif;
            font-weight: 800;
            font-size: 11px;
            color: var(--status-color);
            text-align: right;
            font-variant-numeric: tabular-nums;
            padding-right: 4px;
        }
        .onigimon-bar-track {
            height: 8px;
            border-radius: 999px;
            overflow: hidden;
            background: rgba(255, 255, 255, 0.25);
            border: 1px solid rgba(255, 255, 255, 0.1);
            position: relative;
        }
        body.night-mode .onigimon-bar-track {
            background: rgba(0, 0, 0, 0.35);
            border-color: rgba(255, 255, 255, 0.05);
        }
        .onigimon-bar-track i {
            display: block;
            height: 100%;
            border-radius: inherit;
            transition: width 300ms cubic-bezier(0.4, 0, 0.2, 1);
        }
        .onigimon-action-icon,
        .onigimon-backpack-icon {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: var(--oni-bg);
            border: 1px solid var(--oni-border);
            display: grid;
            place-items: center;
            justify-self: center;
            align-self: center;
            box-shadow: 0 2px 4px var(--oni-shadow);
            line-height: 1;
            cursor: pointer;
            transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
        }
        .onigimon-action-icon::before {
            content: "";
            width: 12px;
            height: 12px;
            background: var(--status-color);
            mask: var(--status-icon) center / contain no-repeat;
            -webkit-mask: var(--status-icon) center / contain no-repeat;
            transition: background-color 150ms ease;
        }
        .onigimon-action-icon:hover::before,
        .onigimon-action-icon:focus-visible::before {
            background: #ffffff;
        }
        .onigimon-action-icon:hover,
        .onigimon-action-icon:focus,
        .onigimon-action-icon:focus-visible,
        .onigimon-action-icon:active {
            background: var(--status-color);
            border-color: var(--status-color);
            outline: none;
        }
        .onigimon-action-icon:hover {
            transform: scale(1.1);
            box-shadow: 0 3px 8px var(--oni-shadow);
        }
        .onigimon-action-icon img,
        .onigimon-backpack-icon img {
            width: 15px;
            height: 15px;
            object-fit: contain;
        }
        .onigimon-action-icon img {
            display: none;
        }
        .onigimon-bar-row.is-selected .onigimon-action-icon {
            background: var(--status-color);
            border-color: var(--status-color);
            box-shadow: 0 3px 8px var(--oni-shadow);
        }
        .onigimon-bar-row.is-selected .onigimon-action-icon::before {
            background: #ffffff;
        }
        .onigimon-bar-row.is-selected .onigimon-action-icon:hover,
        .onigimon-bar-row.is-selected .onigimon-action-icon:focus,
        .onigimon-bar-row.is-selected .onigimon-action-icon:focus-visible,
        .onigimon-bar-row.is-selected .onigimon-action-icon:active {
            background: var(--status-color);
        }
        .onigimon-bar-row.is-selected .onigimon-action-icon:hover::before,
        .onigimon-bar-row.is-selected .onigimon-action-icon:focus-visible::before {
            background: #ffffff;
        }
        .onigimon-bottom {
            display: grid;
            grid-template-columns: minmax(0, 1.22fr) minmax(290px, 0.78fr);
            gap: 24px;
            min-height: 0;
        }
        .onigimon-story-wrap {
            display: grid;
            grid-template-rows: minmax(0, 1fr);
            gap: 0;
            min-width: 0;
            min-height: 0;
        }
        .onigimon-story {
            border-radius: 22px;
            background: var(--oni-panel);
            display: grid;
            place-items: center;
            padding: 22px;
            min-height: 0;
            color: var(--oni-fg);
        }
        .onigimon-story p {
            margin: 0;
            max-width: 600px;
            text-align: center;
            font-size: 21px;
            line-height: 1.25;
            font-weight: 900;
        }
        .onigimon-market-button,
        .onigimon-backpack-title {
            min-height: 40px;
            border-radius: 999px;
            background: var(--oni-panel);
            color: var(--oni-fg);
            font-size: 14px;
            line-height: 1;
            font-weight: 900;
            padding: 6px 14px;
            box-shadow: 0 2px 4px var(--oni-shadow);
        }
        .onigimon-backpack {
            display: grid;
            grid-template-rows: 40px minmax(0, 1fr);
            gap: 8px;
            min-height: 0;
        }
        .onigimon-backpack-head {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0;
            align-items: center;
        }
        .onigimon-backpack-icon {
            width: 40px;
            height: 40px;
            background: var(--oni-panel);
        }
        .onigimon-backpack-title {
            width: 100%;
            min-height: 36px;
            font-size: 12px;
            cursor: default;
            pointer-events: none;
            background: var(--oni-panel);
            border-radius: 999px;
            color: var(--oni-fg);
            font-weight: 900;
            line-height: 1;
            padding: 6px 16px;
            box-shadow: 0 2px 4px var(--oni-shadow);
            display: grid;
            grid-template-columns: 28px 1fr 28px;
            align-items: center;
            justify-items: center;
            gap: 8px;
        }
        .onigimon-backpack-title-icon {
            width: 24px;
            height: 24px;
            object-fit: contain;
            image-rendering: pixelated;
            justify-self: start;
            filter: drop-shadow(0 2px 0 rgba(0, 0, 0, 0.18));
        }
        .onigimon-backpack-title span {
            grid-column: 2;
        }
        .onigimon-market-button:hover,
        .onigimon-market-button:focus,
        .onigimon-market-button:active,
        .onigimon-bag-item:hover,
        .onigimon-bag-item:focus,
        .onigimon-bag-item:active,
        .onigimon-market-card:hover,
        .onigimon-market-card:focus,
        .onigimon-market-card:active,
        .onigimon-daily-gift:hover,
        .onigimon-daily-gift:focus,
        .onigimon-daily-gift:active {
            filter: none;
            outline: none;
        }
        .onigimon-backpack-grid {
            position: relative;
            display: grid;
            grid-template-columns: repeat(5, 48px);
            gap: 10px 10px;
            justify-content: start;
            align-content: start;
            overflow: auto;
            padding: 4px 2px 8px;
            min-height: 0;
            height: 100%;
        }
        .onigimon-bag-item {
            position: relative;
            width: 48px;
            height: 48px;
            border-radius: 10px;
            display: grid;
            place-items: center;
            background: var(--oni-panel-2);
            border: 1px solid var(--oni-border);
            box-shadow: 0 1px 3px var(--oni-shadow);
        }
        .night-mode .onigimon-bag-item {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.15);
        }
        .onigimon-bag-item:hover {
            background: var(--oni-panel);
            border-color: var(--oni-fg);
        }
        .onigimon-bag-item.is-pending {
            opacity: 0.7;
            transform: scale(0.94);
        }
        .night-mode .onigimon-bag-item:hover {
            background: rgba(255, 255, 255, 0.12);
        }
        .onigimon-bag-item img {
            width: 32px;
            height: 32px;
            object-fit: contain;
            image-rendering: pixelated;
        }
        .onigimon-bag-item span {
            position: absolute;
            right: -2px;
            bottom: -2px;
            min-width: 22px;
            height: 22px;
            padding: 0 5px;
            border-radius: 999px;
            display: grid;
            place-items: center;
            background: rgba(255, 255, 255, 0.95);
            color: #000000;
            font-size: 11px;
            font-weight: 900;
            border: 1px solid var(--oni-border);
        }
        .onigimon-empty-backpack {
            position: absolute;
            inset: 0;
            display: grid;
            align-content: center;
            justify-items: center;
            gap: 14px;
            color: var(--oni-muted);
            font-size: 15px;
            font-weight: 800;
            text-align: center;
            padding: 28px 8px;
        }
        .onigimon-empty-backpack-icon {
            width: 46px;
            height: 46px;
            object-fit: contain;
            image-rendering: pixelated;
            filter: drop-shadow(0 3px 0 rgba(0, 0, 0, 0.22));
        }
        .onigimon-market {
            height: 100%;
            min-height: 0;
            display: grid;
            grid-template-rows: minmax(32px, auto) 42px minmax(0, 1fr);
            gap: 8px;
            overflow: hidden;
            width: 100%;
            border-radius: 22px;
            background: var(--oni-panel);
            padding: 12px;
        }
        .onigimon-market-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            color: var(--oni-muted);
            border-bottom: 2px solid var(--oni-border);
            padding-bottom: 4px;
            min-width: 0;
        }
        .onigimon-market-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            font-weight: 900;
            min-width: 0;
            flex: 1 1 auto;
        }
        .onigimon-market-title strong {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .onigimon-market-shop-icon {
            width: 20px;
            height: 20px;
            object-fit: contain;
            image-rendering: pixelated;
            display: inline-block;
            flex: 0 0 auto;
        }
        .onigimon-comet-shop-btn {
            flex: 0 0 auto;
            height: 24px;
            box-sizing: border-box;
            border: 2px solid #f7d676;
            border-radius: 12px;
            background: #ffbd24;
            color: #3b2606;
            cursor: pointer;
            font-family: Silkscreen, "SpaceMono", monospace;
            font-size: 10px;
            font-weight: 900;
            line-height: 1;
            padding: 0 10px;
            white-space: nowrap;
            box-shadow: 0 2px 0 rgba(75, 45, 10, 0.28);
        }
        .onigimon-comet-shop-btn:hover {
            background: #ffd45a;
            border-color: #f7d676;
            box-shadow: 0 2px 0 rgba(75, 45, 10, 0.28);
        }
        .onigimon-wallet {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #ffbd24;
            font-size: 13px;
            font-weight: 900;
            flex: 0 0 auto;
            padding-right: 4px;
        }
        .onigimon-wallet span,
        .onigimon-market-price {
            display: inline-flex;
            align-items: center;
            gap: 7px;
        }
        .onigimon-wallet img,
        .onigimon-market-price img {
            width: 14px;
            height: 14px;
            image-rendering: pixelated;
        }
        .onigimon-daily-gift {
            width: 100%;
            height: 42px;
            border-radius: 20px;
            background: var(--oni-panel-2);
            border: 2px solid var(--oni-border);
            color: var(--oni-muted);
            font-family: Silkscreen, "SpaceMono", monospace;
            font-size: 14px;
            font-weight: 900;
            box-shadow: 0 2px 4px var(--oni-shadow);
        }
        .onigimon-market-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(72px, 1fr));
            gap: 8px;
            overflow: auto;
            padding: 2px 2px 8px;
            min-height: 0;
        }
        @keyframes oni-feed-throw {
            0% {
                opacity: 0;
                transform: translate(var(--x-start), var(--y-start)) scale(0.45) rotate(0deg);
            }
            15% {
                opacity: 1;
            }
            45% {
                opacity: 1;
                transform: translate(var(--x-mid), var(--y-mid)) scale(1.18) rotate(180deg);
            }
            78% {
                opacity: 1;
                transform: translate(var(--x-end), var(--y-end)) scale(0.9) rotate(320deg);
            }
            100% {
                opacity: 0;
                transform: translate(var(--x-end), var(--y-end)) scale(0.28) rotate(380deg);
            }
        }
        @keyframes oni-heart-float {
            0% {
                opacity: 0;
                transform: translate(calc(-50% + var(--x) * 0.15), var(--y-start)) scale(0.25) rotate(-8deg);
            }
            20% {
                opacity: 1;
            }
            78% {
                opacity: 1;
            }
            100% {
                opacity: 0;
                transform: translate(calc(-50% + var(--x) + var(--sway, 0px)), var(--y-end)) scale(1.18) rotate(12deg);
            }
        }
        @keyframes oni-bubble-rise {
            0% { opacity: 0; transform: translate(calc(-50% + var(--x) * 0.35), 78px) scale(0.35); }
            24% { opacity: 1; }
            100% { opacity: 0; transform: translate(calc(-50% + var(--x)), -120px) scale(1.2); }
        }
        @keyframes oni-train-aura {
            0% {
                opacity: 0;
                transform: translate(var(--x), var(--y-start)) scale(0.4) rotate(0deg);
                filter: brightness(1.3);
            }
            20% {
                opacity: 1;
            }
            100% {
                opacity: 0;
                transform: translate(var(--x), var(--y-end)) scale(0.9) rotate(180deg);
            }
        }
        @keyframes oni-play-burst {
            0% {
                opacity: 0;
                transform: translate(-50%, -50%) scale(0.2) rotate(0deg);
            }
            15% {
                opacity: 1;
            }
            100% {
                opacity: 0;
                transform: translate(var(--x-end), var(--y-end)) scale(1) rotate(var(--rot, 360deg));
            }
        }
        @keyframes oni-heal-rise {
            0% {
                opacity: 0;
                transform: translate(var(--x), var(--y-start)) scale(0.5);
            }
            20% {
                opacity: 1;
            }
            80% {
                opacity: 1;
            }
            100% {
                opacity: 0;
                transform: translate(calc(var(--x) + var(--sway, 20px)), var(--y-end)) scale(1.1);
            }
        }
        @keyframes oni-sparkle {
            0% { opacity: 0; transform: translate(calc(-50% + var(--x) * 0.2), calc(-50% + var(--y) * 0.2)) scale(0.2); }
            34% { opacity: 1; }
            100% { opacity: 0; transform: translate(calc(-50% + var(--x)), calc(-50% + var(--y))) scale(1); }
        }
        @keyframes oni-nom {
            0%, 100% { transform: translateY(0) scale(1); }
            38% { transform: translateY(5px) scale(1.08, 0.94); }
            62% { transform: translateY(-3px) scale(0.97, 1.04); }
        }
        @keyframes oni-clean {
            0%, 100% { transform: translateX(0); filter: drop-shadow(0 5px 0 rgba(0, 0, 0, 0.18)); }
            24% { transform: translateX(-5px) rotate(-2deg); filter: saturate(1.3) brightness(1.08) drop-shadow(0 5px 0 rgba(0, 0, 0, 0.18)); }
            52% { transform: translateX(5px) rotate(2deg); }
        }
        @keyframes oni-train {
            0%, 100% { transform: translateY(0) scale(1); }
            24% { transform: translateY(-10px) scale(1.04); }
            52% { transform: translateY(0) scale(0.98, 1.05); }
        }
        @keyframes oni-play {
            0%, 100% { transform: rotate(0deg) translateY(0); }
            30% { transform: rotate(-7deg) translateY(-8px); }
            62% { transform: rotate(7deg) translateY(-5px); }
        }
        @keyframes oni-heal {
            0%, 100% { transform: scale(1); filter: drop-shadow(0 5px 0 rgba(0, 0, 0, 0.18)); }
            42% { transform: scale(1.06); filter: brightness(1.18) saturate(1.2) drop-shadow(0 5px 0 rgba(0, 0, 0, 0.18)); }
        }
        .onigimon-market-card {
            position: relative;
            min-height: 96px;
            border-radius: 14px;
            background: var(--oni-panel-2);
            border: 2px solid var(--oni-border);
            color: var(--oni-fg);
            display: grid;
            grid-template-rows: 1fr 2px 28px;
            align-items: center;
            justify-items: center;
            padding: 8px 6px 4px;
            font-family: Silkscreen, "SpaceMono", monospace;
            font-size: 14px;
            box-shadow: 0 2px 4px var(--oni-shadow);
        }
        .onigimon-market-card:nth-child(n+5) {
            border-color: var(--oni-market-premium);
        }
        .onigimon-market-card.is-bought {
            filter: grayscale(1);
        }
        .onigimon-market-item-img img {
            width: 28px;
            height: 28px;
            object-fit: contain;
            image-rendering: pixelated;
        }
        .onigimon-market-line {
            width: 82%;
            height: 2px;
            background: var(--oni-border);
        }
        .onigimon-market-card small {
            position: absolute;
            right: 7px;
            top: 5px;
            color: var(--oni-muted);
            font-size: 11px;
            font-weight: 900;
        }
        .onigimon-stats-btn {
            position: relative;
        }
        .onigimon-gift-modal-backdrop {
            position: fixed;
            inset: 0;
            display: grid;
            place-items: center;
            background: rgba(0, 0, 0, 0.55);
            z-index: 1000;
            animation: oni-gift-fade-in 160ms ease-out;
        }
        .onigimon-gift-modal {
            width: min(320px, 86vw);
            display: grid;
            justify-items: center;
            gap: 10px;
            padding: 22px 20px 18px;
            border-radius: 22px;
            background: var(--oni-bg);
            color: var(--oni-fg);
            border: 2px solid var(--oni-border);
            box-shadow: 0 14px 32px rgba(0, 0, 0, 0.35);
            text-align: center;
            animation: oni-gift-pop-in 280ms cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        .onigimon-gift-modal-icon {
            width: 64px;
            height: 64px;
            display: grid;
            place-items: center;
        }
        .onigimon-gift-modal-icon img {
            width: 64px;
            height: 64px;
            object-fit: contain;
            image-rendering: pixelated;
            filter: drop-shadow(0 4px 0 rgba(0, 0, 0, 0.18));
        }
        .onigimon-gift-modal-title {
            font-size: 16px;
            font-weight: 900;
            letter-spacing: 0.02em;
        }
        .onigimon-gift-modal-body {
            font-size: 12px;
            color: var(--oni-muted);
            line-height: 1.4;
        }
        .onigimon-gift-modal-body b {
            color: var(--oni-fg);
        }
        .onigimon-gift-modal-ok {
            margin-top: 6px;
            min-width: 110px;
            height: 36px;
            border-radius: 16px;
            background: var(--oni-panel-2);
            color: var(--oni-fg);
            border: 2px solid var(--oni-border);
            font-family: Silkscreen, "SpaceMono", monospace;
            font-size: 12px;
            font-weight: 900;
            box-shadow: 0 2px 4px var(--oni-shadow);
        }
        .onigimon-gift-modal-ok:hover {
            background: var(--oni-panel);
        }
        @keyframes oni-gift-fade-in {
            0% { opacity: 0; }
            100% { opacity: 1; }
        }
        @keyframes oni-gift-pop-in {
            0% { opacity: 0; transform: scale(0.7) translateY(12px); }
            100% { opacity: 1; transform: scale(1) translateY(0); }
        }
        """
