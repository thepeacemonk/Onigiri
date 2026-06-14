import json
from typing import Any, Iterable, Optional

from aqt import mw


_FALLBACK_JS = r"""
(function(){
  if (window.OnigiriNotifications) return;
  window.OnigiriNotifications = {
    show: function(data) {
      data = data || {};
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
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif',
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
      if (data.iconImage) {
        var img = document.createElement('img');
        img.src = data.iconImage;
        img.alt = '';
        img.style.cssText = 'width:100%;height:100%;object-fit:contain;';
        icon.appendChild(img);
      } else {
        icon.textContent = data.icon || 'On';
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
      var timer = setTimeout(hide, data.duration || 4200);
      card.addEventListener('mouseenter', function(){ clearTimeout(timer); });
      card.addEventListener('mouseleave', function(){ timer = setTimeout(hide, data.duration || 4200); });
      card.addEventListener('click', hide);
    }
  };
})();
"""


def _candidate_webviews(context: Any = None) -> Iterable[Any]:
    seen = set()

    def add(owner: Any):
        web = getattr(owner, "web", None)
        if web is not None and id(web) not in seen:
            seen.add(id(web))
            yield web

    if context is not None:
        yield from add(context)

    for owner in (
        getattr(mw, "deckBrowser", None),
        getattr(mw, "overview", None),
        getattr(mw, "reviewer", None),
    ):
        yield from add(owner)


def notification_script(
    message: str,
    *args: Any,
    title: str = "Onigiri",
    variant: str = "onigiri",
    icon: str = "On",
    icon_image: str = "",
    duration: int = 4200,
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
        "duration": duration,
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
    duration: int = 4200,
    hide_icon: bool = False,
    hide_title: bool = False,
    centered: bool = False,
) -> None:
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
    for web in _candidate_webviews(context):
        try:
            web.eval(script)
            return
        except Exception as exc:
            print(f"Onigiri: Could not show custom notification: {exc}")
    print(f"Onigiri notification: {title}: {message}")


def notify_info(message: str, *args: Any, context: Optional[Any] = None, title: str = "Onigiri", **kwargs: Any) -> None:
    notify(message, title=title, context=context)
