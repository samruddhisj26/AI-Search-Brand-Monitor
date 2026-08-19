"""
tests/test_web.py — smoke tests for brand_monitor/web.py's dashboard server.

Covers two T023 regressions:
  * web.main() used to call sys.exit(1) when the database was missing.
    SystemExit doesn't inherit from Exception, so it escaped cli.py's
    `except Exception` dispatch guard and broke the documented contract
    that cli.main(argv) always RETURNS an int. Fixed by having web.main()
    return an int (1 missing DB / 0 clean shutdown) instead.
  * `/api/data` used to send `Access-Control-Allow-Origin: *` with no
    authentication, letting any page the user has open in another tab
    read the whole dataset from the local dashboard while it's running.
    Fixed by dropping the header entirely (the shipped UI and the API
    are same-origin, so nothing legitimate needs it).
"""

import http.client
import http.server
import threading

from brand_monitor import web
from brand_monitor.db import init_db


def test_main_returns_one_when_db_missing(temp_db_path, capsys):
    # temp_db_path points config at a path that is never created (init_db()
    # is intentionally not called here), so web.main() must see it as missing.
    code = web.main(port=0)

    assert code == 1
    captured = capsys.readouterr()
    assert "brand-monitor scan" in captured.out


def test_api_data_response_has_no_cors_header(temp_db_path):
    init_db()  # table must exist so the handler can query it cleanly

    server = http.server.HTTPServer(("127.0.0.1", 0), web.DashboardHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/api/data")
        resp = conn.getresponse()
        body = resp.read()
        headers = {k.lower() for k, v in resp.getheaders()}

        assert "access-control-allow-origin" not in headers
        assert body  # got a real JSON body, not a broken response
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
