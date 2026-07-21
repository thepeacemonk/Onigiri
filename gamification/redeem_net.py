"""Shared HTTP helper for reward/shop code redemption.

The backend is a Google Apps Script web app. A cold start (plus the sheet
scan it does on every call) regularly takes far longer than the 10-12s
timeouts the callers used to pass, so users saw "Request timed out" even
though the script had already marked the code as Used - burning the code
without ever crediting the reward.

Three rules here:

* Be patient. Connect quickly, then wait a long time for the body.
* Retry automatically only when the request provably never reached the
  server (DNS / connection failures).
* Send a stable per-code ``request_id``. If the answer is lost in flight,
  the next attempt at the same code reuses that id and the script replays
  the stored reward instead of answering "Code already used". The id is
  only forgotten once a redemption has been settled locally.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, Optional, Tuple

import requests
from aqt import mw

# (connect, read). The read side is generous on purpose: an Apps Script
# cold start can sit silent for a minute before answering.
REDEEM_TIMEOUT: Tuple[float, float] = (10, 90)

CONNECT_ATTEMPTS = 3

_PENDING_FILE = "redemption_requests.json"


def _pending_path() -> str:
    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    user_files = os.path.join(addon_dir, "user_files")
    os.makedirs(user_files, exist_ok=True)
    return os.path.join(user_files, _PENDING_FILE)


def _normalize(code: str) -> str:
    return "".join(str(code or "").split()).replace("-", "").upper()


def _load_pending() -> Dict[str, str]:
    try:
        with open(_pending_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_pending(data: Dict[str, str]) -> None:
    try:
        with open(_pending_path(), "w", encoding="utf-8") as handle:
            json.dump(data, handle)
    except Exception:
        pass


def request_id_for_code(code: str) -> str:
    """Stable id for redeeming ``code``, kept until the attempt is settled."""
    key = _normalize(code)
    if not key:
        return uuid.uuid4().hex

    pending = _load_pending()
    request_id = pending.get(key)

    if not request_id:
        request_id = uuid.uuid4().hex
        pending[key] = request_id
        _save_pending(pending)

    return request_id


def clear_request_id(code: str) -> None:
    """Forget the id once the server has given a definitive answer."""
    key = _normalize(code)
    pending = _load_pending()

    if pending.pop(key, None) is not None:
        _save_pending(pending)


def post_redeem(
    url: str,
    payload: Dict[str, Any],
    timeout: Optional[Tuple[float, float]] = None,
) -> requests.Response:
    """POST a redemption payload, retrying only pre-send failures.

    Raises the usual ``requests`` exceptions so callers keep their existing
    error handling.
    """
    timeout = timeout or REDEEM_TIMEOUT
    last_error: Optional[Exception] = None

    for attempt in range(CONNECT_ATTEMPTS):
        try:
            return requests.post(url, json=payload, timeout=timeout)
        except requests.exceptions.ConnectTimeout as exc:
            # Never reached the server - safe to retry.
            last_error = exc
        except requests.exceptions.ConnectionError as exc:
            # ConnectionError also covers "connection reset while reading",
            # which is not safe to retry. Only retry when nothing was sent.
            if getattr(exc, "response", None) is not None:
                raise
            last_error = exc

    assert last_error is not None
    raise last_error
