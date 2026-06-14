from PyQt6.QtWidgets import QDialog, QVBoxLayout
from aqt.webview import AnkiWebView
from aqt import mw
import json
from html import escape

from .onigimon import (
    manager,
    _item_icon,
    _category_button_html,
    _category_panel_html,
    ITEMS,
    BERRY_KEYS,
    _addon_asset_url,
    _onigimon_scene_style_attr,
    _onigimon_scene_background_layer
)


def _care_notice_script(message: str) -> str:
    return """
    (function(){
        var message = %s;
        var existing = document.getElementById('onigimon-care-notice');
        if (existing) existing.remove();

        var notice = document.createElement('div');
        notice.id = 'onigimon-care-notice';
        notice.textContent = message;
        notice.style.cssText = [
            'position:fixed',
            'top:16px',
            'left:50%%',
            'transform:translateX(-50%%) translateY(-8px)',
            'box-sizing:border-box',
            'width:min(520px,calc(100vw - 32px))',
            'padding:16px 20px',
            'border-radius:18px',
            'border:1px solid rgba(112,198,166,.45)',
            'background:rgba(255,255,255,.96)',
            'color:#1f3528',
            'box-shadow:0 18px 42px rgba(15,23,42,.22)',
            'font:700 16px/1.35 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif',
            'text-align:center',
            'z-index:2147483647',
            'opacity:0',
            'transition:opacity 180ms ease,transform 220ms cubic-bezier(.16,1,.3,1)',
            'pointer-events:auto'
        ].join(';');
        document.body.appendChild(notice);

        requestAnimationFrame(function(){
            requestAnimationFrame(function(){
                notice.style.opacity = '1';
                notice.style.transform = 'translateX(-50%%) translateY(0)';
            });
        });

        var hide = function(){
            notice.style.opacity = '0';
            notice.style.transform = 'translateX(-50%%) translateY(-8px)';
            setTimeout(function(){ notice.remove(); }, 240);
        };
        var timer = setTimeout(hide, 3600);
        notice.addEventListener('click', function(){
            clearTimeout(timer);
            hide();
        });
    })();
    """ % json.dumps(str(message or ""), ensure_ascii=False)


class OnigimonCareDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Onigimon Care")
        self.resize(480, 700)
        
        self.web = AnkiWebView(self)
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        self._pending_notice = ""
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)
        
        self.render_page()

    def _on_bridge_cmd(self, cmd: str) -> bool:
        if cmd.startswith("onigimon_feed:"):
            item_key = cmd.split(":", 1)[1]
            message = manager.use_item(item_key)
            self._pending_notice = message or "No Onigimon item available."
            self.render_page()
            mw.deckBrowser.refresh()
            return True
        elif cmd.startswith("onigimon_category:"):
            category_id = cmd.split(":", 1)[1]
            message = manager.category_status_message(category_id)
            if message:
                self.web.eval(_care_notice_script(message))
            return True
        elif cmd == "onigimon_play":
            message = manager.play()
            self._pending_notice = message or ""
            self.render_page()
            mw.deckBrowser.refresh()
            return True
        elif cmd == "onigimon_daily_gift":
            message = manager.claim_daily_gift()
            self._pending_notice = message or "Today's Onigimon gift is already claimed."
            self.render_page()
            mw.deckBrowser.refresh()
            return True
        return False

    def render_page(self):
        payload = manager.widget_payload()
        companion = payload.get("companion")
        if not companion:
            self.web.stdHtml("<body><p>No companion found.</p></body>")
            return
            
        name = companion.get('display_name') or companion.get('name') or "Companion"
        self.setWindowTitle(f"Onigimon Care - {name}")

        html_content = self._generate_html(payload, companion)
        notice_script = ""
        if self._pending_notice:
            notice_script = "<script>" + _care_notice_script(self._pending_notice) + "</script>"
            self._pending_notice = ""
        
        # Use the same CSS generation as the profile page to keep consistency
        from ..patcher import generate_profile_page_background_css
        base_css = generate_profile_page_background_css()
        
        full_html = f"""
        <html>
        <head>
            {base_css}
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background-color: var(--canvas, #f0f0f0);
                    color: var(--fg, #333);
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    overflow: hidden;
                }}
        .onigimon-care-modal {{
            position: fixed;
            inset: 0;
            z-index: 10000;
            display: none;
            place-items: center;
            padding: 18px;
            background: rgba(0, 0, 0, 0.42);
            box-sizing: border-box;
        }}

        .onigimon-care-modal.is-open {{
            display: grid;
        }}

        .onigimon-care-dialog {{
            position: relative;
            width: min(720px, calc(100vw - 36px));
            display: grid;
            gap: 14px;
            padding: 18px;
            border-radius: 14px;
            border: 1px solid var(--border, #e0e0e0);
            background: var(--canvas, #ffffff);
            color: var(--fg, #222);
            box-shadow: 0 18px 48px rgba(0, 0, 0, 0.24);
            box-sizing: border-box;
        }}

        .onigimon-care-dialog h3 {{
            margin: 0;
            padding-right: 34px;
            font-size: 18px;
        }}

        #onigimon-care-modal .onigimon-modal-close {{
            --onigimon-close-bg: rgba(20, 20, 20, 0.08);
            --onigimon-close-fg: #222222;
            position: absolute;
            top: 10px;
            right: 10px;
            width: 28px;
            height: 28px;
            border: 0 !important;
            border-radius: 999px;
            background: var(--onigimon-close-bg) !important;
            color: var(--onigimon-close-fg) !important;
            cursor: pointer;
            line-height: 1;
            outline: none !important;
            box-shadow: none !important;
            transform: none !important;
            transition: none !important;
            animation: none !important;
            -webkit-tap-highlight-color: transparent;
        }}

        #onigimon-care-modal .onigimon-modal-close:hover,
        #onigimon-care-modal .onigimon-modal-close:active,
        #onigimon-care-modal .onigimon-modal-close:focus,
        #onigimon-care-modal .onigimon-modal-close:focus-visible {{
            border: 0 !important;
            background: var(--onigimon-close-bg) !important;
            color: var(--onigimon-close-fg) !important;
            outline: none !important;
            box-shadow: none !important;
            transform: none !important;
            transition: none !important;
            animation: none !important;
        }}

        .night #onigimon-care-modal .onigimon-modal-close,
        .night-mode #onigimon-care-modal .onigimon-modal-close,
        .nightMode #onigimon-care-modal .onigimon-modal-close {{
            --onigimon-close-bg: rgba(255, 255, 255, 0.12);
            --onigimon-close-fg: #f2f2f2;
        }}

        #onigimon-care-modal .onigimon-close-icon {{
            width: 18px;
            height: 18px;
            display: block;
            margin: auto;
            pointer-events: none;
            background-color: var(--onigimon-close-fg) !important;
            mask-size: contain;
            -webkit-mask-size: contain;
            mask-repeat: no-repeat;
            -webkit-mask-repeat: no-repeat;
            mask-position: center;
            -webkit-mask-position: center;
            transform: none !important;
            transition: none !important;
            animation: none !important;
        }}

        #onigimon-care-modal .onigimon-modal-close:hover .onigimon-close-icon,
        #onigimon-care-modal .onigimon-modal-close:active .onigimon-close-icon,
        #onigimon-care-modal .onigimon-modal-close:focus .onigimon-close-icon {{
            background-color: var(--onigimon-close-fg) !important;
            transform: none !important;
            transition: none !important;
            animation: none !important;
        }}

        .onigimon-care-actions {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
        }}

        .onigimon-care-actions button {{
            min-width: 0;
            display: grid;
            justify-items: center;
            gap: 5px;
            border: 1px solid var(--border, #e0e0e0);
            border-radius: 10px;
            padding: 10px 8px;
            background: var(--canvas-inset, #f6f6f6);
            color: inherit;
            cursor: pointer;
        }}

        .onigimon-care-actions button:disabled {{
            opacity: 0.45;
            cursor: default;
        }}

        .onigimon-care-actions .onigimon-item-icon {{
            width: 30px;
            height: 30px;
        }}

        .onigimon-care-actions span {{
            font-weight: 600;
            font-size: 13px;
        }}

        .onigimon-care-actions small {{
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--fg-subtle, #757575);
            font-size: 11px;
        }}

        .onigimon-category-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .onigimon-category-chip {{
            min-width: 0;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border: 1px solid transparent;
            border-radius: 999px;
            padding: 6px 10px;
            background: var(--canvas-inset, #f6f6f6);
            color: inherit;
            cursor: pointer;
            font-size: 12px;
        }}

        .onigimon-category-chip:disabled {{
            opacity: 0.45;
            cursor: default;
        }}

        .onigimon-category-chip:not(:disabled):hover {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
        }}

        .onigimon-category-chip.is-selected {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
            background: var(--onigimon-item-bg-light, color-mix(in srgb, var(--accent-color, #007aff) 18%, transparent));
        }}

        .onigimon-category-chip[data-category="treats"]:not(:disabled):hover {{
            border-color: #ff6fc8;
        }}

        .onigimon-category-chip[data-category="treats"].is-selected {{
            border-color: #ff6fc8;
            background: #ffe0f3;
        }}

        .night .onigimon-category-chip[data-category="treats"].is-selected,
        .night-mode .onigimon-category-chip[data-category="treats"].is-selected,
        .nightMode .onigimon-category-chip[data-category="treats"].is-selected {{
            background: #4a1735;
        }}

        .night .onigimon-category-chip.is-selected,
        .night-mode .onigimon-category-chip.is-selected,
        .nightMode .onigimon-category-chip.is-selected {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
            background: var(--onigimon-item-bg-dark, color-mix(in srgb, var(--accent-color, #007aff) 22%, transparent));
        }}

        .onigimon-category-chip span {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-weight: 600;
        }}

        .onigimon-category-chip b {{
            margin-left: auto;
            font-size: 14px;
        }}

        .onigimon-category-panels {{
            display: grid;
            gap: 8px;
        }}

        .onigimon-category-panel {{
            display: none;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 8px;
            padding: 4px 0;
        }}

        .onigimon-category-panel.is-open {{
            display: grid;
        }}

        .onigimon-inventory-choice {{
            min-width: 0;
            display: grid;
            justify-items: center;
            gap: 4px;
            border: 1px solid var(--border, #e0e0e0);
            border-radius: 9px;
            padding: 8px 6px;
            background: var(--canvas-inset, #f6f6f6);
            color: inherit;
            cursor: pointer;
        }}

        .onigimon-inventory-choice:disabled {{
            opacity: 0.45;
            cursor: default;
        }}

        .onigimon-inventory-choice:not(:disabled):hover {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
        }}

        .onigimon-inventory-choice.is-selected {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
            background: var(--onigimon-item-bg-light, color-mix(in srgb, var(--accent-color, #007aff) 16%, var(--canvas-inset, #f6f6f6)));
        }}

        .onigimon-inventory-choice[data-item="poke_candies"]:hover {{
            border-color: #ff6fc8;
        }}

        .onigimon-inventory-choice[data-item="poke_candies"].is-selected {{
            border-color: #ff6fc8;
            background: #ffe0f3;
        }}

        .night .onigimon-inventory-choice[data-item="poke_candies"].is-selected,
        .night-mode .onigimon-inventory-choice[data-item="poke_candies"].is-selected,
        .nightMode .onigimon-inventory-choice[data-item="poke_candies"].is-selected {{
            background: #4a1735;
        }}

        .night .onigimon-inventory-choice.is-selected,
        .night-mode .onigimon-inventory-choice.is-selected,
        .nightMode .onigimon-inventory-choice.is-selected {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
            background: var(--onigimon-item-bg-dark, color-mix(in srgb, var(--accent-color, #007aff) 18%, var(--canvas-inset, #2c2c2c)));
        }}

        .onigimon-inventory-choice.is-passive {{
            cursor: default;
        }}

        .onigimon-inventory-choice span {{
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 12px;
            font-weight: 600;
        }}

        .onigimon-inventory-choice small {{
            color: var(--fg-subtle, #757575);
            font-size: 11px;
            line-height: 1.25;
            text-align: center;
        }}

        .onigimon-modal-inventory {{
            display: grid;
            gap: 8px;
        }}

        .onigimon-modal-inventory-title {{
            color: var(--fg-subtle, #757575);
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .onigimon-modal-inventory-title:not(:first-child) {{
            margin-top: 4px;
        }}

        .onigimon-modal-inventory-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
        }}

        .onigimon-empty-category {{
            color: var(--fg-subtle, #757575);
            font-size: 12px;
            padding: 6px 2px;
        }}

        .onigimon-inventory-chip {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            max-width: 170px;
            padding: 7px 9px;
            border-radius: 999px;
            background: color-mix(in srgb, var(--accent-color, #007aff) 9%, transparent);
            color: inherit;
            font-size: 12px;
        }}

        .onigimon-inventory-chip span {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .onigimon-inventory-chip b {{
            font-size: 13px;
        }}

        .onigimon-berry-chip {{
            display: grid;
            grid-template-columns: 22px minmax(0, 1fr) auto;
            align-items: center;
            max-width: 230px;
            border-radius: 12px;
        }}

        .onigimon-berry-chip small {{
            grid-column: 2 / 4;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--fg-subtle, #757575);
            font-size: 10px;
        }}

        /* Care Modal Display & Animations */
        .onigimon-care-display {{
            position: relative;
            height: 190px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: color-mix(in srgb, var(--accent-color, #007aff) 8%, var(--canvas-inset, #f6f6f6));
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border, #e0e0e0);
            isolation: isolate;
        }}

        .onigimon-care-display::before {{
            content: "";
            position: absolute;
            inset: -14px;
            background-image: var(--onigimon-scene-image, none);
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            filter: blur(var(--onigimon-scene-blur, 9px));
            transform: scale(1.06);
            opacity: var(--onigimon-scene-opacity, 0.9);
            z-index: 0;
            display: none;
        }}

        .onigimon-care-bg {{
            position: absolute;
            inset: -14px;
            transform: scale(1.06);
            opacity: var(--onigimon-scene-opacity, 0.9);
            z-index: 0;
            pointer-events: none;
        }}

        .onigimon-care-display::after {{
            content: "";
            position: absolute;
            inset: 0;
            background: color-mix(in srgb, var(--canvas-inset, #ffffff) 14%, transparent);
            z-index: 1;
        }}

        .night .onigimon-care-display {{
            background: color-mix(in srgb, var(--accent-color, #007aff) 12%, var(--canvas-inset, #2c2c2c));
            border-color: var(--border, #444);
        }}

        .onigimon-care-sprite {{
            width: 96px;
            height: 96px;
            display: grid;
            place-items: center;
            z-index: 2;
        }}

        .onigimon-care-sprite img {{
            width: 92px;
            height: 92px;
            object-fit: contain;
            image-rendering: pixelated;
        }}

        .onigimon-care-item-flow {{
            position: absolute;
            left: 25px;
            top: 25px;
            width: 32px;
            height: 32px;
            opacity: 0;
            z-index: 4;
            pointer-events: none;
        }}

        .onigimon-care-item-flow img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            image-rendering: pixelated;
        }}

        .onigimon-care-modal.has-reaction.is-open .onigimon-care-sprite {{
            animation: onigimon-bounce 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) 0.5s both;
        }}

        .onigimon-care-modal.has-reaction.is-open .onigimon-care-item-flow {{
            animation: onigimon-item-flow 1.0s cubic-bezier(0.25, 0.46, 0.45, 0.94) 0.2s both;
        }}

        @keyframes onigimon-bounce {{
            0% {{ transform: scale(1); }}
            30% {{ transform: scale(1.2) translateY(-12px); }}
            50% {{ transform: scale(0.9) translateY(0); }}
            70% {{ transform: scale(1.05) translateY(-4px); }}
            100% {{ transform: scale(1) translateY(0); }}
        }}

        @keyframes onigimon-item-flow {{
            0% {{
                opacity: 0;
                transform: translate(0, 0) scale(0.6) rotate(0deg);
            }}
            20% {{
                opacity: 1;
                transform: translate(15px, -15px) scale(1.2) rotate(-20deg);
            }}
            80% {{
                opacity: 1;
                transform: translate(110px, 20px) scale(0.9) rotate(180deg);
            }}
            100% {{
                opacity: 0;
                transform: translate(125px, 25px) scale(0.1) rotate(220deg);
            }}
        }}

                
                /* Override modal styles for full page */
                .onigimon-care-modal {{
                    position: static !important;
                    background: transparent !important;
                    backdrop-filter: none !important;
                    -webkit-backdrop-filter: none !important;
                    z-index: 1 !important;
                    opacity: 1 !important;
                    visibility: visible !important;
                    display: flex !important;
                    width: 100%;
                    height: 100%;
                    align-items: center;
                    justify-content: center;
                }}
                .onigimon-care-dialog {{
                    transform: none !important;
                    width: 100% !important;
                    max-width: 650px !important;
                    height: 100% !important;
                    max-height: 850px !important;
                    border-radius: 20px;
                    box-shadow: none !important;
                    margin: 20px;
                    background: transparent !important;
                }}
                .onigimon-modal-close {{
                    display: none !important;
                }}
            </style>
        </head>
        <body class="{mw.pm.night_mode() and 'night-mode' or ''}">
            {html_content}
            {notice_script}
        </body>
        </html>
        """
        
        self.web.stdHtml(full_html, context=self)

    def _generate_html(self, payload, companion):
        name = escape(manager.companion_display_name(companion))
        inventory = payload.get("inventory", {})
        plays_available = int(payload.get("playsAvailable") or 0)
        play_allowance = int(payload.get("playAllowance") or 0)
        gift_ready = bool(payload.get("dailyGiftReady"))
        last_action = payload.get("lastAction")
        
        modal_class = "is-open has-reaction" if last_action else "is-open"
        action_key = last_action if last_action in ITEMS else {"play": "poke_candies", "gift": "pokeballs"}.get(str(last_action), "berries")
        flow_item_html = _item_icon(action_key)
        
        modal_sprite = manager.modal_sprite_url(companion)
        sprite_img = f'<img src="{escape(modal_sprite)}" alt="{name}">' if modal_sprite else ""
        
        categories = (
            ("food", "Food", "berry_cheri", BERRY_KEYS + ("curry_ingredients",), "feed"),
            ("treats", "Treats", "poke_candies", ("poke_candies", "exp_candy"), "gift"),
            ("care", "Care", "mints", ("mints", "medicine"), "gift"),
            ("pokeballs", "Pokéballs", "pokeballs", ("pokeballs",), "none"),
        )
        
        category_bits = "".join(
            _category_button_html(category_id, label, icon_key, keys, inventory)
            for category_id, label, icon_key, keys, _action in categories
        )
        category_panel_bits = "".join(
            _category_panel_html(category_id, keys, action, inventory, companion)
            for category_id, _label, _icon_key, keys, action in categories
        )
        
        gift_disabled = "" if gift_ready else "disabled"
        gift_small = "daily ready" if gift_ready else "select gift"
        gift_onclick = "onigimonTriggerReaction('pokeballs'); pycmd('onigimon_daily_gift');" if gift_ready else ""

        return f"""
        <div id="onigimon-care-modal" class="onigimon-care-modal {modal_class}">
            <div class="onigimon-care-dialog">

                <div class="onigimon-care-display" {_onigimon_scene_style_attr()}>
                    {_onigimon_scene_background_layer("onigimon-care-bg")}
                    <div class="onigimon-care-item-flow">
                        {flow_item_html}
                    </div>
                    <div class="onigimon-care-sprite">
                        {sprite_img}
                    </div>
                </div>

                <div class="onigimon-care-actions">
                    <button id="onigimon-feed-action" disabled>
                        {_item_icon('berry_cheri')}
                        <span>Feed</span>
                        <small>select food</small>
                    </button>
                    <button {'disabled' if plays_available <= 0 else ''} onclick="onigimonTriggerReaction('poke_candies'); pycmd('onigimon_play');">
                        {_item_icon('poke_candies')}
                        <span>Play</span>
                        <small>{plays_available}/{play_allowance} plays</small>
                    </button>
                    <button id="onigimon-gift-action" {gift_disabled} onclick="{gift_onclick}">
                        {_item_icon('pokeballs')}
                        <span>Gift</span>
                        <small>{gift_small}</small>
                    </button>
                </div>
                <div class="onigimon-modal-inventory">
                    <div class="onigimon-modal-inventory-title">Items</div>
                    <div class="onigimon-category-grid">{category_bits}</div>
                    <div class="onigimon-category-panels">{category_panel_bits}</div>
                </div>
                <script>
                (function(){{
                    var modal = document.getElementById('onigimon-care-modal');
                    if (!modal) return;
                    window.onigimonShowCategory = function(category){{
                        modal.querySelectorAll('.onigimon-category-panel').forEach(function(panel){{
                            panel.classList.toggle('is-open', panel.dataset.category === category);
                        }});
                        modal.querySelectorAll('.onigimon-category-chip').forEach(function(chip){{
                            chip.classList.toggle('is-selected', chip.dataset.category === category);
                        }});
                    }};
                    window.onigimonSelectCareItem = function(key, action, label){{
                        modal.dataset.selectedItem = key;
                        modal.querySelectorAll('.onigimon-inventory-choice').forEach(function(choice){{
                            choice.classList.toggle('is-selected', choice.dataset.item === key);
                        }});
                        var feed = document.getElementById('onigimon-feed-action');
                        var gift = document.getElementById('onigimon-gift-action');
                        if (feed) {{
                            feed.disabled = action !== 'feed';
                            feed.querySelector('small').textContent = action === 'feed' ? label : 'select food';
                            feed.onclick = function(event) {{
                                event.stopPropagation();
                                if (action === 'feed') {{
                                    onigimonTriggerReaction(key);
                                    pycmd('onigimon_feed:' + key);
                                }}
                            }};
                        }}
                        if (gift) {{
                            gift.disabled = action !== 'gift';
                            gift.querySelector('small').textContent = action === 'gift' ? label : 'select gift';
                            gift.onclick = function(event) {{
                                event.stopPropagation();
                                if (action === 'gift') {{
                                    onigimonTriggerReaction(key);
                                    pycmd('onigimon_feed:' + key);
                                }}
                            }};
                        }}
                        if (action === 'feed') {{
                            onigimonTriggerReaction(key);
                            pycmd('onigimon_feed:' + key);
                        }}
                    }};
                    window.onigimonTriggerReaction = function(key){{
                        var flow = modal.querySelector('.onigimon-care-item-flow');
                        var source = modal.querySelector('[data-item="' + key + '"] .onigimon-item-icon') ||
                            modal.querySelector('.onigimon-category-chip[data-category="' + key + '"] .onigimon-item-icon');
                        if (flow && source) {{
                            flow.innerHTML = '';
                            flow.appendChild(source.cloneNode(true));
                        }}
                        modal.classList.remove('has-reaction');
                        void modal.offsetWidth;
                        modal.classList.add('has-reaction');
                    }};
                }})();
                </script>
            </div>
        </div>
        """
