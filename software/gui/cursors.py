"""Legacy cursor API forwarding to the waveform's existing cursors and HUD."""
from PyQt5 import QtCore
from software.gui.waveform_widget import (
    WaveformHUD as CursorHUDWidget,
    format_si_time as format_time,
    format_si_freq as format_freq,
)


class CursorManager(QtCore.QObject):
    sigCursorsChanged = QtCore.pyqtSignal(float, float, float)

    def __init__(self, plot_widget, hud_widget=None):
        super().__init__(plot_widget)
        self.waveform = plot_widget.la_waveform
        self.cursor_a = self.waveform.cursor_a
        self.cursor_b = self.waveform.cursor_b
        self.hud_widget = hud_widget or self.waveform.hud
        self.cursor_a.sigPositionChanged.connect(self._on_cursor_moved)
        self.cursor_b.sigPositionChanged.connect(self._on_cursor_moved)

    def set_visible(self, visible):
        self.waveform.toggle_cursors(visible)

    def is_visible(self):
        return self.cursor_a.isVisible()

    def set_positions(self, t_a, t_b):
        self.waveform.set_cursor_positions(t_a, t_b)

    def get_positions(self):
        return float(self.cursor_a.value()), float(self.cursor_b.value())

    def get_delta_t(self):
        return self.waveform.get_delta_t()

    def get_frequency(self):
        return self.waveform.get_frequency()

    def _on_cursor_moved(self):
        t_a, t_b = self.get_positions()
        self.hud_widget.update_values(t_a, t_b)
        self.sigCursorsChanged.emit(t_a, t_b, abs(t_b - t_a))
