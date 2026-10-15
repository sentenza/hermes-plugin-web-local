"""Transport deadline checks, with real httpx and controlled byte arrivals."""
import httpx

import provider as local


def test_slow_drip_stops_and_closes_before_consuming_whole_body(monkeypatch):
    clock = [0.0]
    consumed = []
    closed = []

    class Drip(httpx.SyncByteStream):
        def __iter__(self):
            for i in range(10):
                clock[0] += 0.4
                consumed.append(i)
                yield b"x"

        def close(self):
            closed.append(True)

    monkeypatch.setattr(local, "monotonic", lambda: clock[0], raising=False)
    monkeypatch.setattr(local, "_EXTRACT_TIMEOUT_SECS", 1.0)
    monkeypatch.setattr(local, "is_safe_url", lambda url: True)
    monkeypatch.setattr(local, "check_website_access", lambda url: None)
    monkeypatch.setattr(local, "_make_client", lambda: httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(
            200, headers={"content-type": "text/plain"}, stream=Drip()))))
    result = local._fetch_readable("https://drip.example")
    assert "deadline" in result.get("error", "").lower()
    assert "content" not in result
    assert consumed == [0, 1, 2]
    assert closed == [True]


def test_redirect_does_not_start_new_request_after_deadline(monkeypatch):
    clock = [0.0]
    requested = []

    def handler(request):
        requested.append(str(request.url))
        clock[0] = 2.0
        return httpx.Response(302, headers={"location": "/next"})

    monkeypatch.setattr(local, "monotonic", lambda: clock[0])
    monkeypatch.setattr(local, "_EXTRACT_TIMEOUT_SECS", 1.0)
    monkeypatch.setattr(local, "is_safe_url", lambda url: True)
    monkeypatch.setattr(local, "check_website_access", lambda url: None)
    monkeypatch.setattr(local, "_make_client", lambda: httpx.Client(
        transport=httpx.MockTransport(handler)))
    result = local._fetch_readable("https://redirect.example")
    assert "deadline" in result.get("error", "").lower()
    assert requested == ["https://redirect.example"]


def test_real_loopback_slow_drip_and_fast_body(monkeypatch):
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    disconnected = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            try:
                if self.path == "/fast":
                    self.wfile.write(b"readable")
                else:
                    for _ in range(100):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.02)
            except (BrokenPipeError, ConnectionResetError):
                disconnected.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    # Test-only loopback client; production SSRF checks are not changed.
    monkeypatch.setattr(local, "is_safe_url", lambda url: url.startswith(base + "/"))
    monkeypatch.setattr(local, "check_website_access", lambda url: None)
    monkeypatch.setattr(local, "_make_client", lambda: httpx.Client(timeout=0.5, trust_env=False))
    monkeypatch.setattr(local, "_EXTRACT_TIMEOUT_SECS", 0.2)
    try:
        assert local._fetch_readable(base + "/fast")["content"] == b"readable"
        result = local._fetch_readable(base + "/slow")
        assert "deadline" in result.get("error", "").lower()
        assert "content" not in result
        assert disconnected.wait(1), "server must observe the closed HTTP stream"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
