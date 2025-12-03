import json
import random
from typing import List, Optional

from aqt import gui_hooks, mw

from .. import config


class MochiMessenger:
    def __init__(self) -> None:
        self._reviews_since_last: int = 0
        self._last_message: Optional[str] = None

    @staticmethod
    def _mochi_config() -> dict:
        conf = config.get_config()
        mochi_conf = conf.get("mochi_messages", {})
        if not isinstance(mochi_conf, dict):
            mochi_conf = {}
        return mochi_conf

    def _is_enabled(self) -> bool:
        return bool(self._mochi_config().get("enabled", False))

    def _cards_interval(self) -> int:
        mochi_conf = self._mochi_config()
        value = int(mochi_conf.get("cards_interval", 15) or 1)
        return max(1, value)

    def _messages(self) -> List[str]:
        mochi_conf = self._mochi_config()
        messages = mochi_conf.get("messages") or []
        if not isinstance(messages, list):
            messages = [str(messages)]
        messages = [str(item).strip() for item in messages if str(item).strip()]
        if messages:
            return messages
        default_messages = config.DEFAULTS.get("mochi_messages", {}).get("messages", [])
        return [str(item).strip() for item in default_messages if str(item).strip()]

    def _dispatch_notification(self, message: str) -> None:
        payload = json.dumps({
            "id": "mochi_message",
            "name": "Mochi says…",
            "description": message,
            "icon": "🍡",
        }, ensure_ascii=False)

        state = getattr(mw, "state", None)
        reviewer = getattr(mw, "reviewer", None)
        overview = getattr(mw, "overview", None)
        deck_browser = getattr(mw, "deckBrowser", None)

        webviews = []
        if state == "review" and reviewer and getattr(reviewer, "web", None):
            webviews.append(reviewer.web)
        elif state == "overview" and overview and getattr(overview, "web", None):
            webviews.append(overview.web)
        elif state == "deckBrowser" and deck_browser and getattr(deck_browser, "web", None):
            webviews.append(deck_browser.web)

        for web in [reviewer and getattr(reviewer, "web", None),
                    overview and getattr(overview, "web", None),
                    deck_browser and getattr(deck_browser, "web", None)]:
            if web and web not in webviews:
                webviews.append(web)

        script = (
            "if (window.OnigiriNotifications) {"
            f"window.OnigiriNotifications.show({payload});"
            "}"
        )

        for web in webviews:
            if not web:
                continue
            try:
                web.eval(script)
                break
            except Exception:
                continue

    def _select_message(self) -> Optional[str]:
        messages = self._messages()
        if not messages:
            return None
        candidates = messages.copy()
        if self._last_message and len(candidates) > 1 and self._last_message in candidates:
            candidates.remove(self._last_message)
        message = random.choice(candidates)
        self._last_message = message
        return message

    def _reset(self) -> None:
        self._reviews_since_last = 0
        self._last_message = None

    def on_reviewer_did_answer(self, *args, **kwargs) -> None:
        if not self._is_enabled():
            self._reset()
            return

        interval = self._cards_interval()
        self._reviews_since_last += 1
        if self._reviews_since_last < interval:
            return

        self._reviews_since_last = 0
        message = self._select_message()
        if message:
            self._dispatch_notification(message)

    def on_state_change(self, new_state: str, _old_state: str) -> None:
        if new_state != "review":
            self._reset()


messenger = MochiMessenger()


def register_hooks() -> None:
    gui_hooks.reviewer_did_answer_card.append(messenger.on_reviewer_did_answer)
    gui_hooks.state_did_change.append(messenger.on_state_change)


def unregister_hooks() -> None:
    try:
        gui_hooks.reviewer_did_answer_card.remove(messenger.on_reviewer_did_answer)
    except ValueError:
        pass
    try:
        gui_hooks.state_did_change.remove(messenger.on_state_change)
    except ValueError:
        pass


register_hooks()
