"""Generate protocol-correct UART fixtures without rounding every bit to 9 samples."""
from pathlib import Path
import numpy as np

SAMPLE_COUNT = 32768
TRIGGER_OFFSET = 6554


def make_packet(sample_rate=1000000, status=0, channel=0):
    if not 0 <= channel <= 7 or sample_rate <= 0 or status not in (0, 1, 2):
        raise ValueError('Invalid mock capture configuration')
    spb = sample_rate / 115200
    payload = np.full(SAMPLE_COUNT, 1 << channel, dtype=np.uint8)
    bits = []
    for char in b'TEST_LA_2026\r\n':
        bits.extend([0] + [(char >> k) & 1 for k in range(8)] + [1])
    for bit_idx, bit in enumerate(bits):
        begin = TRIGGER_OFFSET + round(bit_idx * spb)
        end = min(TRIGGER_OFFSET + round((bit_idx + 1) * spb), SAMPLE_COUNT)
        if begin >= SAMPLE_COUNT:
            break
        payload[begin:end] = bit << channel
    footer = int(np.bitwise_xor.reduce(payload))
    header = bytes((0x5A, 0xA5, status, 0x9A, 0x19, 0, 0x80))
    return header + payload.tobytes() + bytes((footer,))


def create_sample_bin(filename=None):
    filename = Path(filename) if filename is not None else Path(__file__).with_name('sample_data_1mhz.bin')
    packet = make_packet()
    filename.write_bytes(packet)
    print(f'Created {filename.name}: {len(packet)} bytes, 1 MHz / UART 115200')


if __name__ == '__main__':
    create_sample_bin()
