"""Offline checks of the actual distributable, with isolated account state."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import urllib.parse
import zipfile

root = Path(__file__).resolve().parent
releases = root / "releases"
archives = sorted(releases.glob(f"Papir-*-macos-{platform.machine()}.zip"), key=lambda p: p.stat().st_mtime)
if not archives:
    raise SystemExit("Run bash macos/package.sh first")
archive = archives[-1]
expected = (releases / "SHA256SUMS.txt").read_text().split()[0]
assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
with zipfile.ZipFile(archive) as zipped:
    paths = zipped.namelist()
    assert all(p.startswith(("Papir.app/", "__MACOSX/")) for p in paths)
    assert not any(Path(p).name in {"client.json", ".env"} or p.endswith(".pdf") for p in paths)
    assert "Papir.app/Contents/Helpers/papir-engine" in paths
    assert "Papir.app/Contents/Resources/ThirdPartyLicenses.txt" in paths
with tempfile.TemporaryDirectory(prefix="Papir relocated ") as temporary:
    location = Path(temporary)
    subprocess.run(["/usr/bin/ditto", "-x", "-k", str(archive), str(location)], check=True)
    app = location / "Papir.app"
    engine = app / "Contents/Helpers/papir-engine"
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "DYLD"))}
    environment["PATH"] = "/usr/bin:/bin"
    environment["PAPIR_CLIENT"] = str(location / "isolated-account/client.json")
    def request(payload):
        response = subprocess.run([str(engine), "--desktop"], input=json.dumps(payload),
                                  capture_output=True, text=True, env=environment, cwd=location, timeout=30)
        assert response.returncode == 0, response.stderr
        return json.loads(response.stdout)
    runtime = request({"action": "runtime"})
    assert runtime == {"ok": True, "frozen": True, "tls_available": True, "ca_bundle_present": True}
    status = request({"action": "status"})
    assert status == {"ok": True, "signed_in": False}
    login = request({"action": "login_begin"})
    parsed = urllib.parse.urlparse(login["url"])
    assert parsed.scheme == "https" and parsed.netloc == "www.amazon.com"
    assert len(login["verifier"]) >= 43
    query = urllib.parse.parse_qs(parsed.query)
    assert query["openid.oa2.code_challenge_method"] == ["S256"]
    help_result = subprocess.run([str(engine), "--help"], capture_output=True, text=True,
                                 env=environment, cwd=location, timeout=30)
    assert help_result.returncode == 0 and "send" in help_result.stdout
    assert not (location / "isolated-account/client.json").exists()
    architecture = subprocess.check_output(["/usr/bin/lipo", "-archs", str(engine)], text=True).strip()
    assert architecture == platform.machine(), architecture
print(f"Verified {archive.name}: checksum, archive scope, relocated signature, bundled engine,")
print("TLS and bundled CA certificates, fresh account status, PKCE sign-in URL, CLI help,")
print("host architecture; no login or upload.")
