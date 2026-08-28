import json
import os
from typing import Any, Iterable, Optional

from aqt import mw
from aqt.qt import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPixmap,
    QPushButton,
    QVBoxLayout,
    Qt,
)
from aqt.theme import theme_manager

try:
    from PyQt6.QtSvg import QSvgRenderer
except Exception:
    try:
        from PyQt5.QtSvg import QSvgRenderer
    except Exception:
        QSvgRenderer = None


_FALLBACK_JS = r"""
(function(){
  if (window.OnigiriNotifications) return;
  window.OnigiriNotifications = {
    show: function(data) {
      data = data || {};
      var displayDuration = function() {
        var configured = Number(window.onigiriNotificationDuration);
        if (isFinite(configured) && configured > 0) return Math.max(1000, Math.min(30000, configured));
        var payloadDuration = Number(data.duration);
        if (isFinite(payloadDuration) && payloadDuration > 0) return Math.max(1000, Math.min(30000, payloadDuration));
        return 4200;
      };
      var stack = document.getElementById('onigiri-notification-stack');
      if (!stack) {
        stack = document.createElement('div');
        stack.id = 'onigiri-notification-stack';
        stack.style.cssText = [
          'position:fixed',
          'top:10px',
          'left:50%',
          'transform:translateX(-50%)',
          'display:flex',
          'flex-direction:column',
          'gap:10px',
          'width:min(380px,calc(100vw - 32px))',
          'z-index:2147483647',
          'pointer-events:none'
        ].join(';');
        document.body.appendChild(stack);
      }
      var card = document.createElement('article');
      var hideIcon = !!data.hideIcon;
      var hideTitle = !!data.hideTitle;
      var centered = !!data.centered;
      card.style.cssText = [
        'display:grid',
        hideIcon ? 'grid-template-columns:1fr' : 'grid-template-columns:auto 1fr',
        'gap:12px',
        'align-items:center',
        'box-sizing:border-box',
        'width:100%',
        'padding:13px 15px',
        'border-radius:16px',
        'border:1px solid rgba(112,198,166,.35)',
        'background:rgba(255,255,255,.94)',
        'color:#243021',
        'box-shadow:0 18px 38px rgba(15,23,42,.24)',
        "font-family:'Poppins',-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif",
        'opacity:0',
        'transform:translateY(-10px) scale(.98)',
        'transition:opacity 180ms ease,transform 220ms cubic-bezier(.16,1,.3,1)',
        'pointer-events:auto'
      ].join(';');
      if (centered) card.style.textAlign = 'center';
      var icon = document.createElement('div');
      icon.style.cssText = [
        'width:38px',
        'height:38px',
        'display:grid',
        'place-items:center',
        'border-radius:12px',
        'background:rgba(112,198,166,.16)',
        'font-size:22px',
        'line-height:1'
      ].join(';');
      // Same default as web/notifications.js: no icon of the caller's own (or
      // the bare "On" placeholder) means the Onigiri logo, not two letters.
      var iconSrc = data.iconImage ||
        ((!data.icon || data.icon === 'On')
          ? '/_addons/1011095603/system_files/onigiri_mini_logo.svg' : '');
      if (iconSrc) {
        var img = document.createElement('img');
        img.src = iconSrc;
        img.alt = '';
        img.style.cssText = 'width:100%;height:100%;object-fit:contain;';
        icon.appendChild(img);
      } else {
        icon.textContent = data.icon;
      }
      var content = document.createElement('div');
      content.style.cssText = 'display:grid;gap:2px;min-width:0;';
      if (centered) content.style.justifyItems = 'center';
      var title = document.createElement('p');
      title.textContent = data.name || 'Onigiri';
      title.style.cssText = 'margin:0;font-size:15px;font-weight:700;line-height:1.25;';
      var desc = document.createElement('p');
      desc.textContent = data.description || '';
      desc.style.cssText = 'margin:0;font-size:' + (hideTitle ? '15px' : '13px') + ';font-weight:' + (hideTitle ? '700' : '400') + ';line-height:1.35;';
      if (!hideTitle) content.appendChild(title);
      if (desc.textContent) content.appendChild(desc);
      if (!hideIcon) card.appendChild(icon);
      card.appendChild(content);
      stack.appendChild(card);
      requestAnimationFrame(function(){ requestAnimationFrame(function(){
        card.style.opacity = '1';
        card.style.transform = 'translateY(0) scale(1)';
      });});
      var hide = function(){
        card.style.opacity = '0';
        card.style.transform = 'translateY(-10px) scale(.98)';
        setTimeout(function(){
          card.remove();
          if (!stack.children.length) stack.remove();
        }, 230);
      };
      var duration = displayDuration();
      var timer = setTimeout(hide, duration);
      card.addEventListener('mouseenter', function(){ clearTimeout(timer); });
      card.addEventListener('mouseleave', function(){ timer = setTimeout(hide, duration); });
      card.addEventListener('click', hide);
    }
  };
})();
"""


