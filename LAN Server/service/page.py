#!/usr/bin/python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys

PAGE = b"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Contest LAN</title><main><h1>Contest LAN is online</h1><p>Your device reached the local contest server.</p></main></html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.serve(True)

    def do_HEAD(self):
        self.serve(False)

    def serve(self, body):
        if self.path != "/":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(PAGE)

if __name__ == "__main__":
    ThreadingHTTPServer((sys.argv[1], int(sys.argv[2])), Handler).serve_forever()
