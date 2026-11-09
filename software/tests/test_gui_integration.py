"""Portable serial/decoder/GUI integration, using a local TCP mock instead of Unix pty."""
from pathlib import Path
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from software.gui.logic_client import LogicAnalyzerClient
from software.decoders.uart_decoder import UARTDecoder
from software.tests.mock_device import MockDevice
from software.qt_bootstrap import configure_qt_plugins


def test_gui_integration():
    with MockDevice() as mock:
        client = LogicAnalyzerClient()
        try:
            assert client.connect(mock.url)[0]
            assert client.ping() == (True, 'v1.0.0')
            result = client.start_capture(rate_idx=3, trig_ch=0, trig_mode=2)
            assert result['success'], result.get('error')
            assert result['checksum_ok'] and result['trig_offset'] == 6554
            assert len(result['channels']) == 8
            assert all(len(c) == 32768 for c in result['channels'])
            text, frames = UARTDecoder().decode(result['channels'][0])
            assert text == 'TEST_LA_2026\r\n'
            assert len(frames) == 14
        finally:
            client.disconnect()

    configure_qt_plugins()
    from PyQt5.QtWidgets import QApplication
    from software.gui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        win._render_capture_data(result)
        assert win.current_data is result
        assert win.txt_decoded.toPlainText().strip() == text.strip()
        assert win.table_frames.rowCount() == 14
    finally:
        win.close()
        app.processEvents()


run_integration_test = test_gui_integration

if __name__ == '__main__':
    test_gui_integration()
    print('PASS: mock TCP -> protocol parser -> UART -> GUI (no hardware).')