def _silent_mode() -> bool:
    """Silent mode: every game notification is suppressed while it is on."""
    try:
        from . import config

        return bool(config.get_config().get("onigiri_reviewer_silent_notifications", False))
    except Exception:
        return False


def _configured_duration(fallback: int = 4200) -> int:
    try:
        from . import config
        duration = int(config.get_config().get("onigiri_notification_duration_ms", fallback))
    except Exception:
        duration = fallback
    return max(1000, min(30000, duration))


def _candidate_webviews(context: Any = None, *, gamification: bool = False) -> Iterable[Any]:
    if not gamification or getattr(mw, "state", None) != "review":
        return

    seen = set()

    def is_reviewer_owner(owner: Any) -> bool:
        return type(owner).__name__ == "Reviewer"

    def add(owner: Any):
        if not is_reviewer_owner(owner):
            return
        web = getattr(owner, "web", None)
        if web is not None and id(web) not in seen:
            seen.add(id(web))
            yield web

    if context is not None:
        yield from add(context)

    yield from add(getattr(mw, "reviewer", None))


def _native_tooltip(message: str) -> None:
    try:
        from aqt.utils import tooltip
        tooltip(str(message or ""))
    except Exception:
        print(f"Onigiri notification: {message}")


def _info_dialog_palette() -> dict[str, str]:
    is_dark = bool(theme_manager.night_mode)
    defaults = {
        "panel": "#1b1c1f" if is_dark else "#ffffff",
        "panel_alt": "#24262b" if is_dark else "#f6f7f9",
        "border": "rgba(255,255,255,.12)" if is_dark else "rgba(17,24,39,.12)",
        "fg": "#f4f4f5" if is_dark else "#111827",
        "muted": "#c9ccd3" if is_dark else "#5b6472",
        "accent": "#70c6a6",
        "accent_soft": "rgba(112,198,166,.18)",
        "button_hover": "#2e3137" if is_dark else "#eef1f4",
    }
    try:
        from . import config

        mode_key = "dark" if is_dark else "light"
        colors = config.get_config().get("colors", {}).get(mode_key, {})
        if isinstance(colors, dict):
            defaults["panel"] = colors.get("--canvas-inset", defaults["panel"])
            defaults["panel_alt"] = colors.get("--highlight-bg", defaults["panel_alt"])
            defaults["border"] = colors.get("--border", defaults["border"])
            defaults["fg"] = colors.get("--fg", defaults["fg"])
            defaults["muted"] = colors.get("--fg-subtle", defaults["muted"])
            defaults["accent"] = colors.get("--accent-color", defaults["accent"])
    except Exception:
        pass
    return defaults


def _info_dialog_icon_pixmap(color: str, size: int = 24) -> QPixmap:
    icon_path = os.path.join(
        os.path.dirname(__file__),
        "system_files",
        "system_icons",
        "unavailable_for_users",
        "info-circle.svg",
    )
    if QSvgRenderer is None or not os.path.exists(icon_path):
        return QPixmap()

    try:
        with open(icon_path, "r", encoding="utf-8") as icon_file:
            svg_data = icon_file.read().replace("currentColor", color)
        renderer = QSvgRenderer(svg_data.encode("utf-8"))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter)
        painter.end()
        return pixmap
    except Exception:
        return QPixmap()


