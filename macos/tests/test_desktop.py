import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from papir import desktop
from papir.papir import save_client, resolve_target


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "client.json"
        self.env = patch.dict("os.environ", {"PAPIR_CLIENT": str(self.path)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_fresh_install_needs_login(self):
        self.assertEqual(desktop.dispatch({"action": "status"}), {"signed_in": False})

    def test_account_and_default_share_cli_without_exposing_secrets(self):
        save_client({"account_name": "Reader", "adp_token": "SECRET", "device_private_key": "PRIVATE"},
                    default_target="DEVICE", default_author="Writer")
        reply = desktop.dispatch({"action": "status"})
        self.assertEqual(reply["default_target"], "DEVICE")
        self.assertEqual(reply["default_author"], "Writer")
        self.assertNotIn("SECRET", json.dumps(reply))
        self.assertNotIn("PRIVATE", json.dumps(reply))
        reply = desktop.dispatch({"action": "defaults", "author": "New writer", "target": "library"})
        self.assertEqual(reply["default_target"], "library")
        self.assertEqual(reply["default_author"], "New writer")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_library_default_resolves_to_cloud_only(self):
        save_client({"account_name": "Reader"}, default_target="library")
        with patch.object(desktop.api, "get_owned_devices") as devices:
            self.assertEqual(resolve_target({}, None), [])
            devices.assert_not_called()

    def test_login_begin_and_finish_keep_matching_verifier(self):
        with patch.object(desktop, "new_verifier", return_value="MATCH"), patch.object(desktop.api, "get_signin_url", return_value="https://example.com/signin"):
            self.assertEqual(desktop.dispatch({"action": "login_begin"})["verifier"], "MATCH")
        with patch.object(desktop, "papirLogin", return_value={"account_name": "Reader"}) as login, patch.object(desktop, "set_default_author"):
            result = desktop.dispatch({"action": "login_finish", "redirect": "CODE", "verifier": "MATCH"})
            login.assert_called_once_with("CODE", "MATCH", device_name="Papir for Mac")
            self.assertTrue(result["signed_in"])

    def test_existing_login_is_not_replaced(self):
        self.path.write_text("{}")
        with patch.object(desktop, "papirLogin") as login:
            with self.assertRaises(ValueError):
                desktop.dispatch({"action": "login_finish", "redirect": "CODE", "verifier": "MATCH"})
            login.assert_not_called()

    def test_server_auth_errors_never_return_secrets(self):
        with patch.object(desktop, "dispatch", side_effect=ValueError("TOKEN SECRET")), patch("sys.stdin", io.StringIO('{"action":"login_finish"}')):
            output = io.StringIO()
            with contextlib.redirect_stdout(output): self.assertEqual(desktop.main(), 1)
        self.assertNotIn("SECRET", output.getvalue())
        self.assertFalse(json.loads(output.getvalue())["ok"])

    def test_devices_only_expose_names_and_serials(self):
        with patch.object(desktop, "papirDevices", return_value=[{"deviceName": "Scribe", "deviceSerialNumber": "DEVICE", "private": "SECRET"}]):
            reply = desktop.dispatch({"action": "devices"})
        self.assertEqual(reply["devices"], [{"serial": "DEVICE", "name": "Scribe"}])
        self.assertNotIn("SECRET", json.dumps(reply))


if __name__ == "__main__": unittest.main()
