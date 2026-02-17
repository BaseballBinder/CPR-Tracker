"""
CPR Performance Tracker - Desktop Entry Point
Starts FastAPI in a background thread and opens a pywebview window.
Falls back to the default browser if pywebview is not available.
This is the target for PyInstaller.
"""
import sys
import os
import socket
import threading
import time
import logging
import urllib.request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if pywebview is available
try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False
    logger.info("pywebview not available — will open in default browser")


def find_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def start_server(port: int) -> None:
    """Run uvicorn in a background thread."""
    import uvicorn
    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def wait_for_server(port: int, timeout: float = 15.0) -> bool:
    """Poll the health check endpoint until the server is ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/__health", timeout=1)
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.15)
    return False


def _cleanup_update_artifacts() -> None:
    """Remove leftover update files from a previous auto-update."""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    updates_dir = os.path.join(appdata, "CPR-Tracker", "_updates")
    if os.path.isdir(updates_dir):
        import shutil
        try:
            shutil.rmtree(updates_dir)
            logger.info("Cleaned up update artifacts")
        except Exception as e:
            logger.warning(f"Could not clean update artifacts: {e}")


def main() -> None:
    """Main entry point for the desktop application."""
    _cleanup_update_artifacts()

    # Ensure AppData directory exists
    from app.desktop_config import ensure_appdata_dir
    ensure_appdata_dir()

    port = find_free_port()
    logger.info(f"Starting server on port {port}")

    # Set port as env var so the app can reference it if needed
    os.environ["CPR_TRACKER_PORT"] = str(port)

    # Start FastAPI in a daemon thread
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server to be ready
    if not wait_for_server(port):
        logger.error("Server failed to start within timeout")
        if HAS_WEBVIEW:
            try:
                webview.create_window(
                    "CPR Tracker - Error",
                    html="<html><body style='font-family:sans-serif;padding:40px;text-align:center;'>"
                         "<h2>Server failed to start</h2>"
                         "<p>Please try restarting the application.</p>"
                         "</body></html>",
                    width=400, height=200,
                )
                webview.start()
            except Exception:
                pass
        else:
            print("ERROR: Server failed to start within timeout. Please restart.")
        sys.exit(1)

    url = f"http://127.0.0.1:{port}/landing"
    logger.info(f"Server ready at http://127.0.0.1:{port}")

    if HAS_WEBVIEW:
        # Native window using Edge WebView2
        window = webview.create_window(
            title="CPR Performance Tracker",
            url=url,
            width=1400,
            height=900,
            min_size=(1024, 700),
            text_select=True,
        )
        webview.start(debug=not getattr(sys, 'frozen', False))
    else:
        # Fallback: open in default browser (dev mode without pywebview)
        import webbrowser
        webbrowser.open(url)
        print(f"\n  CPR Performance Tracker running at: {url}")
        print("  Press Ctrl+C to stop.\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
