"""Bootstrap Ghost + Lemmy credentials for local Docker (must-have #8)."""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

STATE_PATH = Path("data/local_platforms.json")
GHOST_ADMIN_EMAIL = "admin@example.com"
GHOST_ADMIN_PASSWORD = "Kx9!mQ2vL7pR4wZ8nH3sT6yU1bN5cD0f"
GHOST_BLOG_TITLE = "Outpost Local Ghost"
LEMMY_USER = "lemmy_admin"
LEMMY_PASS = "outpost-lemmy-pass"


def _should_bootstrap() -> bool:
    settings = get_settings()
    if os.environ.get("SKIP_PLATFORM_BOOTSTRAP", "").lower() in ("1", "true", "yes"):
        return False
    # Only auto-bootstrap when compose points at real service hostnames.
    lemmy = settings.lemmy_base_url
    ghost = settings.ghost_url
    return "lemmy" in lemmy or "ghost" in ghost


def _load_state() -> dict[str, Any] | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _save_state(data: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _wait_url(client: httpx.Client, url: str, attempts: int = 90, sleep_s: float = 2.0) -> None:
    last_err: Exception | None = None
    for _ in range(attempts):
        try:
            r = client.get(url, timeout=5.0)
            if r.status_code < 500:
                return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(sleep_s)
    raise TimeoutError(f"Timed out waiting for {url}: {last_err}")


def _ghost_setup_payload() -> dict[str, Any]:
    # Ghost Admin API expects root key "setup" as an array (see Ghost 5 docs).
    return {
        "setup": [
            {
                "name": "Outpost Admin",
                "email": GHOST_ADMIN_EMAIL,
                "password": GHOST_ADMIN_PASSWORD,
                "blogTitle": GHOST_BLOG_TITLE,
            }
        ]
    }


def _response_json(response: httpx.Response) -> dict[str, Any]:
    if not response.text or not response.text.strip():
        return {}
    try:
        body = response.json()
        return body if isinstance(body, dict) else {}
    except json.JSONDecodeError:
        return {}


def _extract_ghost_token(response: httpx.Response) -> str | None:
    if response.status_code not in (200, 201):
        return None
    return (_response_json(response).get("authentication") or {}).get("access_token")


def _ghost_session_established(response: httpx.Response) -> bool:
    """Ghost 5.130+ may return 201 text/plain 'Created' and set ghost-admin-api-session cookie."""
    if response.status_code not in (200, 201):
        return False
    if _extract_ghost_token(response):
        return True
    if "ghost-admin-api-session" in (response.headers.get("set-cookie") or "").lower():
        return True
    if response.text.strip().lower() == "created":
        return True
    return False


def _mailpit_url() -> str:
    return os.environ.get("MAILPIT_URL", "http://mailpit:8025").rstrip("/")


def _mailpit_message_count(client: httpx.Client) -> int:
    try:
        r = client.get(f"{_mailpit_url()}/api/v1/messages", timeout=5.0)
        if r.is_success:
            return int(r.json().get("total") or 0)
    except Exception:  # noqa: BLE001
        return 0
    return 0


def _mailpit_latest_otp(client: httpx.Client, min_total: int) -> str:
    for _ in range(45):
        r = client.get(f"{_mailpit_url()}/api/v1/messages", timeout=5.0)
        r.raise_for_status()
        total = int(r.json().get("total") or 0)
        if total > min_total:
            messages = r.json().get("messages") or []
            if messages:
                msg_id = messages[0]["ID"]
                detail = client.get(f"{_mailpit_url()}/api/v1/message/{msg_id}", timeout=5.0)
                detail.raise_for_status()
                payload = detail.json()
                text = payload.get("Text") or payload.get("HTML") or payload.get("Snippet") or ""
                match = re.search(r"\b(\d{6})\b", text)
                if match:
                    return match.group(1)
        time.sleep(1)
    raise RuntimeError("Timed out waiting for Ghost sign-in code in Mailpit (http://localhost:8025)")


def _extract_2fa_challenge(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    if data.get("token"):
        return str(data["token"])
    auth = data.get("authentication") or {}
    if auth.get("token"):
        return str(auth["token"])
    for err in data.get("errors") or []:
        if err.get("token"):
            return str(err["token"])
    return None


def _ghost_login(client: httpx.Client, base: str) -> httpx.Response:
    return client.post(
        f"{base}/ghost/api/admin/session/",
        json={"username": GHOST_ADMIN_EMAIL, "password": GHOST_ADMIN_PASSWORD},
        timeout=30.0,
    )


def _ghost_login_with_optional_2fa(client: httpx.Client, base: str) -> bool:
    min_mail = _mailpit_message_count(client)
    login = _ghost_login(client, base)
    if _ghost_session_established(login):
        return True

    if login.status_code == 403 and "Needs2FAError" in login.text:
        challenge = _extract_2fa_challenge(_response_json(login))
        if not challenge:
            raise RuntimeError(f"Ghost 2FA required but no challenge token: {login.text[:300]}")
        otp = _mailpit_latest_otp(client, min_mail)
        verify = client.post(
            f"{base}/ghost/api/admin/session/verify/",
            json={"token": challenge, "otp": otp},
            timeout=30.0,
        )
        if _ghost_session_established(verify) or _extract_ghost_token(verify):
            return True
        raise RuntimeError(f"Ghost 2FA verify failed ({verify.status_code}): {verify.text[:300]}")

    return False


def _ensure_ghost_admin_session(client: httpx.Client, base: str) -> None:
    if _ghost_login_with_optional_2fa(client, base):
        return

    login = _ghost_login(client, base)
    if login.status_code not in (404, 401, 403):
        if login.status_code >= 500 and "email" in login.text.lower():
            raise RuntimeError(
                "Ghost login failed due to email/mail config. Recreate ghost with Mailpit: "
                "docker compose up -d mailpit ghost --force-recreate"
            )

    setup = client.post(
        f"{base}/ghost/api/admin/authentication/setup/",
        json=_ghost_setup_payload(),
        timeout=30.0,
    )
    if _ghost_session_established(setup) or _extract_ghost_token(setup):
        return

    if setup.status_code in (200, 201, 403, 422):
        if _ghost_login_with_optional_2fa(client, base):
            return

    raise RuntimeError(
        f"Ghost auth failed (login={login.status_code}, setup={setup.status_code}): "
        f"{login.text[:200]} | {setup.text[:200]}"
    )


def _ghost_admin_api_key(client: httpx.Client, base: str) -> str:
    headers = {"Content-Type": "application/json"}
    try:
        integrations = client.get(f"{base}/ghost/api/admin/integrations/", headers=headers, timeout=30.0)
        integrations.raise_for_status()
        for row in integrations.json().get("integrations") or []:
            if row.get("name") != "OutpostCert":
                continue
            for api_key in row.get("api_keys") or []:
                kid = api_key.get("id")
                secret = api_key.get("secret")
                if kid and secret:
                    return f"{kid}:{secret}"

        created = client.post(
            f"{base}/ghost/api/admin/integrations/",
            headers=headers,
            json={
                "integrations": [
                    {
                        "name": "OutpostCert",
                        "description": "Local certification integration",
                        "type": "custom",
                    }
                ]
            },
            timeout=30.0,
        )
        created.raise_for_status()
        integration = (created.json().get("integrations") or [{}])[0]
        for api_key in integration.get("api_keys") or []:
            kid = api_key.get("id")
            secret = api_key.get("secret")
            if kid and secret:
                return f"{kid}:{secret}"
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Ghost integration API key creation failed: {exc}") from exc


def _bootstrap_ghost(client: httpx.Client, base: str) -> str:
    base = base.rstrip("/")
    site_url = f"{base}/ghost/api/admin/site/"
    _wait_url(client, site_url)
    _ensure_ghost_admin_session(client, base)
    return _ghost_admin_api_key(client, base)


def _bootstrap_lemmy(client: httpx.Client, base: str) -> tuple[str, int]:
    base = base.rstrip("/")
    _wait_url(client, f"{base}/api/v3/site")
    login = client.post(
        f"{base}/api/v3/user/login",
        json={"username_or_email": LEMMY_USER, "password": LEMMY_PASS},
        timeout=30.0,
    )
    if login.status_code == 400:
        reg = client.post(
            f"{base}/api/v3/user/register",
            json={
                "username": LEMMY_USER,
                "password": LEMMY_PASS,
                "password_verify": LEMMY_PASS,
                "show_nsfw": False,
            },
            timeout=30.0,
        )
        reg.raise_for_status()
        login = client.post(
            f"{base}/api/v3/user/login",
            json={"username_or_email": LEMMY_USER, "password": LEMMY_PASS},
            timeout=30.0,
        )
    if not login.is_success:
        raise RuntimeError(f"Lemmy login failed ({login.status_code}): {login.text[:300]}")
    jwt = login.json().get("jwt")
    if not jwt:
        raise RuntimeError("Lemmy bootstrap: login returned no jwt")

    headers = {"Authorization": f"Bearer {jwt}"}
    communities = client.get(
        f"{base}/api/v3/community/list",
        params={"type_": "All", "limit": 50},
        headers=headers,
        timeout=30.0,
    )
    communities.raise_for_status()
    for cv in communities.json().get("communities") or []:
        community = cv.get("community") or {}
        if community.get("name") == "outpost_cert":
            return jwt, int(community["id"])

    created = client.post(
        f"{base}/api/v3/community",
        headers=headers,
        json={
            "name": "outpost_cert",
            "title": "Outpost certification",
            "description": "Local test community for connector certification",
            "nsfw": False,
        },
        timeout=30.0,
    )
    if not created.is_success:
        raise RuntimeError(f"Lemmy community create failed ({created.status_code}): {created.text[:300]}")
    community = (created.json().get("community_view") or {}).get("community") or {}
    cid = community.get("id")
    if not cid:
        raise RuntimeError(f"Lemmy bootstrap: community create failed: {created.text[:300]}")
    return jwt, int(cid)


def apply_platform_env(state: dict[str, Any]) -> None:
    if state.get("ghost_admin_api_key"):
        os.environ["GHOST_ADMIN_API_KEY"] = state["ghost_admin_api_key"]
    if state.get("lemmy_jwt"):
        os.environ["LEMMY_JWT"] = state["lemmy_jwt"]
    if state.get("lemmy_community_id"):
        os.environ["LEMMY_COMMUNITY_ID"] = str(state["lemmy_community_id"])
    get_settings.cache_clear()


def ensure_local_platforms_ready() -> None:
    if not _should_bootstrap():
        return

    settings = get_settings()
    existing = _load_state()
    if existing:
        apply_platform_env(existing)
        logger.info("Loaded local platform credentials from %s", STATE_PATH)
        return

    logger.info("Bootstrapping Ghost (%s) and Lemmy (%s)...", settings.ghost_url, settings.lemmy_base_url)
    with httpx.Client(follow_redirects=True) as client:
        ghost_key = _bootstrap_ghost(client, settings.ghost_url)
        lemmy_jwt, community_id = _bootstrap_lemmy(client, settings.lemmy_base_url)

    state = {
        "ghost_admin_api_key": ghost_key,
        "lemmy_jwt": lemmy_jwt,
        "lemmy_community_id": community_id,
    }
    _save_state(state)
    apply_platform_env(state)
    logger.info("Platform bootstrap complete (community_id=%s)", community_id)
