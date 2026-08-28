"""WebUI page for caring for an Onigimon companion.

The manager in :mod:`onigimon` remains the source of truth.  This module only
serializes its state for the browser and routes deliberate browser actions back
to the manager.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests
from aqt import mw
from aqt.qt import QDialog, QVBoxLayout
from aqt.webview import AnkiWebView

from ..translations import tr
from . import redeem_net
from .onigimon import (
    FOOD_ITEM_KEYS,
    HAPPINESS_ITEM_KEYS,
    HYGIENE_ITEM_KEYS,
    ITEMS,
    MEDICINE_ITEM_KEYS,
    TRAINING_ITEM_KEYS,
    _addon_asset_url,
    _item_asset_url,
    _onigimon_scene_image_url,
    manager,
)
from .reward_redemption import REWARD_API_URL, apply_reward


STATUS_DEFS = {
    "health": {"color": "#08c46b", "icon": "system_files/system_icons/unavailable_for_users/heart.svg", "items": MEDICINE_ITEM_KEYS},
    "happiness": {"color": "#ffbd55", "icon": "system_files/system_icons/unavailable_for_users/happy.svg", "items": HAPPINESS_ITEM_KEYS},
    "hygiene": {"color": "#21b7d6", "icon": "system_files/system_icons/unavailable_for_users/soap.svg", "items": HYGIENE_ITEM_KEYS},
    "training": {"color": "#c866e5", "icon": "system_files/system_icons/unavailable_for_users/bolt.svg", "items": TRAINING_ITEM_KEYS},
    "hunger": {"color": "#f45bb3", "icon": "system_files/system_icons/unavailable_for_users/hamburger.svg", "items": FOOD_ITEM_KEYS},
}
STATUS_ORDER = tuple(STATUS_DEFS)


def _addon_package() -> str:
    return mw.addonManager.addonFromModule(__name__)


def _label(item_key: str) -> str:
    item = ITEMS.get(item_key, {})
    return tr(f"onigimon_item_{item_key}", str(item.get("label") or item_key))


def _short_message(message: str) -> str:
    """Keep existing manager messages, but remove the companion-name prefix."""
    companion = manager.active_companion()
    name = manager.companion_display_name(companion) if companion else ""
    message = str(message or "")
    if name and message.startswith(name):
        message = message[len(name):].lstrip(" 's,.")
    return message


def _idle_message(needs: Dict[str, Any]) -> str:
    if not needs:
        return tr("onigimon_live_healthy", "Ready to study together!")
    lowest = min(STATUS_ORDER, key=lambda key: int(needs.get(key, 100) or 100))
    value = int(needs.get(lowest, 100) or 100)
    if value >= 50:
        return tr("onigimon_live_healthy", "Ready to study together!")
    return {
        "health": tr("onigimon_live_hurt"),
        "hunger": tr("onigimon_live_hungry"),
        "happiness": tr("onigimon_live_sad"),
        "hygiene": tr("onigimon_live_dirty"),
        "training": tr("onigimon_live_tired"),
    }.get(lowest, tr("onigimon_live_okay"))


def _status_detail(key: str, companion: Dict[str, Any], needs: Dict[str, Any]) -> str:
    if key == "health":
        return str(int(companion.get("hp", 0) or 0))
    fields = {"happiness": "happiness", "hygiene": "cleanliness", "training": "training", "hunger": "hunger"}
    return str(int(companion.get(fields.get(key, key), needs.get(key, 0)) or 0))


def onigimon_payload() -> Dict[str, Any]:
    raw = manager.widget_payload(refresh_bridge=True)
    companion = raw.get("companion")
    if not companion:
        return {"companion": None}
    needs = raw.get("needs") or {}
    inventory = raw.get("inventory") or {}
    statuses = []
    for key in STATUS_ORDER:
        definition = STATUS_DEFS[key]
        statuses.append({
            "id": key,
            "label": tr(f"onigimon_status_{key}", key.title()),
            "value": max(0, min(100, int(needs.get(key, 0) or 0))),
            "detail": _status_detail(key, companion, needs),
            "color": definition["color"],
            "icon": _addon_asset_url(definition["icon"]),
            "empty": tr(f"onigimon_empty_{key}", tr("onigimon_empty_generic")),
            "items": [
                {"key": item_key, "label": _label(item_key), "count": int(inventory.get(item_key, 0) or 0), "icon": _item_asset_url(ITEMS.get(item_key, {}))}
                for item_key in definition["items"] if int(inventory.get(item_key, 0) or 0) > 0
            ],
        })
    market = []
    bought = set(raw.get("marketPurchased") or [])
    for offer in raw.get("marketItems") or []:
        item_key = str(offer.get("item_key") or "")
        currency = str(offer.get("currency") or "comet_shards")
        currency_key = "valuable_star_piece" if currency == "star_pieces" else "valuable_comet_shard"
        market.append({
            "slot": str(offer.get("slot") or ""), "itemKey": item_key, "label": _label(item_key),
            "icon": _item_asset_url(ITEMS.get(item_key, {})), "amount": int(offer.get("amount") or 1),
            "price": int(offer.get("price") or 0), "currency": currency,
            "currencyIcon": _item_asset_url(ITEMS.get(currency_key, {})), "purchased": str(offer.get("slot") or "") in bought,
        })
    gift = raw.get("lastGift") or None
    return {
        "companion": {**companion, "name": manager.companion_display_name(companion), "spriteUrls": manager.sprite_urls_for_companion(companion)},
        "needs": statuses, "market": market, "wallet": raw.get("wallet") or {},
        "marketGiftReady": bool(raw.get("marketGiftReady")),
        "message": _short_message(raw.get("lastMessage") or "") or _idle_message(needs),
        "gift": {"amount": int(gift.get("amount") or 1), "label": _label(str(gift.get("item_key") or "")), "icon": _item_asset_url(ITEMS.get(str(gift.get("item_key") or ""), {}))} if gift else None,
        "assets": {
            "background": _onigimon_scene_image_url(),
            "backgroundColor": str(manager.config().get("scene_background_color", "#6ea96a") or "#6ea96a"),
            "mart": _addon_asset_url("system_files/gamification_images/Mart.webp"),
            "backpack": _addon_asset_url("system_files/pokesprite/items/key-item-travel-trunk.png"),
            "heart": _addon_asset_url("system_files/system_icons/available_for_users/heart.svg"),
            "star": _addon_asset_url("system_files/system_icons/unavailable_for_users/star_outline.svg"),
            "comet": _item_asset_url(ITEMS.get("valuable_comet_shard", {})),
            "starPiece": _item_asset_url(ITEMS.get("valuable_star_piece", {})),
        },
        "labels": {"backpack": tr("onigimon_backpack"), "market": tr("onigimon_daily_market"), "dailyGift": tr("onigimon_daily_gift"), "giftOpened": tr("onigimon_gift_opened"), "redeem": tr("redeem_action"), "redeemTitle": tr("redeem_onigimon_title"), "redeemHint": tr("redeem_onigimon_hint"), "empty": tr("onigimon_empty_generic"), "level": tr("onigimon_level"), "idle": tr("onigimon_idle_item"), "noCompanion": tr("onigimon_no_companion"), "close": tr("close"), "rewardsEyebrow": tr("onigimon_rewards_eyebrow"), "dailyGiftEyebrow": tr("onigimon_daily_gift"), "giftReceived": tr("onigimon_gift_received"), "okay": tr("okay"), "companion": tr("onigimon_companion_title")},
    }


class OnigimonWebDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("onigimon_care_window_title"))
        self.resize(980, 720)
        self.setMinimumSize(720, 540)
        self.web = AnkiWebView(self)
        self.web.set_bridge_command(self._on_bridge, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self._render()

    def closeEvent(self, event) -> None:
        self._refresh_deck_browser()
        super().closeEvent(event)

    def _render(self) -> None:
        root = os.path.dirname(os.path.dirname(__file__))
        html_path = os.path.join(root, "web", "gamification", "onigimon", "onigimon.html")
        try:
            with open(html_path, encoding="utf-8") as handle:
                body = handle.read()
        except OSError:
            body = "<main><h1>Onigimon page assets are missing.</h1></main>"
        payload = json.dumps(onigimon_payload(), ensure_ascii=False).replace("</", "<\\/")
        package = _addon_package()
        self.web.stdHtml(body, css=[f"/_addons/{package}/web/gamification/onigimon/onigimon.css"], js=[f"/_addons/{package}/web/gamification/onigimon/onigimon.js"], head=f"<script>window.ONIGIRI_ONIGIMON_DATA={payload};</script>", context=self)

    def _push(self, notice: Dict[str, Any] | None = None) -> None:
        payload = json.dumps(onigimon_payload(), ensure_ascii=False).replace("</", "<\\/")
        try:
            self.web.eval(f"window.onOnigimonData && window.onOnigimonData({payload}, {json.dumps(notice or {}, ensure_ascii=False)});")
        except RuntimeError:
            pass

    def _after_change(self, message: str, kind: str = "success") -> None:
        self._refresh_deck_browser()
        self._push({"message": _short_message(message), "kind": kind})

    def _on_bridge(self, command: str) -> bool:
        if command.startswith("onigimon:use:"):
            self._after_change(manager.use_item(command.split(":", 2)[2]) or "", "success")
            return True
        if command.startswith("onigimon:market-buy:"):
            self._after_change(manager.purchase_market_item(command.split(":", 2)[2]) or "", "success")
            return True
        if command == "onigimon:market-gift":
            self._after_change(manager.claim_market_gift() or tr("onigimon_gift_opened"), "success")
            return True
        if command.startswith("onigimon:redeem:"):
            code = command.split(":", 2)[2].strip()
            if code:
                self._redeem(code)
            return True
        return False

    def _redeem(self, code: str) -> None:
        self._push({"message": tr("verifying", "Verifying…"), "kind": "pending"})
        def request():
            return redeem_net.post_redeem(REWARD_API_URL, {"code": code, "client": "onigiri", "profile": getattr(mw.pm, "name", "default"), "context": "onigimon", "request_id": redeem_net.request_id_for_code(code)})
        def done(future):
            try:
                response = future.result()
                data = response.json()
                redeem_net.clear_request_id(code)
                if data.get("result") != "success":
                    self._push({"message": data.get("message", "Invalid code"), "kind": "error"})
                    return
                self._after_change(apply_reward(data), "success")
            except requests.exceptions.ReadTimeout:
                self._push({"message": tr("redeem_timeout", "The server took too long. Enter the same code again to safely retry."), "kind": "error"})
            except Exception:
                self._push({"message": tr("redeem_failed", "Could not redeem this code."), "kind": "error"})
        mw.taskman.run_in_background(request, done)

    def _refresh_deck_browser(self) -> None:
        try:
            from .onigimon import render_widget_html
            web = getattr(mw, "web", None) or getattr(getattr(mw, "deckBrowser", None), "web", None)
            if web:
                web.eval(f"(function(){{var widget=document.querySelector('.onigimon-widget');if(widget)widget.outerHTML={json.dumps(render_widget_html())};}})();")
        except Exception as exc:
            print(f"Onigimon: Error refreshing deck browser: {exc}")


_dialog = None


def open_onigimon_care_dialog() -> None:
    global _dialog
    if _dialog is not None:
        _dialog.close()
    _dialog = OnigimonWebDialog(mw)
    _dialog.show()
