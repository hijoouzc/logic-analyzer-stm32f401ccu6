"""User-facing workflow regressions. No hardware is touched."""
import csv
import json
import time
import numpy as np
import pytest
from PyQt5 import QtWidgets, QtCore
from software.protocol import parse_capture
from software.tests.generate_test_data import make_packet
from software.tests.mock_device import MockDevice
from software.utils.exporter import export_csv, export_vcd, export_image


def wait_for(qapp, predicate, seconds=5):
    deadline = time.monotonic()+seconds
    while not predicate():
        qapp.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError('Timed out waiting for worker/UI')
        time.sleep(.005)
    qapp.processEvents()


def test_offline_start_worker_lock_and_render(window, qapp):
    window.chk_mock.setChecked(True)
    window.combo_rate.setCurrentIndex(0)  # must not relabel 1 MHz fixture as 6 MHz
    window._on_start_capture()
    assert window._busy
    assert not window.act_start.isEnabled() and not window.act_ping.isEnabled()
    window._on_start_capture()  # repeated shortcut must not create another worker
    wait_for(qapp, lambda: not window._busy)
    assert window.worker is None and not window.client.is_connected
    assert window.current_data['sample_rate'] == 1000000
    assert window.table_frames.rowCount() == 14
    assert 'TEST_LA_2026' in window.txt_decoded.toPlainText()
    assert not window._test_messages


def test_ping_and_abort_async_tcp(window, qapp):
    with MockDevice() as server:
        window.combo_ports.setEditText(server.url)
        window._on_ping()
        wait_for(qapp, lambda: not window._busy)
        assert 'v1.0.0' in window.lbl_status.text()
        window._on_start_capture()
        QtCore.QTimer.singleShot(40, window._on_abort)
        wait_for(qapp, lambda: not window._busy)
        assert 'aborted' in window.lbl_status.text().lower()
        assert not window._test_messages


def test_window_close_waits_for_worker_without_terminate(window, qapp):
    with MockDevice() as server:
        window.show()
        window.combo_ports.setEditText(server.url)
        window._on_start_capture()
        window.close()
        assert window._closing and window._busy
        wait_for(qapp, lambda: not window._busy)
        assert not window.isVisible()
        assert window.worker is None


def test_bad_binary_preserves_previous_capture(window, tmp_path):
    previous = window.current_data
    path = tmp_path/'bad.bin'
    raw = bytearray(make_packet())
    raw[-1] ^= 1
    path.write_bytes(raw)
    assert not window._load_bin_file(str(path))
    assert window.current_data is previous
    assert window._test_messages


@pytest.mark.parametrize('status', [0, 1, 2])
def test_consistent_time_origin_waveform_table_csv(window, status, tmp_path):
    result = parse_capture(make_packet(status=status))
    window._render_capture_data(result)
    assert window.trigger_line.value() == 0
    x, _ = window.channel_curves[0].getData()
    assert x[0] == pytest.approx(-.006554)
    assert np.any(x == 0)
    assert len(x) < 500  # Flat runs are compressed only for drawing; all 32768 samples remain in the capture.
    assert float(window.table_frames.item(0, 2).text().split()[0]) == 0
    if status == 1:
        assert 'free-run' in window.trigger_line.label.format
    path = tmp_path/'capture.csv'
    assert export_csv(result, path)
    with path.open() as f:
        rows = list(csv.reader(f))
    assert len(rows) == 32769
    assert float(rows[1][0]) == pytest.approx(x[0])
    assert float(rows[6555][0]) == 0


def test_save_load_capture_preserves_rate_metadata_and_settings(window, monkeypatch, tmp_path):
    path = tmp_path/'saved.lacapture'
    data = parse_capture(make_packet(6000000), 6000000)
    window._render_capture_data(data)
    window.ch_name_edits[0].setText('UART <test>')
    window.waveform.set_channel_color(0, '#00aaff')
    window.waveform.set_channel_visible(7, False)
    window.analyzer['baudrate'] = 115200
    monkeypatch.setattr(QtWidgets.QFileDialog, 'getSaveFileName', lambda *a: (str(path), ''))
    window._save_capture_file()
    document = json.loads(path.read_text(encoding='utf-8'))
    assert document['sample_rate'] == 6000000
    window.analyzer['baudrate'] = 9600
    window.waveform.set_channel_color(0, '#ffffff')
    monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', lambda *a: (str(path), ''))
    window._open_capture_file()
    assert window.current_data['sample_rate'] == 6000000
    assert window.waveform.channel_colors[0] == '#00aaff'
    assert window.waveform.channel_names[0] == 'UART <test>'
    assert not window.waveform.channel_visible[7]
    assert window.analyzer['baudrate'] == 115200
    assert '&lt;test&gt;' in window.waveform.channel_labels_top[0].text()


