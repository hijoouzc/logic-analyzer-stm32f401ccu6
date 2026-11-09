"""Loopback-only TCP mock, portable to Windows/Linux; never requires a board."""
import socket
import socketserver
import threading
import time
from software.protocol import RATES, command, xor_bytes
from software.tests.generate_test_data import make_packet


def control(code, fields=(0, 0, 0)):
    packet = bytes((0x5A, 0xA5, code, *fields))
    return packet + bytes((xor_bytes(packet),))


class MockDevice(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address=('127.0.0.1', 0)):
        super().__init__(address, MockHandler)

    @property
    def url(self):
        return f'socket://127.0.0.1:{self.server_address[1]}'

    def __enter__(self):
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self.shutdown()
        self.server_close()
        self._thread.join(timeout=2)


class MockHandler(socketserver.BaseRequestHandler):
    def handle(self):
        rx = bytearray()
        pending = None
        self.request.settimeout(.01)
        try:
            while True:
                try:
                    data = self.request.recv(512)
                    if not data:
                        break
                    rx.extend(data)
                except socket.timeout:
                    pass
                while len(rx) >= 5:
                    if rx[0] != 0xA5:
                        del rx[0]
                        continue
                    cmd, rate, trig = rx[1:4]
                    error = (0xE0 if xor_bytes(rx[:5]) else
                             0xE1 if cmd == 1 and rate >= len(RATES) else
                             0xE2 if cmd == 1 and (trig >> 4 > 7 or trig & 15 > 2) else
                             0xE3 if cmd == 1 and pending else None)
                    if error:
                        self.request.sendall(control(error, (cmd, rate, trig)))
                        del rx[0]
                        continue
                    del rx[:5]
                    if cmd == 3:
                        self.request.sendall(control(4, (1, 0, 0)))
                    elif cmd == 2:
                        pending = None
                        self.request.sendall(control(5))
                    elif cmd == 1:
                        pending = (time.monotonic()+.15, make_packet(RATES[rate], 1 if trig & 15 == 0 else 0, trig >> 4))
                if pending and time.monotonic() >= pending[0]:
                    packet = pending[1]
                    pending = None
                    # Blocking stream deliberately ignores incoming commands while transmitting.
                    for i in range(0, len(packet), 512):
                        self.request.sendall(packet[i:i+512])
                        time.sleep(.001)
        except (OSError, ConnectionError):
            pass