class OnigiriInfoDialog(QDialog):
    def __init__(self, message: str, title: str = "Onigiri", parent: Any = None):
        super().__init__(parent)
        self.setWindowTitle(title or "Onigiri")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setMinimumWidth(390)
        self.setMaximumWidth(520)

        palette = _info_dialog_palette()
        self.setStyleSheet(f"""
            QDialog {{
                background: transparent;
            }}
            QFrame#onigiriInfoPanel {{
                background-color: {palette["panel"]};
                border: 1px solid {palette["border"]};
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
                color: {palette["fg"]};
            }}
            QLabel#onigiriInfoTitle {{
                font-size: 13px;
                font-weight: 400;
                color: {palette["muted"]};
            }}
            QLabel#onigiriInfoMessage {{
                font-size: 18px;
                font-weight: 400;
                line-height: 1.3;
            }}
            QLabel#onigiriInfoIcon {{
                background-color: {palette["accent_soft"]};
                color: {palette["accent"]};
                border: 1px solid {palette["accent"]};
                border-radius: 20px;
                font-size: 22px;
                font-weight: 400;
            }}
            QPushButton#onigiriInfoOk {{
                background-color: {palette["panel_alt"]};
                color: {palette["fg"]};
                border: 1px solid {palette["border"]};
                border-radius: 14px;
                min-width: 88px;
                min-height: 34px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 400;
            }}
            QPushButton#onigiriInfoOk:hover {{
                background-color: {palette["button_hover"]};
                border-color: {palette["accent"]};
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        panel = QFrame()
        panel.setObjectName("onigiriInfoPanel")
        outer.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(18)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(16)

        icon = QLabel()
        icon.setObjectName("onigiriInfoIcon")
        icon.setFixedSize(42, 42)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_pixmap = _info_dialog_icon_pixmap(palette["accent"], 24)
        if icon_pixmap.isNull():
            icon.setText("i")
        else:
            icon.setPixmap(icon_pixmap)
        content.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        text_stack = QVBoxLayout()
        text_stack.setContentsMargins(0, 0, 0, 0)
        text_stack.setSpacing(6)

        title_label = QLabel(title or "Onigiri")
        title_label.setObjectName("onigiriInfoTitle")
        title_label.setWordWrap(True)
        text_stack.addWidget(title_label)

        message_label = QLabel(str(message or ""))
        message_label.setObjectName("onigiriInfoMessage")
        message_label.setWordWrap(True)
        text_stack.addWidget(message_label)

        content.addLayout(text_stack, 1)
        layout.addLayout(content)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addStretch()
        ok_button = QPushButton("OK")
        ok_button.setObjectName("onigiriInfoOk")
        ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        buttons.addWidget(ok_button)
        layout.addLayout(buttons)


def _native_show_info(message: str, title: str = "Onigiri") -> None:
    try:
        parent = mw if mw is not None else None
        dialog = OnigiriInfoDialog(str(message or ""), title=title, parent=parent)
        dialog.exec()
    except Exception:
        try:
            from aqt.utils import showInfo
            showInfo(str(message or ""), title=title)
        except Exception:
            _native_tooltip(message)


def notification_script(
    message: str,
    *args: Any,
    title: str = "Onigiri",
    variant: str = "onigiri",
    icon: str = "On",
    icon_image: str = "",
    duration: Optional[int] = None,
    hide_icon: bool = False,
    hide_title: bool = False,
    centered: bool = False,
) -> str:
    payload = {
        "name": title,
        "description": str(message or ""),
        "variant": variant,
        "icon": icon,
        "iconImage": icon_image,
        "duration": _configured_duration() if duration is None else duration,
        "hideIcon": hide_icon,
        "hideTitle": hide_title,
        "centered": centered,
    }
    return (
        _FALLBACK_JS
        + "\nwindow.OnigiriNotifications.show("
        + json.dumps(payload, ensure_ascii=False)
        + ");"
    )


def notify(
    message: str,
    *args: Any,
    title: str = "Onigiri",
    context: Any = None,
    variant: str = "onigiri",
    icon: str = "On",
    icon_image: str = "",
    duration: Optional[int] = None,
    hide_icon: bool = False,
    hide_title: bool = False,
    centered: bool = False,
    gamification: bool = False,
) -> None:
    if not gamification:
        _native_tooltip(message)
        return

    # Silent mode: the games keep playing, they just say nothing. Checked here
    # rather than at each call site because this is the single door every game
    # toast goes through (the reviewer webview enforces the same key on its own
    # side — see web/notifications.js).
    if _silent_mode():
        return

    script = notification_script(
        message,
        title=title,
        variant=variant,
        icon=icon,
        icon_image=icon_image,
        duration=duration,
        hide_icon=hide_icon,
        hide_title=hide_title,
        centered=centered,
    )
    for web in _candidate_webviews(context, gamification=gamification):
        try:
            web.eval(script)
            return
        except Exception as exc:
            print(f"Onigiri: Could not show custom notification: {exc}")


def notify_info(message: str, *args: Any, context: Optional[Any] = None, title: str = "Onigiri", **kwargs: Any) -> None:
    if kwargs.get("gamification"):
        notify(message, title=title, context=context, **kwargs)
        return
    _native_show_info(message, title=title)
