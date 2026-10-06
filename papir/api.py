#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# Typed wrappers for the Amazon auth + STK APIs. Uses requests (duivesteyn style).
# Protocol is reverse-engineered from Amazon's Send to Kindle desktop app,
# following stkclient (Max Johnson, MIT) + cyrgim/stk. Unofficial.
#
# # bmd 2026

"""Amazon auth + Send-to-Kindle HTTP calls."""

import json
import urllib.parse

import requests

from papir import signer

CLIENT_ID = "658490dfb190e494030082836775981fa23be0c2425441860352ba0f55915b43002d"
DEVICE_TYPE = "A1K6D1WRW0MALS"
PID = "D21NN3GG"
SOFTWARE_VER = "253"
OS_VERSION = "MacOSX_10.14.6_x64"

TOKEN_HOST = "api.amazon.com"
FIRS_HOST = "firs-ta-g7g.amazon.com"
STK_HOST = "stkservice.amazon.com"

CLIENT_INFO = {
    "appName": "ShellExtension",
    "appVersion": "1.1.1.253",
    "os": OS_VERSION,
    "osArchitecture": "x64",
}

TIMEOUT = 30


class APIError(ValueError):
    """Amazon returned an HTTP error. .body holds the decoded server message."""

    def __init__(self, msg, body=None):
        self.body = body
        if body is not None:
            try:
                body = json.loads(body) if isinstance(body, (bytes, str)) else body
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                pass
            try:
                msg += f" {json.dumps(body)[:2000]}"
            except (TypeError, ValueError):
                msg += f" {str(body)[:2000]}"
        super().__init__(msg)


def get_signin_url(verifier):
    """Build the Amazon sign-in URL for a PKCE verifier. Open in a browser."""
    import base64
    import hashlib
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    q = {
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.ns.oa2": "http://www.amazon.com/ap/ext/oauth/2",
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.oa2.client_id": "device:" + CLIENT_ID,
        "openid.mode": "checkid_setup",
        "openid.oa2.scope": "device_auth_access",
        "openid.oa2.response_type": "code",
        "openid.oa2.code_challenge": challenge,
        "openid.oa2.code_challenge_method": "S256",
        "openid.return_to": "https://www.amazon.com/gp/sendtokindle",
        "openid.ns.pape": "http://specs.openid.net/extensions/pape/1.0",
        "openid.pape.max_auth_age": "0",
        "accountStatusPolicy": "P1",
        "openid.assoc_handle": "amzn_device_na",
        "pageId": "amzn_device_common_dark",
        "disableLoginPrepopulate": "1",
    }
    return "https://www.amazon.com/ap/signin?" + urllib.parse.urlencode(q)


def parse_authorization_code(redirect_url):
    """Pull openid.oa2.authorization_code out of the final redirect URL.

    Also accepts a bare code (e.g. ANprBJrehznaOHilnEIHemzX) for when the
    terminal truncates the paste — the code is the only part we need.
    """
    s = redirect_url.strip().strip("'\"")
    if s and "://" not in s and "?" not in s and "=" not in s and " " not in s and len(s) < 200:
        return s  # bare authorization code, no URL parsing needed
    u = urllib.parse.urlparse(redirect_url.strip())
    q = urllib.parse.parse_qs(u.query)
    try:
        return q["openid.oa2.authorization_code"][0]
    except (KeyError, IndexError):
        raise ValueError("no openid.oa2.authorization_code in redirect URL — sign-in did not complete")


