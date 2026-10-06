# 02 — Protocol (what the old app does)

Derived from static analysis of the installed app
(`/Applications/Send to Kindle/Send to Kindle.app/Contents/MacOS/SendToKindle`)
plus `stkclient==0.1.1` source (`api.py`, `signer.py`, `model.py`). No MITM needed —
traffic is HTTPS + RSA-signed; strings match the RE clients exactly.

`Papir` re-implements this protocol cleanly — no Amazon code, no keychain scraping.

## Hosts

| Host | Use |
|---|---|
| `www.amazon.com` | OAuth sign-in (`/ap/signin?`), `openid.return_to=https://www.amazon.com/gp/sendtokindle` |
| `api.amazon.com` | `POST /auth/token` — exchange `authorization_code` → `access_token` |
| `firs-ta-g7g.amazon.com` | `POST /FirsProxy/registerDeviceWithToken` (XML) → `adp_token` + RSA private key; `GET /FirsProxy/disownFiona` (logout) |
| `stkservice.amazon.com` | `POST /GetUploadUrl`, `POST /SendToKindle`, `POST /GetListOfOwnedDevices` (JSON, signed) |
| S3 presigned `uploadUrl` | `PUT` raw file bytes, `Content-Length` only |

Old binary also references `stkservice-preprod`, `kd.amazon.com`, `todo-ta-g7g`,
`updates.amazon.com` — ignore for v1.

## Auth (once per machine)

1. PKCE OAuth: `verifier = base64url(rand(32))`, `challenge = base64url(sha256(verifier))`.
   Sign-in URL params: `openid.oa2.client_id=device:658490df...`, `scope=device_auth_access`,
   `response_type=code`, `code_challenge=S256`. Always `amazon.com` even for AU/EU accounts.
2. User signs in → copies final redirect URL → parse `openid.oa2.authorization_code`.
3. `POST https://api.amazon.com/auth/token`:
   `{"app_name":"Unknown","client_domain":"DeviceLegacy","client_id":"65849...","code_algorithm":"SHA-256","code_verifier":...,"requested_token_type":"access_token","source_token":...,"source_token_type":"authorization_code"}`
   → `{"access_token": "..."}`.
4. `POST https://firs-ta-g7g.amazon.com/FirsProxy/registerDeviceWithToken` (XML `deviceType=A1K6D1WRW0MALS`, serial, pid `D21NN3GG`, authToken, `softwareVersion=253`, ...).
   → XML with `device_private_key`, `adp_token`, `name`, `home_region` (`NA`/`EU`).
   Persist as `client.json` (`chmod 600`).

Old app stores equivalents in login keychain (`SendToKindle`: `DeviceToken`, `SigningKey`, ...).
Do NOT scrape the keychain — do a fresh `papir login` registration so creds are separable/revocable.

## Send (per file)

1. `POST https://stkservice.amazon.com/GetUploadUrl`
   body `{"ClientInfo":{"appName":"ShellExtension","appVersion":"1.1.1.253","os":"MacOSX_10.14.6_x64","osArchitecture":"x64"},"fileSize": N}`
   → `{"stkToken","uploadUrl","expiryTime","statusCode":0}`.
2. `PUT <uploadUrl>` raw bytes, headers `Content-Length`, `Accept-Language`, `User-Agent: Mozilla/5.0`. Expect 200.
3. `POST https://stkservice.amazon.com/SendToKindle`
```json
{
  "ClientInfo": {...},
  "DocumentMetadata": {"author": "deCapital", "crc32": 0, "inputFormat": "PDF", "title": "Imperial Investment Case"},
  "archive": true,
  "forceConvert": false,
  "stkToken": "<step 1>",
  "targetDevices": ["DEVICE_SERIAL"]
}
```
→ `{"sku":"...","statusCode":0}`.

> Correction (2026-10-06, verified against the app binary's key table
> `archive/batchId/targetDevices/title/author/inputFormat/crc32/DocumentMetadata/forceConvert/sendTimeMillis/shouldExtractWebContent`):
> the official app sends **no** `outputFormat` / `deliveryMechanism`.
> `stkclient`'s hardcoded `"outputFormat": "MOBI"` makes the backend convert PDFs
> to Kindle format — Papir omits both fields and sends `forceConvert: false`
> (the unchecked "Convert PDF to Kindle format" box), so PDFs stay native.

`targetDevices: []` = library-only (uploads to Personal Documents without explicit device targets) — useful fallback when device list 503s.

## Request signing (the gotcha)

Every `stkservice` call needs:

```
X-ADP-Authentication-Token: <adp_token>
X-ADP-Request-Digest: <base64(RSA(priv, bare_sha256("METHOD\nPATH\nDATE\nBODY\nADPTOKEN"))) >:<DATE>
DATE = UTC YYYY-MM-DDTHH:MM:SSZ
```

Bare digest = PKCS#1 v1.5 over raw 32-byte SHA-256, **no DigestInfo prefix**
(Go: `rsa.SignPKCS1v15(rnd, key, crypto.Hash(0), sum[:])`; Python `rsa` lib: manual pad `01 FF...FF 00 || digest` then `pow()` — see `stkclient/signer.py:54-60`).
Using standard SHA256-with-DigestInfo → opaque 403.

## The Author tag

- The binary's send dialog has `authorLineEdit` / `titleLineEdit` (`&Author:`, `&Title:`,
  `Truncating author to`, `Truncating title length to`, `<Document Author>`, `<Document Title>`).
- Values go **only** into `DocumentMetadata.author` / `.title` in step 3.
- Email gateway has no such field — hence "email can't set author, app can". `Papir` exposes both as first-class CLI/GUI fields.
- `inputFormat` = source extension uppercased (`PDF/EPUB/DOCX/DOC/RTF/TXT/HTM/HTML/MOBI/AZW/JPEG/PNG/GIF/BMP`). `outputFormat` is always `MOBI` in `stkclient`; server converts. `archive:true` keeps a copy in the library. Papir omits `deliveryMechanism`.

## Local evidence (this Mac)

- `~/Library/Preferences/com.amazon.SendToKindle.plist`: device list (`a selected reader` selected, Pixel, iPad, ...), `ArchiveDocument=true`, `ConvertPdfToMobi=false`.
- `~/Library/Application Support/Amazon/SendToKindle/stk.db`: tables `Configuration` (empty), `Metrics`/`MetricsData` with `STKGetConfigure`, `STKGetListOfOwnedDevices`, `STKInit`, `S3UPLOAD`, `STKSendToKindle`, `DocumentSendSuccess` (+`DocumentSize`).
