"""Non-interactive JSON bridge for the bundled Mac app.

Authentication material travels on stdin, never in process arguments. Responses
expose account names and preferences, never persisted authentication secrets.
"""
import json
import sys
from papir import api
from papir.papir import (
    client_path, get_default_author, get_default_target, load_client,
    new_verifier, papirDevices, papirLogin, papirLogout,
    set_default_author, set_default_target,
)


def dispatch(request):
    action = request.get("action")
    if action == "runtime":
        import ssl
        import requests
        from pathlib import Path
        return {"frozen": bool(getattr(sys, "frozen", False)),
                "tls_available": bool(ssl.OPENSSL_VERSION),
                "ca_bundle_present": Path(requests.certs.where()).is_file()}
    if action == "status":
        try:
            info, _ = load_client()
        except FileNotFoundError:
            return {"signed_in": False}
        return {"signed_in": True, "account_name": info.get("account_name", ""),
                "default_author": get_default_author() or "",
                "default_target": get_default_target() or "all"}
    if action == "login_begin":
        verifier = new_verifier()
        return {"url": api.get_signin_url(verifier), "verifier": verifier}
    if action == "login_finish":
        if client_path().exists():
            raise ValueError("Already signed in. Sign out before connecting another account.")
        redirect = request.get("redirect", "").strip()
        verifier = request.get("verifier", "")
        if not redirect or not verifier:
            raise ValueError("Start sign-in and paste the final browser URL or code.")
        info = papirLogin(redirect, verifier, device_name="Papir for Mac")
        author = info.get("account_name") or ""
        if author:
            set_default_author(author)
        return {"signed_in": True, "account_name": author, "default_author": author,
                "default_target": "all"}
    if action == "devices":
        return {"default_target": get_default_target(), "devices": [
            {"serial": d["deviceSerialNumber"], "name": d.get("deviceName") or "Unnamed device"}
            for d in papirDevices()
        ]}
    if action == "defaults":
        if "author" in request:
            set_default_author(request["author"])
        if "target" in request:
            target = request["target"]
            set_default_target(None if target == "all" else target)
        return dispatch({"action": "status"})
    if action == "logout":
        papirLogout()
        return {"signed_in": False}
    raise ValueError("Unknown desktop action")


def main():
    action = None
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("Expected a JSON object")
        action = request.get("action")
        result = dispatch(request)
        print(json.dumps({"ok": True, **result}))
        return 0
    except Exception:
        # Do not return token exchange bodies, pasted URLs, or registration data.
        message = {
            "login_finish": "Sign-in failed. Start again with a fresh browser sign-in and paste its complete final URL or code.",
            "devices": "Could not load devices. Try refreshing in a moment.",
            "logout": "Could not sign out. Try again.",
            "defaults": "Could not save preferences. Check that you are signed in.",
        }.get(action, "Could not read account settings. Check your local Papir configuration.")
        print(json.dumps({"ok": False, "error": message}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