def token_exchange(authorization_code, code_verifier):
    """Exchange authorization_code for an access_token. Returns the token string."""
    body = {
        "app_name": "Unknown",
        "client_domain": "DeviceLegacy",
        "client_id": CLIENT_ID,
        "code_algorithm": "SHA-256",
        "code_verifier": code_verifier,
        "requested_token_type": "access_token",
        "source_token": authorization_code,
        "source_token_type": "authorization_code",
    }
    try:
        r = requests.post(
            f"https://{TOKEN_HOST}/auth/token",
            json=body,
            headers={"Accept-Language": "en-US", "x-amzn-identity-auth-domain": TOKEN_HOST,
                      "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["access_token"]
    except requests.HTTPError as e:
        raise APIError(str(e), e.response.content if e.response is not None else None) from e


def register_device_with_token(access_token, serial, device_name):
    """Register a new device. Returns dict device_info (persist as client.json)."""
    import xml.etree.ElementTree as ET

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    xml_body = (
        "<?xml version='1.0' encoding='UTF-8'?><request><parameters>"
        + "".join(f"<{t}>{esc(v)}</{t}>" for t, v in [
            ("deviceType", DEVICE_TYPE),
            ("deviceSerialNumber", serial),
            ("pid", PID),
            ("authToken", access_token),
            ("authTokenType", "AccessToken"),
            ("softwareVersion", SOFTWARE_VER),
            ("os_version", OS_VERSION),
            ("device_model", device_name),
        ])
        + "</parameters></request>"
    )
    try:
        r = requests.post(
            f"https://{FIRS_HOST}/FirsProxy/registerDeviceWithToken",
            data=xml_body.encode(),
            headers={"Content-Type": "text/xml", "Accept-Language": "en-US,*", "User-Agent": "Mozilla/5.0"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        root = ET.fromstring(r.content)
        info = {el.tag: el.text for el in root}
        # keep only known fields, require the two secrets
        out = {
            "device_private_key": info.get("device_private_key"),
            "adp_token": info.get("adp_token"),
            "device_type": info.get("device_type", DEVICE_TYPE),
            "device_serial_number": serial,
            "device_name": device_name,
            "account_name": info.get("name", ""),
            "home_region": info.get("home_region", ""),
        }
        if not out["device_private_key"] or not out["adp_token"]:
            raise APIError("incomplete registration response", r.content[:2000])
        return out
    except requests.HTTPError as e:
        raise APIError(str(e), e.response.content if e.response is not None else None) from e


def _signed_post(path, device_info, body):
    """POST JSON to stkservice with ADP headers. Returns decoded dict."""
    data = json.dumps({"ClientInfo": CLIENT_INFO, **body}, indent=4)
    digest = signer.digest_header_for_request(
        device_info["device_private_key"], device_info["adp_token"], "POST", path, data)
    try:
        r = requests.post(
            f"https://{STK_HOST}{path}",
            data=data.encode(),
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Content-Type": "application/json",
                "X-ADP-Request-Digest": digest,
                "X-ADP-Authentication-Token": device_info["adp_token"],
                "Accept-Language": "en-US,*",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        raise APIError(str(e), e.response.content if e.response is not None else None) from e


def get_owned_devices(device_info):
    """Return list of {deviceName, deviceSerialNumber, deviceCapabilities}."""
    res = _signed_post("/GetListOfOwnedDevices", device_info, {})
    return res.get("ownedDevices", [])


def get_upload_url(device_info, file_size):
    """Return (upload_url, stk_token)."""
    res = _signed_post("/GetUploadUrl", device_info, {"fileSize": file_size})
    return res["uploadUrl"], res["stkToken"]


class _ProgressReader:
    """File-like wrapper reporting bytes read. Lets requests stream with Content-Length."""

    def __init__(self, fp, total, on_progress):
        self._fp = fp
        self._total = total
        self._sent = 0
        self._cb = on_progress

    def __len__(self):
        return self._total

    def read(self, n=-1):
        chunk = self._fp.read(n)
        if chunk:
            self._sent += len(chunk)
            try:
                self._cb(self._sent, self._total)
            except Exception:  # noqa: BLE001 — progress must never break the upload
                pass
        return chunk


def upload_file(url, file_size, fp, on_progress=None):
    """Stream fp to the presigned S3 URL via PUT. Raises APIError on non-200."""
    body = _ProgressReader(fp, file_size, on_progress) if on_progress else fp
    try:
        r = requests.put(
            url,
            data=body,
            headers={
                "Content-Length": str(file_size),
                "Accept-Language": "en-US,*",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=120,
        )
        if r.status_code != 200:
            raise APIError(f"upload HTTP {r.status_code} {r.reason}", r.content[:2000])
    except requests.RequestException as e:
        raise APIError(str(e)) from e


def build_send_body(stk_token, targets, author, title, fmt, archive=True, force_convert=False):
    """Build the /SendToKindle JSON body mirroring the official desktop app.

    Keys observed in the app binary: archive, targetDevices, title/author/
    inputFormat/crc32 under DocumentMetadata, forceConvert, stkToken.
    Deliberately NOT sent: outputFormat/deliveryMechanism — the app never
    sends them, and outputFormat=MOBI makes the backend convert PDFs.
    forceConvert=False keeps the native PDF (the app's unchecked checkbox).
    """
    return {
        "DocumentMetadata": {"author": author, "crc32": 0, "inputFormat": fmt, "title": title},
        "archive": archive,
        "forceConvert": force_convert,
        "stkToken": stk_token,
        "targetDevices": targets,
    }


def send_to_kindle(device_info, stk_token, targets, author, title, fmt, archive=True, force_convert=False):
    """Final delivery call. Returns sku string."""
    body = build_send_body(stk_token, targets, author, title, fmt, archive, force_convert)
    res = _signed_post("/SendToKindle", device_info, body)
    return res.get("sku", "")


def logout(device_info):
    """Disown the device server-side. Best-effort; always delete local creds after."""
    path = "/FirsProxy/disownFiona?contentDeleted=false"
    digest = signer.digest_header_for_request(
        device_info["device_private_key"], device_info["adp_token"], "GET", path, "")
    try:
        requests.get(
            f"https://{FIRS_HOST}{path}",
            headers={
                "X-ADP-Request-Digest": digest,
                "X-ADP-Authentication-Token": device_info["adp_token"],
                "Accept-Language": "en-US,*",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        pass
