"""Boundaries between A's interactive GUI and B's capture/session workflows."""
import pytest
from software.tests.generate_test_data import make_packet
from software.protocol import parse_capture


def test_session_settings_survive_closing_and_recreating_tabs(window):
    first = window.current_data
    window.analyzer['channel'] = 3
    window.waveform.set_channel_name(3, 'First UART')
    window.waveform.set_channel_color(3, '#00aaff')
    window._on_add_session_tab()
    window.analyzer['channel'] = 5
    second = parse_capture(make_packet(channel=5))
    window._render_capture_data(second)
    window.waveform.set_channel_name(5, 'Second UART')
    window.tab_sessions.setCurrentIndex(0)
    assert window.current_data is first
    assert window.analyzer['channel'] == 3
    assert window.waveform.channel_names[3] == 'First UART'
    assert window.waveform.channel_colors[3] == '#00aaff'
    window._on_close_session_tab(0)
    assert window.current_data is second
    assert window.analyzer['channel'] == 5
    assert window.waveform.channel_names[5] == 'Second UART'
    window._on_add_session_tab()
    assert window.current_data is None
    window.tab_sessions.setCurrentIndex(0)
    assert window.current_data is second


def test_cleared_capture_does_not_reappear_on_session_switch(window):
    window._on_clear_capture_data()
    window._on_add_session_tab()
    window.tab_sessions.setCurrentIndex(0)
    assert window.current_data is None
    assert not window.current_uart_frames
    assert not window.waveform._uart_frames
    assert window.table_frames.rowCount() == 0


def test_configured_uart_keeps_payload_bubbles_and_ctrl_click_navigation(window):
    window.analyzer['channel'] = 3
    window._render_capture_data(parse_capture(make_packet(channel=3)))
    window.waveform.plot_widget.setXRange(0, .0002, padding=0)
    window.waveform._render_uart_bubbles()
    frame = window.current_uart_frames[0]
    bubble = window.waveform.decode_items[0]
    assert bubble.t_start == pytest.approx((frame['data_start_sample'] - 6554) / 1000000)
    assert bubble.t_stop == pytest.approx((frame['data_end_sample'] - 6554) / 1000000)
    assert bubble.y_top >= sum(window.waveform.row_heights[:3])
    assert not window.waveform.show_hardware_sample_points
    bubble.on_ctrl_clicked()
    assert window.table_frames.selectionModel().selectedRows()[0].row() == 0


@pytest.mark.parametrize('kind,channel', [('I2C', 6), ('SPI', 7)])
def test_protocol_decorations_follow_configured_channel_on_resize(window, qapp, kind, channel):
    window.analyzer['kind'] = kind
    window.analyzer['sda' if kind == 'I2C' else 'mosi'] = channel
    window._decode_uart()
    assert window.waveform.analyzer_channel == channel
    assert window.current_analyzer == kind.lower()
    window.show()
    window.resize(1500, 960)
    qapp.processEvents()
    assert not window.waveform._uart_frames
    assert window.waveform._protocol_decoration[0] == kind.lower()


def test_all_hidden_channels_remain_safe_and_can_be_restored(window):
    for ch in range(8):
        window.waveform.set_channel_visible(ch, False)
    assert window.waveform.row_heights == [0] * 8
    assert not window.waveform.bit_dots_item
    window.waveform.set_channel_visible(0, True)
    assert window.waveform.row_heights[0] > 0


def test_manual_mock_url_survives_port_refresh(window):
    window.chk_mock.setChecked(False)
    window.combo_ports.setEditText('socket://127.0.0.1:8765')
    window._refresh_ports(auto_connect=False)
    assert window._selected_port() == 'socket://127.0.0.1:8765'
