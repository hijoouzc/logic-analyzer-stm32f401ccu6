"""Checks available without Qt/NumPy/pyserial; does not replace pytest or HIL.

Run from the repository root: python software/tests/verify_integration_stdlib.py
"""
import ast
from functools import reduce
from operator import xor
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from software.decoders.uart_decoder import UARTDecoder
from software.decoders.i2c_decoder import I2CDecoder
from software.decoders.spi_decoder import SPIDecoder


class IntegrationChecks(unittest.TestCase):
    def test_python_syntax_and_internal_import_paths(self):
        for path in (ROOT / 'software').rglob('*.py'):
            if any(part in ('.venv', 'venv', '__pycache__') for part in path.parts):
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                tree = ast.parse(path.read_bytes(), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('software.'):
                        target = ROOT.joinpath(*node.module.split('.'))
                        self.assertTrue(target.is_dir() or target.with_suffix('.py').is_file(), node.module)
                    if isinstance(node, (ast.Module, ast.ClassDef)):
                        names = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
                        self.assertEqual(len(names), len(set(names)), (path, names))
                    if isinstance(node, ast.Dict):
                        keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
                        self.assertEqual(len(keys), len(set(keys)), (path, keys))

    def test_fixture_wire_format(self):
        raw = (ROOT / 'software/tests/sample_data_1mhz.bin').read_bytes()
        self.assertEqual(len(raw), 32776)
        self.assertEqual(raw[:3], bytes.fromhex('5a a5 00'))
        self.assertEqual(struct.unpack_from('<HH', raw, 3), (6554, 32768))
        self.assertEqual(reduce(xor, raw[7:-1], 0), raw[-1])
        payload = raw[7:-1]
        self.assertEqual(payload[:6554], bytes([1]) * 6554)
        self.assertEqual(payload[6554], 0)
        self.assertTrue(all(v in (0, 1) for v in payload))

    def test_fixture_uart_decode_and_combined_metadata(self):
        raw = (ROOT / 'software/tests/sample_data_1mhz.bin').read_bytes()
        text, frames = UARTDecoder().decode(list(raw[7:-1]), start_idx=6554)
        self.assertEqual(text, 'TEST_LA_2026\r\n')
        self.assertEqual(len(frames), 14)
        for frame in frames:
            self.assertEqual(len(frame['bit_positions']), 8)
            self.assertEqual(len(frame['bit_centers']), 8)
            self.assertAlmostEqual(frame['data_end_sample'] - frame['data_start_sample'], 8e6 / 115200)
            self.assertLessEqual(abs(frame['stop_sample'] - frame['start_sample'] - 10e6 / 115200), 1)

    def test_fractional_uart_rates(self):
        bits = []
        for value in b'TEST_LA_2026\r\n':
            bits.extend([0] + [(value >> bit) & 1 for bit in range(8)] + [1])
        for rate in (500000, 1000000, 2000000, 3000000, 6000000):
            with self.subTest(rate=rate):
                samples = [1] * 32768
                for bit, level in enumerate(bits):
                    begin = 6554 + round(bit * rate / 115200)
                    end = 6554 + round((bit + 1) * rate / 115200)
                    samples[begin:end] = [level] * (end - begin)
                text, frames = UARTDecoder(rate).decode(samples, start_idx=6554)
                self.assertEqual(text, 'TEST_LA_2026\r\n')
                self.assertEqual(len(frames), 14)

    def test_uart_boundary_and_invalid_input(self):
        bits = [0] + [(0x55 >> bit) & 1 for bit in range(8)] + [1]
        samples = [1] * 10 + [level for bit in bits for level in [bit] * 10]
        self.assertEqual(UARTDecoder(1000000, 100000).decode(samples, -100)[0], 'U')
        self.assertEqual(UARTDecoder().decode(samples, 40, 10), ('', []))
        for rate in (0, -1, float('inf'), float('nan')):
            self.assertEqual(UARTDecoder(rate).decode(samples)[1], [])
        self.assertEqual(UARTDecoder(10000).decode(samples)[1], [])

    def test_i2c_repeated_start_read_nack(self):
        scl, sda = [1] * 4, [1] * 4

        def hold(clock, data):
            scl.extend([clock] * 4)
            sda.extend([data] * 4)

        def start():
            hold(1, 1)
            hold(1, 0)

        def byte(value, ack):
            for bit in [(value >> i) & 1 for i in range(7, -1, -1)] + [ack]:
                hold(0, bit)
                hold(1, bit)
            hold(0, ack)

        start()
        byte(0x78, 0)
        byte(0xAA, 0)
        start()
        byte(0x79, 0)
        byte(0x55, 1)
        hold(0, 0)
        hold(1, 0)
        hold(1, 1)
        _, frames = I2CDecoder().decode(scl, sda, start_idx=-2)
        self.assertEqual([f['type'] for f in frames], ['START', 'ADDRESS', 'DATA', 'REPEATED_START', 'ADDRESS', 'DATA', 'STOP'])
        self.assertEqual(frames[1]['val'], 0x3C)
        self.assertEqual(frames[4]['rw'], 'R')
        self.assertEqual(frames[5]['val'], 0x55)
        self.assertFalse(frames[5]['ack'])
        self.assertTrue(all(f['stop_sample'] > f['start_sample'] for f in frames))

    def test_spi_modes_bit_orders_and_chip_select(self):
        for mode in range(4):
            for order in ('MSB', 'LSB'):
                for active in ('LOW', 'HIGH'):
                    with self.subTest(mode=mode, order=order, active=active):
                        cpol, cpha = mode // 2, mode % 2
                        selected = 0 if active == 'LOW' else 1
                        sck, mosi, miso, cs = [cpol] * 4, [0] * 4, [0] * 4, [1 - selected] * 4

                        def hold(clock, m, s, enabled):
                            sck.extend([clock] * 3)
                            mosi.extend([m] * 3)
                            miso.extend([s] * 3)
                            cs.extend([enabled] * 3)

                        hold(cpol, 0, 0, selected)
                        for bit in range(8):
                            shift = 7 - bit if order == 'MSB' else bit
                            m, s = (0x9F >> shift) & 1, (0x55 >> shift) & 1
                            hold(cpol, m, s, selected)
                            hold(1 - cpol, m, s, selected)
                            hold(cpol, m, s, selected)
                        hold(cpol, 0, 0, 1 - selected)
                        _, frames = SPIDecoder(cpol=cpol, cpha=cpha, bit_order=order, cs_active=active).decode(sck, mosi, miso, cs, start_idx=-5)
                        self.assertEqual(len(frames), 1)
                        self.assertEqual(frames[0]['mosi_val'], 0x9F)
                        self.assertEqual(frames[0]['miso_val'], 0x55)
        self.assertEqual(SPIDecoder().decode([0, 1] * 8, [1] * 16, [1] * 16, [0] * 15 + [1])[1], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