def test_invalid_session_metadata_preserves_state(window, tmp_path, monkeypatch):
    previous = window.current_data
    path = tmp_path/'bad.lacapture'
    path.write_text('[]')
    monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', lambda *a: (str(path), ''))
    window._open_capture_file()
    assert window.current_data is previous
    assert window._test_messages


def test_session_tabs_retain_independent_captures(window):
    first = window.current_data
    window._on_add_session_tab()
    assert window.current_data is None
    assert window.tab_sessions.count() == 2
    other = parse_capture(make_packet(status=1))
    window._render_capture_data(other)
    window.tab_sessions.setCurrentIndex(0)
    assert window.current_data is first
    window.tab_sessions.setCurrentIndex(1)
    assert window.current_data is other


def test_uart_channel_configuration_pretrigger_decode_and_bit_centers(window):
    result = parse_capture(make_packet(channel=3))
    window.analyzer['channel'] = 3
    window._render_capture_data(result)
    assert window.current_uart_frames[0]['start_sample'] == 6554
    assert window.waveform.analyzer_channel == 3
    window.waveform.plot_widget.setXRange(0, .0002, padding=0)
    window.waveform._render_uart_bubbles()
    assert window.waveform.bit_dots_item is not None
    spots = window.waveform.bit_dots_item.getData()[0]
    first = window.current_uart_frames[0]['bit_centers'][0]
    assert spots[0] == pytest.approx((first-6554)/1000000)
    # A valid UART frame before trigger must not be discarded.
    raw = bytearray(make_packet())
    raw[7:32775] = np.roll(result['channels'][3], -6000).tobytes()
    from software.protocol import xor_bytes
    raw[-1] = xor_bytes(raw[7:-1])
    window.analyzer['channel'] = 0
    window._render_capture_data(parse_capture(raw))
    assert window.current_uart_frames[0]['start_sample'] == 554


def test_channel_visibility_rows_and_filter_reapplied(window):
    window.waveform.plot_widget.setXRange(0, .0002, padding=0)
    window.edit_search.setText('never matches')
    window._decode_uart()
    assert all(window.table_frames.isRowHidden(i) for i in range(14))
    window.waveform.set_channel_visible(0, False)
    assert window.waveform.row_heights[0] == 0
    assert window.waveform.bit_dots_item is None
    window.waveform.set_channel_visible(0, True)
    assert window.waveform.bit_dots_item is not None


@pytest.mark.parametrize('kind', ['I2C', 'SPI'])
def test_additional_analyzer_gui_paths(window, kind):
    window.analyzer['kind'] = kind
    window._decode_uart()
    assert kind in window.lbl_ana_item.text()


def test_export_vcd_does_not_accumulate_fractional_period_drift(tmp_path):
    channels = [np.arange(601, dtype=np.uint8)%2 for _ in range(8)]
    data = dict(channels=channels, sample_rate=6000000, sample_count=601, trig_offset=0)
    path = tmp_path/'wave.vcd'
    assert export_vcd(data, path)
    timestamps = [int(line[1:]) for line in path.read_text().splitlines() if line.startswith('#')]
    assert timestamps[-1] == 100000  # 600 / 6 MHz = 100 us, not 100200 ns
    assert timestamps[1:4] == [167, 333, 500]
    assert len(timestamps) == 601


@pytest.mark.parametrize('rate', [0, -1, float('nan')])
def test_export_invalid_rate_is_rejected(tmp_path, rate):
    data = dict(channels=[np.ones(2) for _ in range(8)], sample_rate=rate, sample_count=2)
    assert not export_csv(data, tmp_path/'bad.csv')
    assert not export_vcd(data, tmp_path/'bad.vcd')


def test_png_svg_export(window, tmp_path):
    for suffix in ('png', 'svg'):
        path = tmp_path/f'wave.{suffix}'
        assert export_image(window.plot_widget, str(path))
        assert path.stat().st_size > 100


def test_vcd_constant_capture_keeps_end_time(tmp_path):
    path = tmp_path/'constant.vcd'
    data = dict(channels=[np.zeros(100) for _ in range(8)], sample_count=100, sample_rate=1000000)
    assert export_vcd(data, path)
    assert path.read_text().splitlines()[-1] == '#99000'


def test_unknown_analyzer_metadata_rejected(window):
    with pytest.raises(ValueError):
        window._validated_settings({'analyzer': {'unknown_option': 'value'}})


def test_plot_and_channel_labels_stay_aligned_after_resize(window, qapp):
    from software.ui import theme
    window.show()
    for width, height in [(1280, 860), (1500, 960), (1080, 600)]:
        window.resize(width, height)
        qapp.processEvents()
        wave = window.waveform
        assert abs(sum(wave.row_heights) - (wave.plot_widget.height()-theme.AXIS_HEIGHT)) < 10
        assert wave.top_spacer.height() == theme.AXIS_HEIGHT+theme.HUD_HEIGHT
        assert all(wave.channel_frames[i].height() == wave.row_heights[i] for i in range(8))
