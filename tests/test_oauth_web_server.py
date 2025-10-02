"""Isolated tests for OAuth web server - testing the real implementation."""

import re
import time
import urllib.request
from http.server import HTTPServer
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode

import pytest

from oauth_web_server import OAuthWebHandler, run_web_oauth_flow


def test_oauth_handler_serves_authorization_page(unused_tcp_port: int) -> None:
    """Test that the handler serves the authorization page with correct content."""
    # Set up the authorization URL
    test_auth_url = "https://etrade.com/authorize?token=test123"
    OAuthWebHandler.authorization_url = test_auth_url
    OAuthWebHandler.verification_code = None

    server = HTTPServer(("localhost", unused_tcp_port), OAuthWebHandler)
    server_thread = Thread(target=server.serve_forever)
    server_thread.start()

    try:
        # Give server time to start
        time.sleep(0.2)

        # Make GET request
        with urllib.request.urlopen(f"http://localhost:{unused_tcp_port}/") as response:
            html = response.read().decode()
            # Verify the HTML contains expected elements
            assert response.status == 200
        assert "E*TRADE Authorization" in html
        assert test_auth_url in html
        assert "Step 1" in html
        assert "Step 2" in html
        assert "Step 3" in html
        assert 'name="code"' in html
        assert 'charset="UTF-8"' in html

    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1)


def test_oauth_handler_accepts_verification_code(unused_tcp_port: int) -> None:
    """Test that the handler accepts and stores verification code via POST."""
    OAuthWebHandler.authorization_url = "https://example.com/auth"
    OAuthWebHandler.verification_code = None

    server = HTTPServer(("localhost", unused_tcp_port), OAuthWebHandler)
    server_thread = Thread(target=server.serve_forever)
    server_thread.start()

    try:
        time.sleep(0.2)

        # Submit verification code
        test_code = "ABC123XYZ"
        post_data = urlencode({"code": test_code}).encode()

        request = urllib.request.Request(
            f"http://localhost:{unused_tcp_port}/", data=post_data, method="POST"
        )
        with urllib.request.urlopen(request) as response:
            html = response.read().decode()
            # Verify response
            assert response.status == 200
        assert "Authorization Complete" in html
        assert "✓" in html

        # Verify code was stored
        assert OAuthWebHandler.verification_code == test_code

    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1)


def test_oauth_handler_rejects_empty_code(unused_tcp_port: int) -> None:
    """Test that the handler rejects empty verification code."""
    OAuthWebHandler.authorization_url = "https://example.com/auth"
    OAuthWebHandler.verification_code = None

    server = HTTPServer(("localhost", unused_tcp_port), OAuthWebHandler)
    server_thread = Thread(target=server.serve_forever)
    server_thread.start()

    try:
        time.sleep(0.2)

        # Submit empty code
        post_data = urlencode({"code": ""}).encode()

        request = urllib.request.Request(
            f"http://localhost:{unused_tcp_port}/", data=post_data, method="POST"
        )

        # Should get 400 Bad Request
        with pytest.raises(HTTPError) as exc_info:
            urllib.request.urlopen(request)

        assert exc_info.value.code == 400

        # Verify code was NOT stored
        assert OAuthWebHandler.verification_code is None

    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1)


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_oauth_handler_rejects_whitespace_only_code(unused_tcp_port: int) -> None:
    """Test that the handler rejects whitespace-only verification code."""
    OAuthWebHandler.authorization_url = "https://example.com/auth"
    OAuthWebHandler.verification_code = None

    server = HTTPServer(("localhost", unused_tcp_port), OAuthWebHandler)
    server_thread = Thread(target=server.serve_forever)
    server_thread.start()

    try:
        time.sleep(0.2)

        # Submit whitespace-only code
        post_data = urlencode({"code": "   "}).encode()

        request = urllib.request.Request(
            f"http://localhost:{unused_tcp_port}/", data=post_data, method="POST"
        )

        with pytest.raises(HTTPError) as exc_info:
            urllib.request.urlopen(request)

        assert exc_info.value.code == 400
        assert OAuthWebHandler.verification_code is None

    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1)


