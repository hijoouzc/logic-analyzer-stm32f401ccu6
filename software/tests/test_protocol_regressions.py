"""Regression tests for stream framing, file validation and concurrency boundaries."""
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from software.protocol import command, parse_capture, valid_data_header
from software.gui.logic_client import LogicAnalyzerClient
from software.tests.generate_test_data import make_packet
from software.tests.mock_device import control


class FakeSerial:
    is_open = True
    timeout = .05

    def __init__(self, response=b'', chunk=4096, on_read=None):
        self.response = response
        self.buf = bytearray()
        self.chunk = chunk
        self.writes = []
        self.on_read = on_read

    def reset_input_buffer(self):
        self.buf.clear()

    def write(self, data):
        self.writes.append(bytes(data))
        if data[1] == 1:
            self.buf.extend(self.response)
        elif data[1] == 3:
            self.buf.extend(self.response or control(4, (1, 0, 0)))
        elif data[1] == 2:
            self.buf.extend(self.response or control(5))
        return len(data)

    def read(self, n):
        if self.on_read:
            self.on_read(self)
        data = bytes(self.buf[:min(n, self.chunk)])
        del self.buf[:len(data)]
        return data

    def close(self):
        self.is_open = False


def client_for(monkeypatch, response, chunk=4096):
    client = LogicAnalyzerClient()
    client.ser = FakeSerial(response, chunk)
    # Advance a private test clock on each read loop, no real timeout sleeps.
    now = [0.]
    def clock():
        now[0] += .0001
        return now[0]
    monkeypatch.setattr('software.gui.logic_client.time', SimpleNamespace(monotonic=clock))
    return client


@pytest.mark.parametrize('chunk', [1, 2, 7, 64, 512, 4096])
@pytest.mark.parametrize('status', [0, 1, 2])
def test_fragmented_data_frames(monkeypatch, chunk, status):
    client = client_for(monkeypatch, make_packet(status=status), chunk)
    result = client.start_capture()
    assert result['success'], result
    assert result['status'] == status
    assert client.ser.writes == [command(1, 3, 0)]
    assert result['sample_count'] == 32768


def test_resynchronizes_noise_false_header_and_stale_control(monkeypatch):
    data = (b'\xff\x5a' + b'\x5a\xa5\x90\0\0\0\0' + b'\x5a\xa5\0\0\0\0\0' +
            control(4, (1, 0, 0)) + control(0xE0, (3, 0, 0)) + make_packet())
    client = client_for(monkeypatch, data, 2)
    assert client.start_capture()['success']


@pytest.mark.parametrize('code', [0xE0, 0xE1, 0xE2, 0xE3])
def test_nak_echo_correlates_with_start(monkeypatch, code):
    client = client_for(monkeypatch, control(code, (1, 3, 0)))
    result = client.start_capture()
    assert not result['success']
    assert client.RSP_CODES[code] in result['error']


@pytest.mark.parametrize('index,value', [(0, 0), (1, 0), (2, 3), (3, 0), (5, 0xFF), (-1, 7)])
def test_rejects_bad_capture_fields(index, value):
    packet = bytearray(make_packet())
    packet[index] = value
    with pytest.raises(ValueError):
        parse_capture(packet)


@pytest.mark.parametrize('cut', [0, 6, 7, 32775, 32777])
def test_rejects_wrong_size(cut):
    packet = make_packet()
    with pytest.raises(ValueError):
        parse_capture((packet+b'\0')[:cut])


def test_serial_checksum_failure_never_returns_channels(monkeypatch):
    packet = bytearray(make_packet())
    packet[-1] ^= 1
    result = client_for(monkeypatch, packet).start_capture()
    assert not result['success'] and 'channels' not in result


def test_short_transfer_times_out(monkeypatch):
    client = client_for(monkeypatch, make_packet()[:200])
    assert not client.start_capture()['success']


def test_abort_requires_valid_checksum_and_ack(monkeypatch):
    bad = bytearray(control(5))
    bad[-1] ^= 1
    client = client_for(monkeypatch, bytes(bad))
    ok, message = client.abort()
    assert not ok
    assert message


def test_ping_noise_bad_checksum_then_valid(monkeypatch):
    bad = bytearray(control(4, (1, 0, 0)))
    bad[-1] ^= 1
    client = client_for(monkeypatch, b'junk' + bytes(bad) + control(4, (1, 0, 0)), 1)
    assert client.ping() == (True, 'v1.0.0')


def test_abort_flag_is_serviced_by_capture_owner(monkeypatch):
    client = client_for(monkeypatch, b'')
    triggered = [False]
    def on_read(serial):
        if not triggered[0]:
            triggered[0] = True
            client.request_abort()
    client.ser.on_read = on_read
    # Empty START, then fake device emits ACK on ABORT.
    result = client.start_capture()
    assert result.get('aborted')
    assert client.ser.writes == [command(1, 3, 0), command(2)]


def test_no_commands_or_disconnect_during_payload(monkeypatch):
    client = client_for(monkeypatch, make_packet(), 64)
    observed = []
    def phase(_):
        observed.append(client.ping()[0])
        observed.append(client.abort()[0])
        observed.append(client.connect('OFFLINE_MOCK')[0])
        observed.append(client.disconnect())
        client.request_abort()
    result = client.start_capture(phase_callback=phase)
    assert result['success']
    assert observed == [False]*4
    assert client.ser.writes == [command(1, 3, 0)]


@pytest.mark.parametrize('params', [(9, 0, 0), (-1, 0, 0), (3, 8, 0), (3, 0, 3), (3.5, 0, 0)])
def test_invalid_configuration_is_rejected_before_serial_io(params):
    client = LogicAnalyzerClient()
    assert not client.start_capture(*params)['success']


def test_offline_fixture_keeps_real_sample_rate():
    client = LogicAnalyzerClient()
    assert client.connect('OFFLINE_MOCK')[0]
    result = client.start_capture(rate_idx=0)
    assert result['success'] and result['sample_rate'] == 1000000
    assert result['offline']


def test_offline_invalid_header_and_missing_file(tmp_path):
    client = LogicAnalyzerClient()
    missing = client.load_offline_file(tmp_path/'missing.bin')
    assert not missing['success']
    path = tmp_path/'bad.bin'
    data = bytearray(make_packet())
    data[5] = 0
    data[6] = 0
    path.write_bytes(data)
    assert not client.load_offline_file(path)['success']


@pytest.mark.parametrize('rate', [0, -1, float('nan'), float('inf')])
def test_nonpositive_or_nonfinite_rate(rate):
    with pytest.raises(ValueError):
        parse_capture(make_packet(), rate)
