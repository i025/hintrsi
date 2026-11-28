"""Expose only the model proxy's Unix socket inside an isolated network namespace."""
import selectors
import socket
import socketserver
import sys


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as upstream:
            upstream.connect(sys.argv[1])
            with selectors.DefaultSelector() as selector:
                selector.register(self.request, selectors.EVENT_READ, upstream)
                selector.register(upstream, selectors.EVENT_READ, self.request)
                while True:
                    for key, _ in selector.select():
                        data = key.fileobj.recv(65536)
                        if not data:
                            return
                        key.data.sendall(data)


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


with Server(('127.0.0.1', 18767), Handler) as server:
    server.serve_forever()
