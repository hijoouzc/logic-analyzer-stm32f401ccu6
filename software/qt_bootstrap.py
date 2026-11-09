"""Configure Qt before QApplication (Qt 5 on Windows can mangle non-ASCII paths)."""
from pathlib import Path
import os
import PyQt5
from PyQt5.QtCore import QCoreApplication


def configure_qt_plugins():
    # Qt's offscreen plugin does not query the Windows system font database.
    # Point it at real fonts so headless tests/screenshots contain readable text.
    if os.name == 'nt' and os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        if fonts.is_dir():
            os.environ.setdefault('QT_QPA_FONTDIR', str(fonts))
    plugins = Path(PyQt5.__file__).resolve().parent / 'Qt5' / 'plugins'
    if plugins.is_dir():
        # Use the Unicode API instead of Qt's locale-dependent installation path.
        paths = QCoreApplication.libraryPaths()
        QCoreApplication.setLibraryPaths([str(plugins)] + [p for p in paths if Path(p).is_dir() and p != str(plugins)])
