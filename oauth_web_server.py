"""Web-based OAuth authorization flow for non-interactive environments."""

import logging
import socket
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs

logger = logging.getLogger(__name__)


class OAuthWebHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for web-based OAuth flow."""

    verification_code: str | None = None
    authorization_url: str = ""

    def log_message(self, format: str, *args: object) -> None:
        """Suppress server logs."""
        pass

    def do_GET(self) -> None:
        """Serve the OAuth authorization page."""
        # fmt: off
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>E*TRADE MCP Server - Authorization</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
        .container {{ background: #f5f5f5; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #333; }}
        .notice {{ background: #fff3cd; border-left: 4px solid #ff9800; padding: 12px; margin: 20px 0; font-size: 14px; }}
        .step {{ margin: 20px 0; padding: 15px; background: white; border-radius: 4px; }}
        .step-number {{ color: #007bff; font-weight: bold; }}
        input[type="text"] {{ width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px; }}
        button {{ background: #007bff; color: white; padding: 12px 24px; font-size: 16px; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px; }}
        button:hover {{ background: #0056b3; }}
        a {{ color: #007bff; text-decoration: none; font-weight: bold; }}
        a:hover {{ text-decoration: underline; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>E*TRADE MCP Server Authorization</h1>

        <div class="step">
            <p><span class="step-number">Step 1:</span> Click this link to authorize with E*TRADE:</p>
            <p><a href="{self.authorization_url}" target="_blank">Open E*TRADE Authorization Page</a></p>
        </div>

        <div class="step">
            <p><span class="step-number">Step 2:</span> After authorizing on E*TRADE's website, they will show you a verification code.</p>
        </div>

        <div class="step">
            <p><span class="step-number">Step 3:</span> Enter the verification code below:</p>
            <form action="/" method="POST">
                <input type="text" name="code" placeholder="Enter verification code" autofocus required />
                <button type="submit">Submit Code</button>
            </form>
        </div>

        <div class="footer">
            This page will close automatically after successful authorization.
        </div>

        <div class="notice">
            <strong>Note:</strong> This page is served by your local E*TRADE MCP server.
            It is not affiliated with or maintained by E*TRADE. This is a temporary authorization flow
            to connect your MCP server to your E*TRADE account via your AI chat client.
        </div>
    </div>
</body>
</html>"""
        # fmt: on
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def do_POST(self) -> None:
        """Handle verification code submission."""
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length).decode()
        params = parse_qs(post_data)

        code = params.get("code", [""])[0].strip()
        if code:
            OAuthWebHandler.verification_code = code
            # fmt: off
            html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Authorization Complete</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }
        .success { background: #d4edda; color: #155724; padding: 20px; border-radius: 8px; margin: 20px 0; }
        h1 { color: #155724; }
    </style>
</head>
<body>
    <div class="success">
        <h1>✓ Authorization Complete</h1>
        <p>You can close this window and return to your application.</p>
    </div>
</body>
</html>"""
            # fmt: on
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
        else:
            self.send_response(400)
            self.end_headers()


def run_web_oauth_flow(authorization_url: str, timeout: int = 300) -> str:
    """Run OAuth authorization flow via temporary web server.

    Args:
        authorization_url: The OAuth provider's authorization URL
        timeout: Maximum time to wait for verification code (seconds)

    Returns:
        Verification code entered by user

    Raises:
        TimeoutError: If user doesn't complete authorization within timeout
    """
    # Find an available port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    # Set up handler with authorization URL
    OAuthWebHandler.authorization_url = authorization_url
    OAuthWebHandler.verification_code = None

    # Start server in background thread
    server = HTTPServer(("localhost", port), OAuthWebHandler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Open browser to local authorization page
    local_url = f"http://localhost:{port}"
    logger.info(f"Opening browser to {local_url} for OAuth flow")
    webbrowser.open(local_url)

    # Wait for verification code with timeout
    start_time = time.time()

    while OAuthWebHandler.verification_code is None:
        if time.time() - start_time > timeout:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=1)
            raise TimeoutError(
                f"OAuth authorization timed out after {timeout} seconds. "
                "Please try again."
            )
        time.sleep(0.5)

    # Got the code, shut down server
    verification_code = OAuthWebHandler.verification_code
    server.shutdown()
    server.server_close()
    server_thread.join(timeout=1)
    logger.info("Received verification code via web flow")

    return verification_code
