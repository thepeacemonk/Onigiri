import json
import random
from datetime import date
from typing import Any, Dict, List, Optional

from aqt import gui_hooks, mw

from .. import config

MANTRA_HISTORY_LIMIT = 30


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
        if bool(config.get_config().get("focusedGaming", False)):
            return False
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

    def _custom_icon_url(self) -> Optional[str]:
        """Web URL for the user's custom messenger image, if one is set and present."""
        mochi_conf = self._mochi_config()
        if mochi_conf.get("icon_choice") != "custom":
            return None
        rel_path = str(mochi_conf.get("custom_icon", "") or "").strip()
        if not rel_path:
            return None

        import os
        from .. import addon_path

        abs_path = rel_path if os.path.isabs(rel_path) else os.path.join(addon_path, rel_path)
        if not os.path.exists(abs_path):
            return None

        try:
            package = mw.addonManager.addonFromModule(__name__)
        except Exception:
            return None
        web_rel = os.path.relpath(abs_path, addon_path).replace(os.sep, "/")
        return f"/_addons/{package}/{web_rel}"

    def _font_style(self):
        """Resolve the configured message font to a (family, @font-face css) pair.

        Returns (None, "") for the system default or when the font can't be
        resolved, so the notification simply keeps its built-in font stack."""
        mochi_conf = self._mochi_config()
        font_key = str(mochi_conf.get("font", "system") or "system").strip()
        if not font_key or font_key == "system":
            return None, ""

        import os
        from .. import addon_path
        from ..fonts import get_all_fonts

        info = get_all_fonts(addon_path).get(font_key)
        if not info:
            return None, ""
        family = str(info.get("family", "") or "").strip()
        if not family:
            return None, ""

        font_file = info.get("file")
        if not font_file:
            return family, ""

        try:
            package = mw.addonManager.addonFromModule(__name__)
        except Exception:
            return None, ""
        if info.get("user"):
            url = f"/_addons/{package}/user_files/fonts/{font_file}"
        else:
            url = f"/_addons/{package}/system_files/fonts/system_fonts/{font_file}"
        css = f"@font-face {{ font-family: '{family}'; src: url('{url}'); }}"
        return family, css

    def _dispatch_notification(self, message: str) -> None:
        mochi_conf = self._mochi_config()
        custom_title = str(mochi_conf.get("title_name", "") or "").strip()
        data = {
            "id": "mochi_message",
            "name": custom_title or "Mochi says…",
            "description": message,
            "icon": "🍡",
        }
        if mochi_conf.get("hide_title", False):
            data["hideTitle"] = True
        custom_icon = self._custom_icon_url()
        if custom_icon:
            data["iconImage"] = custom_icon

        text_color = str(mochi_conf.get("text_color", "") or "").strip()
        if text_color:
            data["textColorLight"] = text_color
            data["textColorDark"] = text_color

        family, font_face = self._font_style()
        if family:
            data["fontFamily"] = family

        payload = json.dumps(data, ensure_ascii=False)

        if getattr(mw, "state", None) != "review":
            return

        reviewer = getattr(mw, "reviewer", None)
        web = reviewer and getattr(reviewer, "web", None)
        if not web:
            return

        # Register the chosen @font-face in the reviewer webview before showing
        # the card, so the family name resolves. Only one mochi font is active at
        # a time, so a single reused <style> element is enough.
        font_face_script = ""
        if font_face:
            font_face_json = json.dumps(font_face)
            font_face_script = (
                "(function(){var id='onigiri-mochi-font';"
                "var s=document.getElementById(id);"
                "if(!s){s=document.createElement('style');s.id=id;"
                "(document.head||document.documentElement).appendChild(s);}"
                f"if(s.textContent!=={font_face_json}){{s.textContent={font_face_json};}}"
                "})();"
            )

        script = (
            font_face_script
            + "if (window.OnigiriNotifications) {"
            f"window.OnigiriNotifications.show({payload});"
            "}"
        )

        try:
            web.eval(script)
        except Exception:
            pass

    def _select_message(self) -> Optional[str]:
        messages = self._messages()
        if not messages:
            return None
        candidates = messages.copy()
        if self._last_message and len(candidates) > 1 and self._last_message in candidates:
            candidates.remove(self._last_message)
        message = random.choice(candidates)
        self._last_message = message
        self._record_history(message)
        return message

    def _record_history(self, message: str) -> None:
        conf = config.get_config()
        mochi_conf = conf.setdefault("mochi_messages", {})
        if not isinstance(mochi_conf, dict):
            mochi_conf = {}
            conf["mochi_messages"] = mochi_conf
        history = mochi_conf.get("history") or []
        if not isinstance(history, list):
            history = []
        today = date.today().isoformat()
        if not (history and history[0].get("text") == message and history[0].get("date") == today):
            history.insert(0, {"text": message, "date": today})
        mochi_conf["history"] = history[:MANTRA_HISTORY_LIMIT]
        config.write_config(conf)

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


def get_mantra_history() -> List[Dict[str, Any]]:
    """Newest-first list of {"text", "date"} entries for past Mochi Messages."""
    conf = config.get_config()
    mochi_conf = conf.get("mochi_messages", {})
    if not isinstance(mochi_conf, dict):
        return []
    history = mochi_conf.get("history") or []
    if not isinstance(history, list):
        return []
    return [item for item in history if isinstance(item, dict) and item.get("text")]


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
