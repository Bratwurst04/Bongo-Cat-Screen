"""Real auth/storage/entry-point code with fake HTTP, sockets and credentials."""

import base64
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))
import main
import spotify_api as api_module
from spotify_api import SpotifyApiBridge, SpotifyApiError

TOKEN = {"access_token": "DEMO_ACCESS_NOT_A_CREDENTIAL", "refresh_token": "DEMO_REFRESH_NOT_A_CREDENTIAL",
         "expires_in": 3600, "token_type": "Bearer"}


class FakeConnection:
    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = bytearray()
        self.timeouts = []

    def makefile(self, *args): return self.input
    def sendall(self, data): self.output.extend(data)
    def settimeout(self, value): self.timeouts.append(value)


class SpotifySecurityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "tokens.json"
        self.api = SpotifyApiBridge("PUBLIC_DEMO_CLIENT_ID", self.path)
        for method in ("connect", "bind"):
            guard = patch.object(socket.socket, method, side_effect=AssertionError("Real network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)

    def flow(self, requests, *, browser_error=None, browser_ok=True, token_error=None):
        case = self
        self.now = 100.0
        self.connections = []
        self.auth_query = {}

        class Server:
            def __init__(self, address, handler):
                case.assertEqual(address, ("127.0.0.1", 43821))
                self.handler, self.closed, self.index = handler, False, 0
                case.server = self

            def handle_request(self):
                if self.index >= len(requests):
                    case.now += self.timeout
                    return
                request = requests[self.index]
                self.index += 1
                request = request.replace("{state}", case.auth_query["state"][0])
                connection = FakeConnection(request.encode("ascii"))
                case.connections.append(connection)
                self.handler(connection, ("127.0.0.1", 12345), self)
                case.now += 0.2

            def server_close(self): self.closed = True

        def browser(url):
            self.auth_query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            if browser_error:
                raise browser_error
            return browser_ok

        self.api._form_request = Mock(side_effect=token_error, return_value=TOKEN.copy())
        with patch("spotify_api._CallbackServer", Server), \
             patch("spotify_api.webbrowser.open", side_effect=browser), \
             patch("spotify_api.time.monotonic", side_effect=lambda: self.now):
            return self.api.authorize_interactive(timeout_seconds=3)

    @staticmethod
    def request(path="/callback?code=DEMO_CODE&state={state}", host="127.0.0.1:43821", method="GET"):
        return f"{method} {path} HTTP/1.1\r\nHost: {host}\r\n\r\n"

    def test_invalid_requests_do_not_consume_flow_or_bypass_state(self):
        invalid = [self.request("/favicon.ico"), self.request(host="untrusted.invalid"),
                   self.request("/other?code=DEMO&state={state}"),
                   self.request("http://127.0.0.1:43821/callback?code=DEMO&state={state}"),
                   self.request("/callback?code=DEMO&state=wrong"),
                   self.request("/callback?error=access_denied"),
                   self.request("/callback?code=DEMO&code=OTHER&state={state}"),
                   self.request("/callback?code=DEMO&state={state}&state={state}"),
                   self.request("/callback?code=DEMO&error=denied&state={state}"),
                   self.request("/callback?code=DEMO&state="),
                   self.request(method="POST"),
                   self.request(host="127.0.0.1:43821\r\nHost: 127.0.0.1:43821")]
        for request in invalid:
            with self.subTest(request=request):
                self.assertTrue(self.flow([request, self.request()]))
                self.assertTrue(self.server.closed)
                self.assertEqual(self.server.index, 2)
                self.api._form_request.assert_called_once()
                self.assertTrue(bytes(self.connections[-1].output).startswith(b"HTTP/1.0 200"))
                self.assertNotIn(b"Spotify anslutet", self.connections[-1].output)
                self.assertLessEqual(self.connections[-1].timeouts[0], 2)

    def test_pkce_matches_verifier_and_registered_redirect(self):
        self.assertTrue(self.flow([self.request()]))
        values = self.api._form_request.call_args.args[1]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(values["code_verifier"].encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(self.auth_query["code_challenge"], [challenge])
        self.assertEqual(self.auth_query["code_challenge_method"], ["S256"])
        self.assertEqual(values["redirect_uri"], api_module.REDIRECT_URI)
        self.assertGreaterEqual(len(values["code_verifier"]), 43)
        self.assertLessEqual(len(values["code_verifier"]), 128)

    def test_valid_denial_closes_without_touching_tokens(self):
        self.api._set_tokens(TOKEN.copy())
        previous = self.path.read_bytes()
        with self.assertRaisesRegex(SpotifyApiError, "authorization denied"):
            self.flow([self.request("/callback?error=private_text&state={state}")])
        self.api._form_request.assert_not_called()
        self.assertTrue(self.server.closed)
        self.assertEqual(self.path.read_bytes(), previous)

    def test_timeout_browser_and_token_failures_always_close(self):
        cases = [{}, {"browser_ok": False}, {"browser_error": RuntimeError("demo")},
                 {"token_error": SpotifyApiError("demo")}]
        for options in cases:
            with self.subTest(options=options):
                with self.assertRaises((SpotifyApiError, RuntimeError)):
                    self.flow([self.request()] if options.get("token_error") else [], **options)
                self.assertTrue(self.server.closed)
                self.assertFalse(self.path.exists())

    def test_socket_absolute_deadline_is_checked_before_reading(self):
        connection = api_module._CallbackSocket.__new__(api_module._CallbackSocket)
        connection._io_refs = 0
        connection._closed = False
        self.addCleanup(connection.close)
        connection.deadline = 1
        with patch("spotify_api.time.monotonic", return_value=2):
            with self.assertRaises(TimeoutError):
                connection.recv_into(bytearray(10))

    def test_invalid_token_payload_keeps_working_memory_and_disk(self):
        self.api._set_tokens(TOKEN.copy())
        previous = self.path.read_bytes()
        old_memory = self.api._tokens.copy()
        invalid = [[], {}, dict(TOKEN, access_token=""), dict(TOKEN, refresh_token=None),
                   dict(TOKEN, access_token="DEMO\r\nInjected"), dict(TOKEN, expires_in=float("nan")),
                   dict(TOKEN, expires_in=-1), dict(TOKEN, expires_in=10**400), dict(TOKEN, expires_in="3600"),
                   dict(TOKEN, token_type="Basic")]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(SpotifyApiError):
                self.api._set_tokens(payload)
            self.assertEqual(self.api._tokens, old_memory)
            self.assertEqual(self.path.read_bytes(), previous)
        for bad_value in (object(), float("nan")):
            with self.subTest(serialization=type(bad_value).__name__):
                with self.assertRaisesRegex(SpotifyApiError, "Invalid Spotify token response"):
                    self.api._set_tokens(dict(TOKEN, extra=bad_value))
                self.assertEqual(self.api._tokens, old_memory)
                self.assertEqual(self.path.read_bytes(), previous)
        with patch("atomic_file.os.replace", side_effect=OSError("demo disk failure")):
            with self.assertRaises(OSError):
                self.api._set_tokens(dict(TOKEN, access_token="DEMO_NEW_ACCESS"))
        self.assertEqual(self.api._tokens, old_memory)
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.glob(".*.tmp")), [])

    def test_corrupt_token_file_is_not_overwritten(self):
        for damaged in (b'[]', b'{"refresh_token":42}', b'incomplete',
                        b'{"expires_at":"bad"}', b'{"expires_at":NaN}',
                        b'{"adaptive_last_request_at":null}'):
            with self.subTest(damaged=damaged):
                self.path.write_bytes(damaged)
                with self.assertRaises(SpotifyApiError):
                    SpotifyApiBridge("PUBLIC_DEMO", self.path)
                self.assertEqual(self.path.read_bytes(), damaged)

    def test_corrupt_credentials_keep_local_media_bridge_available(self):
        from media_bridge import WindowsMediaBridge
        self.path.write_bytes(b'{"expires_at":"bad"}')
        errors = Mock()
        bridge = WindowsMediaBridge(Mock(), on_error=errors, spotify_client_id="PUBLIC_DEMO",
                                    spotify_token_path=self.path)
        self.assertIsNone(bridge._spotify)
        self.assertEqual(bridge.status()["spotify"]["state"], "error")
        self.assertEqual(self.path.read_bytes(), b'{"expires_at":"bad"}')
        errors.assert_called_once()

    def test_deep_token_json_keeps_original_and_local_bridge_available(self):
        from media_bridge import WindowsMediaBridge
        damaged = b'{"metadata":' + b'[' * 1500 + b'0' + b']' * 1500 + b'}'
        self.path.write_bytes(damaged)
        bridge = WindowsMediaBridge(Mock(), spotify_client_id="PUBLIC_DEMO", spotify_token_path=self.path)
        self.assertIsNone(bridge._spotify)
        self.assertEqual(bridge.status()["spotify"]["state"], "error")
        self.assertEqual(self.path.read_bytes(), damaged)
        deep = []
        for _ in range(1500):
            deep = [deep]
        self.path.unlink()
        self.api._set_tokens(TOKEN.copy())
        original = self.path.read_bytes()
        previous = self.api._tokens.copy()
        with self.assertRaises(SpotifyApiError):
            self.api._set_tokens(dict(TOKEN, metadata=deep))
        self.assertEqual(self.api._tokens, previous)
        self.assertEqual(self.path.read_bytes(), original)

    def test_atomic_token_writes_use_unique_temporary_files(self):
        import atomic_file
        replace = atomic_file.os.replace
        names = []

        def observe(source, destination):
            names.append(str(source))
            return replace(source, destination)

        with patch("atomic_file.os.replace", side_effect=observe):
            self.api._set_tokens(TOKEN.copy())
            self.api._save_tokens()
        self.assertEqual(len(set(names)), 2)
        self.assertEqual(list(self.path.parent.glob(".*.tmp")), [])

    def test_all_authenticated_redirects_are_refused(self):
        request = urllib.request.Request("https://api.spotify.com/v1/me/player", headers={"Authorization": "Bearer DEMO"})
        for code in (301, 302, 303, 307, 308):
            for destination in ("https://api.spotify.com/other", "https://example.invalid/", "http://api.spotify.com/"):
                with self.subTest(code=code, destination=destination), self.assertRaises(urllib.error.HTTPError):
                    api_module._NoRedirect().redirect_request(request, None, code, "demo", {}, destination)
        with patch("spotify_api.urllib.request.build_opener") as opener:
            with self.assertRaises(SpotifyApiError):
                api_module._spotify_urlopen(urllib.request.Request("http://api.spotify.com/"), timeout=1)
            opener.assert_not_called()

    def test_json_and_artwork_body_reads_are_bounded(self):
        response = Mock()
        response.read.return_value = b"x" * 11
        with self.assertRaises(SpotifyApiError):
            api_module._read_limited(response, 10)
        response.read.assert_called_once_with(11)
        response.read.return_value = b"demo artwork"
        opener = Mock()
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        with patch("spotify_api.urllib.request.build_opener", return_value=opener):
            self.assertEqual(self.api._download("https://example.invalid/cover.png"), b"demo artwork")
        request = opener.open.call_args.args[0]
        self.assertIsNone(request.get_header("Authorization"))
        response.read.assert_called_with(api_module.MAX_ARTWORK_BYTES + 1)


class SetupOwnershipTests(unittest.TestCase):
    def invoke(self, args, *, acquired=True, failure=None):
        with patch.object(sys, "argv", ["bongo", *args]), \
             patch("main.diagnostics"), patch("main._instance_lock") as lock, \
             patch("main.ConfigManager") as config, patch("main.SpotifyApiBridge") as bridge, \
             patch("main._setup_error") as error:
            lock.acquire.return_value = acquired
            config.return_value.config_dir = Path("SYNTHETIC_PROFILE_NOT_USED")
            config.return_value.get_setting.return_value = "PUBLIC_DEMO_CLIENT_ID"
            bridge.return_value.authorize_interactive.side_effect = failure
            result = main.main()
            return result, lock, config, bridge, error

    def test_running_app_blocks_link_and_client_id_before_any_config_or_token_use(self):
        for args in (["--link-spotify"], ["--spotify-client-id", "PUBLIC_DEMO"]):
            with self.subTest(args=args):
                result, lock, config, bridge, error = self.invoke(args, acquired=False)
                self.assertEqual(result, 1)
                config.assert_not_called()
                bridge.assert_not_called()
                lock.close.assert_not_called()
                error.assert_called_once()

    def test_setup_always_releases_owned_lock(self):
        for failure in (None, SpotifyApiError("demo"), OSError("demo")):
            with self.subTest(failure=failure):
                result, lock, config, bridge, error = self.invoke(["--link-spotify"], failure=failure)
                self.assertEqual(result, 0 if failure is None else 1)
                lock.close.assert_called_once_with()
                bridge.return_value.authorize_interactive.assert_called_once_with()

    def test_windowed_setup_error_is_visible(self):
        with patch("main._WINDOWED", True), patch("main.os.name", "nt"), \
             patch("ctypes.windll.user32.MessageBoxW") as message:
            main._setup_error("Close app before linking")
        message.assert_called_once()

    def test_malformed_token_extension_reaches_neutral_cli_error_feedback(self):
        with tempfile.TemporaryDirectory() as folder:
            api = SpotifyApiBridge("PUBLIC_DEMO", Path(folder) / "tokens.json")
            api._set_tokens(TOKEN.copy())
            original = api.token_path.read_bytes()
            api.authorize_interactive = lambda: api._set_tokens(dict(TOKEN, extension=float("nan")))
            with patch.object(sys, "argv", ["bongo", "--link-spotify"]), \
                 patch("main.diagnostics"), patch("main._instance_lock") as lock, \
                 patch("main.ConfigManager") as config, patch("main.SpotifyApiBridge", return_value=api), \
                 patch("main._setup_error") as error:
                config.return_value.get_setting.return_value = "PUBLIC_DEMO"
                config.return_value.config_dir = Path(folder)
                self.assertEqual(main.main(), 1)
                error.assert_called_once_with("Spotify setup failed: Invalid Spotify token response")
                lock.close.assert_called_once_with()
            self.assertEqual(api.token_path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