def test_oauth_handler_trims_whitespace_from_code(unused_tcp_port: int) -> None:
    """Test that the handler trims whitespace from verification code."""
    OAuthWebHandler.authorization_url = "https://example.com/auth"
    OAuthWebHandler.verification_code = None

    server = HTTPServer(("localhost", unused_tcp_port), OAuthWebHandler)
    server_thread = Thread(target=server.serve_forever)
    server_thread.start()

    try:
        time.sleep(0.2)

        # Submit code with whitespace
        post_data = urlencode({"code": "  CODE123  "}).encode()

        request = urllib.request.Request(
            f"http://localhost:{unused_tcp_port}/", data=post_data, method="POST"
        )
        with urllib.request.urlopen(request) as response:
            html = response.read().decode()
            assert response.status == 200
            assert "Authorization Complete" in html
        # Verify whitespace was trimmed
        assert OAuthWebHandler.verification_code == "CODE123"

    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1)


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_run_web_oauth_flow_integration() -> None:
    """Integration test for the complete web OAuth flow."""
    auth_url = "https://etrade.com/authorize?token=abc123"
    test_code = "VERIFICATION_CODE_123"

    # Track if browser was opened
    browser_opened = []

    def mock_browser_open(url: str) -> bool:
        browser_opened.append(url)

        # Simulate user submitting code after a short delay
        def submit_code() -> None:  # pragma: no cover
            time.sleep(0.3)
            # Extract port from the URL that was opened
            match = re.search(r":(\d+)", url)
            if match:  # pragma: no cover
                port = int(match.group(1))
                # Submit the verification code
                post_data = urlencode({"code": test_code}).encode()
                request = urllib.request.Request(
                    f"http://localhost:{port}/", data=post_data, method="POST"
                )
                with urllib.request.urlopen(request):
                    pass

        Thread(target=submit_code).start()
        return True

    with patch(
        "oauth_web_server.webbrowser.open", autospec=True, side_effect=mock_browser_open
    ):
        # Run the OAuth flow
        code = run_web_oauth_flow(auth_url, timeout=5)

        # Verify we got the code back
        assert code == test_code

        # Verify browser was opened to localhost
        assert len(browser_opened) == 1
        assert "localhost" in browser_opened[0]


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_run_web_oauth_flow_timeout_real() -> None:
    """Test that run_web_oauth_flow actually times out when no code is provided."""
    auth_url = "https://example.com/auth"

    # Don't open browser, just suppress it
    with patch("oauth_web_server.webbrowser.open", autospec=True):
        # Use very short timeout
        start = time.time()

        with pytest.raises(TimeoutError, match="OAuth authorization timed out"):
            run_web_oauth_flow(auth_url, timeout=1)

        elapsed = time.time() - start

        # Verify it actually waited (allow some overhead for thread cleanup)
        assert 0.4 < elapsed < 1.5


def test_oauth_handler_suppresses_logs(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that OAuthWebHandler.log_message suppresses output."""
    handler = OAuthWebHandler.__new__(OAuthWebHandler)

    # Call log_message - should produce no output
    handler.log_message("Test message %s", "arg")

    # Verify nothing was printed
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_run_web_oauth_flow_finds_random_port() -> None:
    """Test that run_web_oauth_flow successfully finds an available port."""
    auth_url = "https://example.com/auth"
    ports_used = []

    def track_browser_open(url: str) -> bool:  # pragma: no cover
        # Extract the port
        match = re.search(r":(\d+)", url)
        if match:  # pragma: no cover
            ports_used.append(int(match.group(1)))

            # Submit code immediately
            def submit() -> None:
                time.sleep(0.1)
                port = ports_used[-1]
                post_data = urlencode({"code": "FAST"}).encode()
                request = urllib.request.Request(
                    f"http://localhost:{port}/", data=post_data, method="POST"
                )
                with urllib.request.urlopen(request):
                    pass

            Thread(target=submit).start()
        return True

    with patch(
        "oauth_web_server.webbrowser.open",
        autospec=True,
        side_effect=track_browser_open,
    ):
        code = run_web_oauth_flow(auth_url, timeout=2)

        assert code == "FAST"
        assert len(ports_used) == 1
        # Port should be in ephemeral range
        assert 1024 < ports_used[0] < 65535
