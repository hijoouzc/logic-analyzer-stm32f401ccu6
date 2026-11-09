"""Wire format shared by serial, offline files and tests (spec/protocol.md)."""
import math
import struct
import numpy as np

SYNC = b'\x5a\xa5'
SAMPLE_COUNT = 32768
TRIGGER_OFFSET = 6554
FRAME_SIZE = SAMPLE_COUNT + 8
RATES = (6000000, 3000000, 2000000, 1000000, 500000, 200000, 100000, 50000, 10000)
CONTROL_CODES = (0x04, 0x05, 0xE0, 0xE1, 0xE2, 0xE3)
STATUS_NAMES = {0: 'Triggered (STATUS_TRIGGER_OK)', 1: 'Free-run (STATUS_FREERUN_OK)', 2: 'Timeout (STATUS_TIMEOUT)'}


def xor_bytes(data):
    value = 0
    for byte in data:
        value ^= int(byte)
    return value


def command(cmd, rate=0, trigger=0):
    body = bytes((0xA5, cmd, rate, trigger))
    return body + bytes((xor_bytes(body),))


def valid_data_header(header):
    return (len(header) >= 7 and header[:2] == SYNC and header[2] in STATUS_NAMES
            and struct.unpack_from('<HH', header, 3) == (TRIGGER_OFFSET, SAMPLE_COUNT))


def parse_capture(data, sample_rate=1000000, elapsed_s=0):
    if not math.isfinite(float(sample_rate)) or float(sample_rate) <= 0:
        raise ValueError('Tần số lấy mẫu phải là số hữu hạn lớn hơn 0.')
    if len(data) != FRAME_SIZE:
        raise ValueError(f'Sai kích thước khung: {len(data)} != {FRAME_SIZE} bytes.')
    if not valid_data_header(data[:7]):
        raise ValueError('Header không hợp lệ: cần Magic 5A A5, Status 00..02, trig_offset 6554, sample_count 32768.')
    if xor_bytes(data[7:-1]) != data[-1]:
        raise ValueError('Sai Footer XOR checksum của payload.')
    payload = np.frombuffer(bytes(data[7:-1]), dtype=np.uint8)
    return dict(success=True, error='', status=data[2], status_name=STATUS_NAMES[data[2]],
                trig_offset=TRIGGER_OFFSET, sample_count=SAMPLE_COUNT, sample_rate=float(sample_rate),
                payload=payload, channels=[((payload >> k) & 1).astype(np.uint8) for k in range(8)],
                elapsed_s=elapsed_s, checksum_ok=True)


def capture_bytes(data):
    payload = bytes(data['payload'])
    raw = SYNC + struct.pack('<BHH', int(data['status']), int(data['trig_offset']), int(data['sample_count']))
    raw += payload + bytes((xor_bytes(payload),))
    parse_capture(raw, data['sample_rate'])
    return raw
