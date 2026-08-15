#!/usr/bin/env python3
"""原型静态服务 — 零依赖 stdlib。

用法:
    python3 serve.py [root] [port]

默认 root=~/www, port=8008。
与 caddy 版本的差别只有实现,对外行为一致:目录索引 + no-cache。
no-cache 是为了让 ?v=N 之外再多一层保险 —— 对方浏览器不会拿到旧页面。
"""
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/www")
PORT = int(sys.argv[2] if len(sys.argv) > 2 else os.environ.get("PROTO_PORT", 8008))


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), partial(Handler, directory=ROOT))
    srv.daemon_threads = True
    sys.stderr.write("serving %s on 0.0.0.0:%d\n" % (ROOT, PORT))
    srv.serve_forever()
