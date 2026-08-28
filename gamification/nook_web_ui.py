"""WebUI pages for Nook Level and Mr. Taiyaki Store.

The game rules remain in :mod:`nook_level`; this module only turns that state
into a WebView payload and routes browser actions back to the manager.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List

import requests
from aqt import mw
from aqt.qt import QDialog, QVBoxLayout
from aqt.webview import AnkiWebView

from ..translations import tr
from ..refresh import schedule_ui_refresh
from . import redeem_net
from .nook_level import manager


SHOP_API_URL = "https://script.google.com/macros/s/AKfycbyQl6b_cPnXJEJeEJryvsuRzZYclfIt_LWN1Mqqf63FjzCbKdPKV_uHIgYtHIXmAbnB/exec"


def _addon_package() -> str:
    return mw.addonManager.addonFromModule(__name__)


def _asset_url(path: str) -> str:
    return f"/_addons/{_addon_package()}/system_files/gamification_images/{path}"


def _item_groups() -> Dict[str, Dict[str, Any]]:
    store = manager.get_store_data()
    return {
        "restaurants": store.get("restaurants", {}),
        "evolutions": store.get("evolutions", {}),
        "shops": store.get("shops", {}),
    }


def _current_item(store: Dict[str, Any]) -> Dict[str, Any]:
    item_id = store.get("current_theme_id", "default")
    if item_id == "default":
        return {
            "id": "default",
            "name": tr("onigiri_stand_name", "Onigiri Stand"),
            "description": tr("onigiri_stand_desc", "Your cozy starting nook."),
            "theme": "#D49083",
            "image": "sushi/onigiri_stand.webp",
        }
    for items in _item_groups().values():
        if item_id in items:
            return {"id": item_id, **items[item_id]}
    return {"id": "default", "name": tr("onigiri_stand_name", "Onigiri Stand"), "image": "sushi/onigiri_stand.webp", "theme": "#D49083"}


def _rush_history() -> List[Dict[str, Any]]:
    try:
        game = manager._gamification_manager
        history = []
        for special in game.daily_specials:
            if special.completed:
                history.append({
                    "name": special.name,
                    "description": special.description,
                    "difficulty": special.difficulty,
                    "target": special.target_cards,
                    "date": (special.completed_date or "").split("T")[0],
                })
        return sorted(history, key=lambda item: item["date"], reverse=True)
    except Exception:
        return []


# Copy shown by the two webview pages. Both read it from the payload's
# `strings` map, so the pages follow the add-on language like the rest of the UI.
_NOOK_STRING_KEYS = (
    "restaurant_level_title", "home", "recipe_rush_title", "nook_tab_collection",
    "nook_store_short", "nook_your_study_space", "nook_level_uppercase",
    "nook_browse_store", "current_restaurant_header", "nook_change_your_nook",
    "nook_todays_rush", "nook_view_order", "nook_daily_study_order",
    "nook_closes_in", "nook_collect", "nook_ingredients", "nook_reward",
    "nook_rush_finish_hint", "nook_recipe_book", "nook_completed_rushes",
    "nook_your_unlocks", "restaurant_collection_header", "nook_open_store",
    "nook_navigation_aria", "nook_equipped_alt", "nook_no_items_yet",
    "nook_ingredients_hidden", "nook_history_empty", "restaurants_header",
    "evolutions_header", "shops_header", "cards", "xp_label",
    "nook_stage_prepare", "nook_stage_deliver", "nook_stage_completed",
    "rarity_common", "rarity_uncommon", "rarity_rare", "rarity_epic",
    "rarity_legendary",
)

_STORE_STRING_KEYS = (
    "taiyaki_store", "store_categories_aria", "store_coins_label",
    "store_collection_eyebrow", "store_taiyaki_coins", "store_power_up",
    "store_redeem_lead", "store_earn_title", "store_earn_desc",
    "store_support_title", "store_support_desc", "store_more_coins_title",
    "store_more_coins_desc", "store_buy_coins", "store_already_have_code",
    "redeem_code", "store_code_aria", "store_redeem_aria", "store_nook_details",
    "store_thank_you", "store_coins_added_desc", "store_contribution_note",
    "awesome", "close", "store_mascot_alt", "store_equip", "store_equipped",
    "store_no_items_section", "store_about_item", "store_desc_restaurants",
    "store_desc_evolutions", "store_desc_shops", "restaurants_header",
    "evolutions_header", "shops_header", "buy", "close_restaurant",
)


def _strings(keys) -> Dict[str, str]:
    return {key: tr(key) for key in keys}


def _localized_default_rush_name(name: Any) -> Any:
    """Translate the built-in starter Rush without changing custom titles."""
    return tr("default_sushi_rush", "Sushi Rush") if name == "Sushi Rush" else name


def nook_payload() -> Dict[str, Any]:
    """Build the complete read model for the redesigned Nook page."""
    progress = manager.get_progress_payload()
    store = manager.get_store_data()
    current = _current_item(store)
    rush = manager.get_daily_special_status()
    target = max(1, int(rush.get("target", 0) or 1))
    current_progress = max(0, int(rush.get("current_progress", 0) or 0))
    difficulty = str(rush.get("difficulty", "common") or "common").lower()
    history = _rush_history()
    counts = {key: 0 for key in ("common", "uncommon", "rare", "epic", "legendary")}
    for item in history:
        if item["difficulty"] in counts:
            counts[item["difficulty"]] += 1

    try:
        cutoff = int(mw.col.sched.day_cutoff) * 1000
    except Exception:
        cutoff = int(datetime.now().timestamp() * 1000) + 24 * 60 * 60 * 1000

    return {
        "progress": progress,
        "store": store,
        "current": current,
        "rush": {
            **rush,
            "target": target,
            "current": current_progress,
            "fraction": min(1, current_progress / target),
            "difficulty": difficulty,
            "difficultyLabel": tr(f"rarity_{difficulty}", difficulty.title()),
            "title": _localized_default_rush_name(rush.get("rush_name") or tr("recipe_rush_title", "Nook Rush")),
            "name": _localized_default_rush_name(rush.get("name") or tr("recipe_rush_title", "Nook Rush")),
            "description": rush.get("description") or tr("complete_your_reviews", "Complete your reviews to finish today's order."),
            "stage": rush.get("stage", "collect"),
            "endAt": cutoff,
        },
        "history": history,
        "recipeCounts": counts,
        "imageBase": _asset_url("nook_folder/") ,
        "coinImage": _asset_url("Tayaki_coin.webp"),
        "strings": _strings(_NOOK_STRING_KEYS),
    }


def store_payload() -> Dict[str, Any]:
    """Build the store's read model without refreshing Nook Rush data."""
    return {
        "store": manager.get_store_data(),
        "imageBase": _asset_url("nook_folder/"),
        "coinImage": _asset_url("Tayaki_coin.webp"),
        "strings": _strings(_STORE_STRING_KEYS),
    }


