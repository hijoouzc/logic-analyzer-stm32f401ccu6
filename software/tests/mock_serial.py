"""Portable mock device. Run: python tests/mock_serial.py --port 8765."""
from pathlib import Path
import argparse
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from software.tests.mock_device import MockDevice


def run_mock_server(port=8765):
    with MockDevice(('127.0.0.1', port)) as server:
        print(f'Mock STM32 running: {server.url}', flush=True)
        print('Paste this URL in the editable GUI port box (uncheck Offline Mock).', flush=True)
        print('Simulates protocol traffic, not hardware timing. Ctrl+C to stop.', flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    run_mock_server(parser.parse_args().port)
