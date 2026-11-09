"""Single-owner USB-CDC client; only the capture worker reads/writes serial."""
import os
import threading
import time
import serial
import serial.tools.list_ports
import numpy as np
from software.protocol import (SYNC, SAMPLE_COUNT, FRAME_SIZE, RATES, CONTROL_CODES,
                               STATUS_NAMES, command, parse_capture, valid_data_header, xor_bytes)


class LogicAnalyzerClient:
    RATE_TABLE = [dict(idx=i, freq=f, label=f'{f / 1e6:g} MHz' if f >= 1000000 else f'{f / 1e3:g} kHz')
                  for i, f in enumerate(RATES)]
    TRIG_MODES = [dict(mode=i, name=n) for i, n in enumerate(('Free-run', 'Rising', 'Falling'))]
    RSP_CODES = {0x04: 'RSP_PONG', 0x05: 'RSP_ABORTED', 0xE0: 'ERR_CHECKSUM',
                 0xE1: 'ERR_INVALID_RATE', 0xE2: 'ERR_INVALID_TRIG', 0xE3: 'ERR_BUSY'}
    STATUS_NAMES = STATUS_NAMES

    def __init__(self):
        self.ser = None
        self.port_name = ''
        self.baudrate = 115200
        self.is_offline_mock = False
        self._lock = threading.Lock()
        self._abort_requested = threading.Event()
        self._receiving = threading.Event()
        self._rx = bytearray()

    @property
    def is_connected(self):
        return self.is_offline_mock or (self.ser is not None and self.ser.is_open)

    @property
    def receiving_payload(self):
        return self._receiving.is_set()

    @staticmethod
    def list_ports():
        return [(p.device, f'{p.device} - {p.description}') for p in serial.tools.list_ports.comports()] + [
            ('OFFLINE_MOCK', 'Offline Mock (1 MHz, UART 115200)')]

    def connect(self, port, baudrate=115200, timeout=0.05):
        if not self._lock.acquire(blocking=False):
            return False, 'Đang giao tiếp; chưa thể thay đổi kết nối.'
        try:
            self._disconnect()
            self._abort_requested.clear()
            if port == 'OFFLINE_MOCK':
                self.is_offline_mock = True
            else:
                self.ser = serial.serial_for_url(port, baudrate=baudrate, timeout=min(timeout, 0.05), write_timeout=0.5)
                self.ser.reset_input_buffer()
            self.port_name, self.baudrate = port, baudrate
            return True, f'Đã kết nối {port}'
        except (OSError, serial.SerialException, ValueError) as e:
            self._disconnect()
            return False, f'Không thể mở cổng {port}: {e}'
        finally:
            self._lock.release()

    def _disconnect(self):
        if self.ser:
            try:
                self.ser.close()
            except (OSError, serial.SerialException):
                pass
        self.ser = None
        self.is_offline_mock = False
        self.port_name = ''
        self._rx.clear()

    def disconnect(self):
        if not self._lock.acquire(blocking=False):
            return False
        try:
            self._disconnect()
            return True
        finally:
            self._lock.release()

    def request_abort(self):
        """Set a flag only: no concurrent serial reads/writes from the UI."""
        if not self.receiving_payload:
            self._abort_requested.set()

    def _write(self, packet):
        if self.ser.write(packet) != len(packet):
            raise serial.SerialException('Không gửi đủ 5 byte lệnh.')

    def _prepare(self):
        if not self.is_connected:
            raise serial.SerialException('Chưa kết nối cổng serial!')
        self._rx.clear()
        self._receiving.clear()
        if self.ser:
            self.ser.reset_input_buffer()

    def _read_exact(self, count, timeout_s=2.0):
        """Compatibility helper for manual HIL scripts, outside capture only."""
        data = bytearray()
        deadline = time.monotonic() + timeout_s
        while self.ser and len(data) < count and time.monotonic() < deadline:
            data.extend(self.ser.read(min(4096, count-len(data))))
        return data

    def _read_frame(self, deadline, allow_data=False, progress_callback=None, phase_callback=None,
                    cancel_capture=False):
        abort_sent = False
        data_header = False
        while time.monotonic() < deadline:
            if not data_header:
                start = self._rx.find(SYNC)
                if start < 0:
                    self._rx[:] = self._rx[-1:] if self._rx.endswith(SYNC[:1]) else b''
                else:
                    del self._rx[:start]
                    if len(self._rx) >= 7:
                        code = self._rx[2]
                        if code in CONTROL_CODES and xor_bytes(self._rx[:7]) == 0:
                            packet = bytes(self._rx[:7])
                            del self._rx[:7]
                            return packet, abort_sent
                        if allow_data and valid_data_header(self._rx[:7]):
                            data_header = True
                            self._receiving.set()
                            if phase_callback:
                                phase_callback('receiving')
                        else:
                            del self._rx[0]
                            continue
            if data_header:
                if progress_callback:
                    progress_callback(min(max(0, len(self._rx)-7), SAMPLE_COUNT+1), SAMPLE_COUNT+1)
                if len(self._rx) >= FRAME_SIZE:
                    packet = bytes(self._rx[:FRAME_SIZE])
                    del self._rx[:FRAME_SIZE]
                    return packet, abort_sent
            # Inspect a buffered header before honoring Abort; once data is
            # recognized, no command may be interleaved with its payload.
            if cancel_capture and self._abort_requested.is_set() and not abort_sent and not data_header:
                self._write(command(2))
                abort_sent = True
            size = min(4096, FRAME_SIZE-len(self._rx)) if data_header else 7
            self._rx.extend(self.ser.read(size))
        raise TimeoutError('Hết thời gian chờ phản hồi hợp lệ hoặc truyền thiếu dữ liệu/checksum sai.')

    def _control(self, cmd_id, expected):
        if not self._lock.acquire(blocking=False):
            return False, 'Đang capture/truyền dữ liệu; lệnh bị khóa.'
        try:
            self._prepare()
            if self.is_offline_mock:
                return True, 'v1.0.0-offline' if cmd_id == 3 else 'Capture aborted (offline)'
            self._write(command(cmd_id))
            deadline = time.monotonic() + (2 if cmd_id == 3 else 1.5)
            while True:
                packet, _ = self._read_frame(deadline)
                if packet[2] == expected:
                    if cmd_id == 2 and packet[3:6] != b'\0\0\0':
                        continue
                    return True, (f'v{packet[3]}.{packet[4]}.{packet[5]}' if cmd_id == 3 else 'Capture aborted')
                if packet[2] >= 0xE0 and packet[3:6] == bytes((cmd_id, 0, 0)):
                    return False, self.RSP_CODES[packet[2]]
        except (OSError, ValueError, serial.SerialException, TimeoutError) as e:
            return False, str(e)
        finally:
            self._lock.release()

    def ping(self):
        return self._control(3, 4)

    def send_ping(self):
        return self.ping()

    def abort(self):
        return self._control(2, 5)

    def send_abort(self):
        return self.abort()[0]

    def start_capture(self, rate_idx=3, trig_ch=0, trig_mode=0, progress_callback=None, phase_callback=None):
        values = (rate_idx, trig_ch, trig_mode)
        if any(not isinstance(v, (int, np.integer)) for v in values) or not (
                0 <= rate_idx < 9 and 0 <= trig_ch < 8 and 0 <= trig_mode < 3):
            return dict(success=False, error='RATE_IDX/Trigger Channel/Trigger Mode không hợp lệ.')
        if not self._lock.acquire(blocking=False):
            return dict(success=False, error='Đang capture/truyền dữ liệu; lệnh bị khóa.')
        try:
            self._prepare()
            started = time.monotonic()
            if self.is_offline_mock:
                # Fixture is 1 MHz, regardless of the selected real-device rate.
                path = os.path.join(os.path.dirname(__file__), '..', 'tests', 'sample_data_1mhz.bin')
                result = self.load_offline_file(path)
                result['offline'] = True
                return result
            trig_cfg = (trig_ch << 4) | trig_mode
            self._write(command(1, rate_idx, trig_cfg))
            deadline = started + 42598.0 / RATES[rate_idx] + 3.5
            abort_sent = False
            while True:
                packet, sent = self._read_frame(deadline, True, progress_callback, phase_callback, not abort_sent)
                abort_sent = abort_sent or sent
                if len(packet) == FRAME_SIZE:
                    return parse_capture(packet, RATES[rate_idx], time.monotonic()-started)
                code = packet[2]
                if code == 5 and abort_sent and packet[3:6] == b'\0\0\0':
                    return dict(success=False, aborted=True, error='Capture aborted')
                echoes = [bytes((1, rate_idx, trig_cfg))]
                if abort_sent:
                    echoes.append(bytes((2, 0, 0)))
                # Ignore delayed PONG or NAK for a different command.
                if code >= 0xE0 and packet[3:6] in echoes:
                    return dict(success=False, error=self.RSP_CODES[code])
        except (OSError, ValueError, serial.SerialException, TimeoutError) as e:
            return dict(success=False, error=str(e))
        finally:
            self._receiving.clear()
            self._abort_requested.clear()
            self._lock.release()

    def send_start(self, rate_idx=3, trig_ch=0, trig_mode=0):
        r = self.start_capture(rate_idx, trig_ch, trig_mode)
        if not r.get('success'):
            return 0xFF, 0, 0, np.array([], dtype=np.uint8), False
        return r['status'], r['trig_offset'], r['sample_count'], r['payload'], r['checksum_ok']

    def load_offline_file(self, filepath, sample_rate=1000000):
        try:
            with open(filepath, 'rb') as f:
                raw = f.read(FRAME_SIZE+1)
            return parse_capture(raw, sample_rate)
        except (OSError, ValueError) as e:
            return dict(success=False, error=f'Lỗi đọc tệp offline: {e}')