class _NookWebDialog(QDialog):
    """Shared native shell. All game pages themselves are HTML/CSS/JS."""

    def __init__(self, page: str, parent=None) -> None:
        super().__init__(parent)
        self.page = page
        self._refresh_on_close = False
        self.setWindowTitle(tr("restaurant_level", "Nook Level") if page == "nook" else tr("mr_taiyaki_store", "Mr. Taiyaki Store"))
        self.resize(1100, 760)
        self.setMinimumSize(720, 540)
        self.web = AnkiWebView(self)
        self.web.set_bridge_command(self._on_bridge, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self._render()

    def closeEvent(self, event) -> None:
        """Apply global theme changes only after the store is out of the way."""
        should_refresh = self._refresh_on_close
        self._refresh_on_close = False
        super().closeEvent(event)
        if should_refresh:
            schedule_ui_refresh()

    def _render(self) -> None:
        root = os.path.dirname(os.path.dirname(__file__))
        if self.page == "nook":
            html_path = os.path.join(root, "web", "gamification", "nook_level", "nook_level.html")
            css = [f"/_addons/{_addon_package()}/web/gamification/nook_level/nook_level.css"]
            js = [f"/_addons/{_addon_package()}/web/gamification/nook_level/nook_level.js"]
        else:
            html_path = os.path.join(root, "web", "gamification", "mr_taiyaki_store", "mr_taiyaki_store.html")
            css = [f"/_addons/{_addon_package()}/web/gamification/mr_taiyaki_store/mr_taiyaki_store.css"]
            js = [f"/_addons/{_addon_package()}/web/gamification/mr_taiyaki_store/mr_taiyaki_store.js"]
        try:
            with open(html_path, encoding="utf-8") as handle:
                body = handle.read()
        except OSError:
            body = "<main><h1>Onigiri page assets are missing.</h1></main>"
        payload = json.dumps(self._payload(), ensure_ascii=False).replace("</", "<\\/")
        self.web.stdHtml(body, css=css, js=js, head=f"<script>window.ONIGIRI_NOOK_DATA={payload};</script>", context=self)

    def _payload(self) -> Dict[str, Any]:
        return nook_payload() if self.page == "nook" else store_payload()

    def _push(self, notice: Dict[str, Any] | None = None) -> None:
        payload = json.dumps(self._payload(), ensure_ascii=False).replace("</", "<\\/")
        notice_js = json.dumps(notice or {}, ensure_ascii=False)
        try:
            self.web.eval(f"window.onNookData && window.onNookData({payload}, {notice_js});")
        except RuntimeError:
            # A redeem request can settle after the user has closed its page.
            pass

    def _on_bridge(self, command: str) -> bool:
        if command == "nook:open-store":
            open_taiyaki_store_dialog()
            return True
        if command == "nook:refresh":
            self._push()
            return True
        if command.startswith("store:buy:"):
            item_id = command.split(":", 2)[2]
            success, message = manager.buy_item(item_id)
            if success:
                self._refresh_on_close = True
            self._push({"kind": "success" if success else "error", "message": message})
            return True
        if command.startswith("store:equip:"):
            item_id = command.split(":", 2)[2]
            success, message = manager.equip_item(item_id)
            if success:
                self._refresh_on_close = True
            self._push({"kind": "success" if success else "error", "message": message})
            return True
        if command.startswith("store:redeem:"):
            code = command.split(":", 2)[2].strip()
            if code:
                self._redeem(code)
            return True
        return False

    def _redeem(self, code: str) -> None:
        """Redeem in Anki's task manager; the WebView never performs network I/O."""
        self._push({"kind": "pending", "message": tr("verifying", "Verifying…")})

        def request():
            # Keep this payload consistent with the other redemption screens.
            # In particular, the Apps Script uses the request id to replay a
            # successful result if its first response was lost in transit.
            return redeem_net.post_redeem(SHOP_API_URL, {
                "code": code,
                "client": "onigiri",
                "profile": getattr(mw.pm, "name", "default"),
                "context": "taiyaki",
                "request_id": redeem_net.request_id_for_code(code),
            })

        def done(future):
            try:
                response = future.result()
                data = response.json()
                if data.get("result") != "success":
                    redeem_net.clear_request_id(code)
                    self._push({"kind": "error", "message": data.get("message", "Invalid Code")})
                    return

                # The code server now returns ``reward_type`` and ``amount``.
                # The previous store-only handler read just ``coins``, so an
                # accepted code could be marked Used without adding anything.
                # Reuse the canonical handler, which supports both response
                # formats and writes the active profile's gamification file.
                from .reward_redemption import apply_reward

                message = apply_reward(data)
                redeem_net.clear_request_id(code)
                amount = max(0, int(data.get("amount", data.get("coins", 0)) or 0))
                # Do not reset Anki here: it can reload the WebView before its
                # success notice and wallet animation have been painted.
                self._push({"kind": "success", "message": message, "coinsAdded": amount})
            except Exception as exc:
                message = tr("redeem_failed", "Could not redeem this code.")
                if isinstance(exc, requests.exceptions.ReadTimeout):
                    message = tr("redeem_timeout", "The server took too long. Enter the same code again to safely retry.")
                self._push({"kind": "error", "message": message})

        mw.taskman.run_in_background(request, done)


_nook_dialog = None
_store_dialog = None


def open_nook_level_dialog() -> None:
    global _nook_dialog
    if _nook_dialog is not None:
        _nook_dialog.close()
    _nook_dialog = _NookWebDialog("nook", mw)
    _nook_dialog.show()


def open_taiyaki_store_dialog() -> None:
    global _store_dialog
    if _store_dialog is not None:
        _store_dialog.close()
    _store_dialog = _NookWebDialog("store", mw)
    _store_dialog.show()
