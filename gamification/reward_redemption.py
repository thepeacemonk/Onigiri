from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, Optional

import requests
from aqt import mw
from aqt.qt import *

from ..onigiri_notifications import notify_info as showInfo


REWARD_API_URL = "https://script.google.com/macros/s/AKfycbxTGeWG088ZNkCYeyR2EnDiAKmlaInNbqCw0VAU2vlUmUAc8PW2JVMywGIyFS-bDb8C/exec"
BUY_CODES_URL = "https://buymeacoffee.com/peacemonk/extras"


def _night_mode() -> bool:
    try:
        return bool(mw and mw.pm and mw.pm.night_mode())
    except Exception:
        return False


def _profile_name() -> str:
    try:
        return mw.pm.name or "default"
    except Exception:
        return "default"


def _addon_path() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _device_pixel_ratio(widget=None) -> float:
    candidates = []
    if widget is not None:
        try:
            candidates.append(widget.devicePixelRatioF())
        except Exception:
            pass
        try:
            screen = widget.screen()
            if screen is not None:
                candidates.append(screen.devicePixelRatio())
        except Exception:
            pass
    try:
        app = getattr(mw, "app", None)
        screen = app.primaryScreen() if app else None
        if screen is not None:
            candidates.append(screen.devicePixelRatio())
    except Exception:
        pass

    for value in candidates:
        try:
            ratio = float(value)
        except (TypeError, ValueError):
            continue
        if ratio > 0:
            return max(1.0, min(ratio, 4.0))
    return 1.0


def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="reward_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


