"""Render the integrated GUI for visual comparison, using the live widgets.

Legacy invocation: python -m software.ui.proto v3 out.png.
Historical measurements and crops remain in docs/. All previews render the
integrated application so the prototype cannot drift from the GUI.
"""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from software.gui.main_window import MainWindow
from software.qt_bootstrap import configure_qt_plugins
from PyQt5 import QtWidgets


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else 'v3'
    if version not in ('v1', 'v2', 'v3'):
        raise SystemExit('Usage: python -m software.ui.proto [v1|v2|v3] [out.png]')
    output = sys.argv[2] if len(sys.argv) > 2 else 'proto_out.png'
    configure_qt_plugins()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from unittest.mock import patch
    with patch('serial.tools.list_ports.comports', return_value=[]):
        window = MainWindow(load_sample_on_start=True)
    window.timer_hotplug.stop()
    window.resize(1780, 1197)
    window.show()
    for _ in range(5):
        app.processEvents()
    if not window.grab().save(output):
        raise SystemExit(f'Cannot save preview: {output}')
    window.close()
    print(f'Saved integrated GUI ({version} compatibility): {output}')


if __name__ == '__main__':
    main()