class RewardCodeDialog(QDialog):
    def __init__(self, parent=None, context: str = "reward") -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Redeem Reward")
        self.setFixedWidth(430)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        if self.context == "hex":
            self._setup_hex_ui()
            return
        if self.context == "onigimon":
            self._setup_onigimon_ui()
            return

        dark = _night_mode()
        bg = "#101820" if dark else "#f7fbff"
        panel = "#182634" if dark else "#ffffff"
        text = "#f5fbff" if dark else "#18313f"
        muted = "#9fb4c2" if dark else "#607989"
        accent = "#28a6ff" if self.context == "hex" else "#ffbd24"
        accent_2 = "#36d6a1" if self.context == "hex" else "#f06aa8"

        title_text = "Redeem Hex Code" if self.context == "hex" else "Redeem Onigimon Code"
        hint_text = (
            "Paste a Hex Coins code from Hexagon Land."
            if self.context == "hex"
            else "Paste a Comet Shards, Star Pieces, or Onigimon item code."
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 22)
        layout.setSpacing(16)

        hero = QWidget()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(8)

        icon = QLabel("HX" if self.context == "hex" else "ON")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(48, 48)
        icon.setStyleSheet(f"""
            QLabel {{
                background: {accent};
                color: {"#05131f" if self.context == "hex" else "#3b2606"};
                border-radius: 14px;
                font-size: 15px;
                font-weight: 900;
            }}
        """)
        hero_layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel(title_text)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {text}; font-size: 23px; font-weight: 900;")
        hero_layout.addWidget(title)

        subtitle = QLabel(hint_text)
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {muted}; font-size: 13px; font-weight: 600;")
        hero_layout.addWidget(subtitle)
        hero.setStyleSheet(f"""
            QWidget {{
                background: {panel};
                border: 1px solid {"#2a4052" if dark else "#dbeaf2"};
                border-radius: 18px;
            }}
        """)
        layout.addWidget(hero)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Paste code here")
        self.code_input.setClearButtonEnabled(True)
        self.code_input.setFixedHeight(46)
        self.code_input.returnPressed.connect(self.accept)
        self.code_input.setStyleSheet(f"""
            QLineEdit {{
                background: {panel};
                color: {text};
                border: 2px solid {"#2a4052" if dark else "#cfe2ed"};
                border-radius: 12px;
                padding: 0 14px;
                font-size: 15px;
                font-weight: 700;
            }}
            QLineEdit:focus {{
                border-color: {accent};
            }}
        """)
        layout.addWidget(self.code_input)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        redeem_btn = QPushButton("Redeem")
        redeem_btn.clicked.connect(self.accept)
        for btn in (cancel_btn, redeem_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(42)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {muted};
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 800;
            }}
            QPushButton:hover {{ color: {text}; }}
        """)
        redeem_btn.setStyleSheet(f"""
            QPushButton {{
                background: {accent};
                color: {"#05131f" if self.context == "hex" else "#3b2606"};
                border: none;
                border-radius: 12px;
                font-size: 15px;
                font-weight: 900;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background: {accent_2};
            }}
        """)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(redeem_btn)
        layout.addLayout(buttons)

        self.setLayout(layout)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")

    def _setup_hex_ui(self) -> None:
        dark = _night_mode()
        bg = "#1b1f24" if dark else "#f4f6f8"
        panel = "#22272e" if dark else "#ffffff"
        border = "#33393f" if dark else "#e3e7ea"
        text = "#eef1f4" if dark else "#1c2530"
        muted = "#8b94a0" if dark else "#69727e"
        accent = "#1fb6ff"
        accent_bg = "rgba(31, 182, 255, 0.18)" if dark else "rgba(31, 182, 255, 0.1)"

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 22)
        layout.setSpacing(16)

        hero = QWidget()
        hero.setObjectName("hexHeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        coin = QLabel()
        coin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        coin.setFixedSize(40, 40)
        coin_icon_path = os.path.join(_addon_path(), "system_files", "gamification_images", "Hexagon_world.png")
        if os.path.exists(coin_icon_path):
            dpr = _device_pixel_ratio(self)
            target = max(1, round(26 * dpr))
            coin_pixmap = QPixmap(coin_icon_path).scaled(
                target,
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            coin_pixmap.setDevicePixelRatio(dpr)
            coin.setPixmap(coin_pixmap)
        else:
            coin.setText("HC")
        coin.setStyleSheet(f"""
            QLabel {{
                background: {accent_bg};
                color: {accent};
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
            }}
        """)
        top_row.addWidget(coin)

        title = QLabel("Redeem Hex Coins")
        title.setStyleSheet(f"color: {text}; font-size: 16px; font-weight: 600;")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(title, 1)
        hero_layout.addLayout(top_row)

        subtitle = QLabel("Enter a Hexagon Land code to add coins to your wallet.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {muted}; font-size: 13px; font-weight: 400;")
        hero_layout.addWidget(subtitle)

        self._add_support_row(hero_layout, muted, accent, border, accent_bg)

        hero.setStyleSheet(f"""
            QWidget#hexHeroCard {{
                background: {panel};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)
        layout.addWidget(hero)

        self._add_code_controls(layout, panel, text, muted, accent, "#ffffff", "#159be0", border=border)
        self.setLayout(layout)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")

    def _setup_onigimon_ui(self) -> None:
        dark = _night_mode()
        bg = "#211318" if dark else "#f4f6f8"
        panel = "#2b1a20" if dark else "#ffffff"
        border = "#3f2c33" if dark else "#e3e7ea"
        text = "#fbeef2" if dark else "#1c2530"
        muted = "#c8a3ad" if dark else "#69727e"
        accent = "#f06aa8"
        accent_bg = "rgba(240, 106, 168, 0.18)" if dark else "rgba(240, 106, 168, 0.12)"

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 22)
        layout.setSpacing(16)

        hero = QWidget()
        hero.setObjectName("onigimonHeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        mart = QLabel()
        mart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mart.setFixedSize(40, 40)
        mart_icon_path = os.path.join(_addon_path(), "system_files", "gamification_images", "Mart.png")
        if os.path.exists(mart_icon_path):
            dpr = _device_pixel_ratio(self)
            target = max(1, round(26 * dpr))
            mart_pixmap = QPixmap(mart_icon_path).scaled(
                target,
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            mart_pixmap.setDevicePixelRatio(dpr)
            mart.setPixmap(mart_pixmap)
        else:
            mart.setText("ON")
        mart.setStyleSheet(f"""
            QLabel {{
                background: {accent_bg};
                color: {accent};
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
            }}
        """)
        top_row.addWidget(mart)

        title = QLabel("Redeem Onigimon Code")
        title.setStyleSheet(f"color: {text}; font-size: 16px; font-weight: 600;")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(title, 1)
        hero_layout.addLayout(top_row)

        subtitle = QLabel("Enter a code to add Comet Shards, Star Pieces, or items.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {muted}; font-size: 13px; font-weight: 400;")
        hero_layout.addWidget(subtitle)

        self._add_support_row(hero_layout, muted, accent, border, accent_bg)

        hero.setStyleSheet(f"""
            QWidget#onigimonHeroCard {{
                background: {panel};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)
        layout.addWidget(hero)

        self._add_code_controls(layout, panel, text, muted, accent, "#ffffff", "#d44e8c", border=border)
        self.setLayout(layout)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")

    def _add_code_controls(
        self,
        layout: QVBoxLayout,
        panel: str,
        text: str,
        muted: str,
        accent: str,
        accent_text: str,
        hover: str,
        border: str = "rgba(127, 151, 164, 0.35)",
    ) -> None:
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Paste code here")
        self.code_input.setClearButtonEnabled(True)
        self.code_input.setFixedHeight(40)
        self.code_input.returnPressed.connect(self.accept)
        self.code_input.setStyleSheet(f"""
            QLineEdit {{
                background: {panel};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
                font-weight: 400;
            }}
            QLineEdit:focus {{
                border-color: {accent};
            }}
        """)
        layout.addWidget(self.code_input)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        redeem_btn = QPushButton("Redeem")
        redeem_btn.clicked.connect(self.accept)
        for btn in (cancel_btn, redeem_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {muted};
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
                padding: 0 12px;
            }}
            QPushButton:hover {{ color: {text}; }}
        """)
        redeem_btn.setStyleSheet(f"""
            QPushButton {{
                background: {accent};
                color: {accent_text};
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: {hover}; }}
        """)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(redeem_btn)
        layout.addLayout(buttons)

    def _add_support_row(
        self,
        layout: QVBoxLayout,
        muted: str,
        accent: str,
        border: str,
        hover_bg: str,
    ) -> None:
        support_text = QLabel("Support Onigiri to get special coin codes and unlock exclusive themes!")
        support_text.setWordWrap(True)
        support_text.setStyleSheet(f"color: {muted}; font-size: 12px; font-weight: 400;")
        layout.addWidget(support_text)

        buy_row = QHBoxLayout()
        buy_row.addStretch(1)
        buy_btn = QPushButton("Buy Coin Codes")
        buy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        buy_btn.setFixedHeight(32)
        buy_btn.setMinimumWidth(220)
        buy_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(BUY_CODES_URL)))
        buy_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {accent};
                border: 1px solid {border};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background: {hover_bg}; }}
        """)
        buy_row.addWidget(buy_btn)
        buy_row.addStretch(1)
        layout.addLayout(buy_row)

    def code(self) -> str:
        return self.code_input.text().strip()


def open_reward_redeem_dialog(parent=None, context: str = "reward") -> bool:
    dialog = RewardCodeDialog(parent, context)
    if not dialog.exec():
        return False
    code = dialog.code()
    if not code:
        return False
    return redeem_reward_code(code, parent=parent, context=context)


def redeem_reward_code(code: str, parent=None, context: str = "reward") -> bool:
    try:
        payload = {
            "code": code,
            "client": "onigiri",
            "profile": _profile_name(),
            "context": context,
        }
        response = requests.post(REWARD_API_URL, json=payload, timeout=12)
        data = response.json()
    except requests.exceptions.Timeout:
        showInfo("Request timed out. Please check your internet connection.")
        return False
    except requests.exceptions.ConnectionError:
        showInfo("Could not connect to the reward server.")
        return False
    except Exception as exc:
        showInfo(f"Could not redeem code: {exc}")
        return False

    if data.get("result") != "success":
        showInfo(f"Redemption failed:\n{data.get('message', 'Invalid Code')}")
        return False

    try:
        message = apply_reward(data)
    except Exception as exc:
        showInfo(f"Code was accepted, but the reward could not be applied locally:\n{exc}")
        return False

    showInfo(message)
    _refresh_visible_surfaces(parent)
    return True


def apply_reward(data: Dict[str, Any]) -> str:
    reward_type = str(data.get("reward_type") or "").strip().lower()
    if not reward_type and "coins" in data:
        reward_type = "taiyaki_coins"

    if reward_type == "taiyaki_coins":
        amount = int(data.get("amount", data.get("coins", 0)) or 0)
        _add_taiyaki_coins(amount)
        return f"Redeemed {amount} Taiyaki Coins."

    if reward_type == "hex_coins":
        amount = int(data.get("amount", data.get("coins", 0)) or 0)
        from . import hexagon_land

        state = hexagon_land.manager.load()
        state.hex_coins = int(state.hex_coins) + amount
        hexagon_land.manager.save(state)
        return f"Redeemed {amount} Hex Coins."

    if reward_type == "onigimon_coins":
        amount = int(data.get("amount", data.get("coins", 0)) or 0)
        currency = str(data.get("currency") or "comet_shards").strip().lower()
        from .onigimon import manager

        state = manager.load()
        if currency in ("star_piece", "star_pieces", "stars"):
            state.star_pieces = int(state.star_pieces) + amount
            label = "Star Pieces"
        else:
            state.comet_shards = int(state.comet_shards) + amount
            label = "Comet Shards"
        manager.save()
        return f"Redeemed {amount} {label}."

    if reward_type == "onigimon_item":
        item_key = str(data.get("item_key") or data.get("item") or "").strip()
        amount = int(data.get("amount", 1) or 1)
        if not item_key:
            raise ValueError("Missing Onigimon item key.")
        from .onigimon import ITEMS, manager

        if item_key not in ITEMS:
            raise ValueError(f"Unknown Onigimon item: {item_key}")
        state = manager.load()
        state.inventory[item_key] = int(state.inventory.get(item_key, 0) or 0) + amount
        manager.save()
        label = ITEMS.get(item_key, {}).get("label", item_key)
        return f"Redeemed {amount} {label}."

    raise ValueError(f"Unknown reward type: {reward_type or 'blank'}")


def _add_taiyaki_coins(amount: int) -> None:
    path = os.path.join(_addon_path(), "user_files", f"gamification_{_profile_name()}.json")
    data: Dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    restaurant = data.setdefault("restaurant_level", {})
    restaurant["taiyaki_coins"] = int(restaurant.get("taiyaki_coins", 0) or 0) + amount
    restaurant.pop("_security_token", None)
    _atomic_write_json(path, data)
    try:
        from .nook_level import manager

        manager.refresh_state()
    except Exception:
        pass


def _refresh_visible_surfaces(parent: Optional[QObject] = None) -> None:
    try:
        if parent and hasattr(parent, "push_payload"):
            parent.push_payload()
        elif parent and hasattr(parent, "render_page"):
            parent.render_page()
    except Exception:
        pass
    try:
        if mw and getattr(mw, "deckBrowser", None):
            mw.deckBrowser.refresh()
    except Exception:
        pass
