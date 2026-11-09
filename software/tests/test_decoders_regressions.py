"""Decoder coverage: real fractional UART timing, I2C repeated starts, all SPI modes."""
import numpy as np
import pytest
from software.decoders.uart_decoder import UARTDecoder
from software.decoders.i2c_decoder import I2CDecoder
from software.decoders.spi_decoder import SPIDecoder
from software.tests.generate_test_data import make_packet
from software.protocol import parse_capture


@pytest.mark.parametrize('rate', [500000, 1000000, 2000000, 3000000, 6000000])
def test_uart_fractional_bit_periods_and_numpy(rate):
    samples = parse_capture(make_packet(rate), rate)['channels'][0]
    text, frames = UARTDecoder(rate).decode(samples, start_idx=6554)
    assert text == 'TEST_LA_2026\r\n'
    assert len(frames) == 14
    for frame in frames:
        for bit, center in enumerate(frame['bit_centers']):
            # Retain A's fractional marker coordinates and rounded sample indices.
            assert center == pytest.approx(frame['start_sample'] + rate/115200*(1.5+bit) - .5)
            assert frame['bit_positions'][bit] == round(frame['start_sample'] + rate/115200*(1.5+bit))
        assert frame['data_end_sample'] - frame['data_start_sample'] == pytest.approx(8*rate/115200)
        assert abs(frame['stop_sample']-frame['start_sample']-rate/115200*10) <= 1


def test_uart_end_of_buffer_and_empty_ranges():
    spb = 10
    bits = [0] + [(0x55 >> i) & 1 for i in range(8)] + [1]
    samples = np.array([1]*10+[b for bit in bits for b in [bit]*spb], dtype=np.uint8)
    text, frames = UARTDecoder(1000000, 100000).decode(samples, -100)
    assert text == 'U' and len(frames) == 1
    assert UARTDecoder().decode(np.array([], dtype=np.uint8)) == ('', [])
    assert UARTDecoder(10000).decode(samples)[1] == []
    assert UARTDecoder().decode(samples, 40, 10) == ('', [])


def test_i2c_repeated_start_read_nack_and_numpy():
    scl, sda = [1]*4, [1]*4
    def hold(clock, data, n=4):
        scl.extend([clock]*n)
        sda.extend([data]*n)
    def start():
        hold(1, 1)
        hold(1, 0)
    def byte(value, ack):
        for bit in [(value >> i)&1 for i in range(7,-1,-1)] + [ack]:
            hold(0, bit)
            hold(1, bit)
        hold(0, ack)
    start()
    byte(0x78, 0)  # address 0x3C write, ACK
    byte(0xAA, 0)
    start()
    byte(0x79, 0)  # address 0x3C read, ACK
    byte(0x55, 1)  # final data NACK
    hold(0, 0)
    hold(1, 0)
    hold(1, 1)
    text, frames = I2CDecoder().decode(np.array(scl), np.array(sda), start_idx=-2)
    assert [f['type'] for f in frames] == ['START','ADDRESS','DATA','REPEATED_START','ADDRESS','DATA','STOP']
    assert frames[1]['val'] == 0x3C and frames[4]['rw'] == 'R'
    assert frames[5]['val'] == 0x55 and not frames[5]['ack']


def spi_signal(mode, bit_order, active):
    cpol, cpha = mode//2, mode%2
    cs_level = 0 if active == 'LOW' else 1
    sck, mosi, miso, cs = [cpol]*4, [0]*4, [0]*4, [1-cs_level]*4
    def hold(clock, m, s, selected, n=3):
        sck.extend([clock]*n); mosi.extend([m]*n)
        miso.extend([s]*n); cs.extend([selected]*n)
    hold(cpol, 0, 0, cs_level)
    for i in range(8):
        shift = 7-i if bit_order == 'MSB' else i
        m, s = (0x9F>>shift)&1, (0x55>>shift)&1
        # Data is stable on both edges; CPHA selects the edge to sample.
        hold(cpol, m, s, cs_level)
        hold(1-cpol, m, s, cs_level)
        hold(cpol, m, s, cs_level)
    hold(cpol, 0, 0, 1-cs_level)
    return tuple(np.array(a) for a in (sck, mosi, miso, cs))


@pytest.mark.parametrize('mode', range(4))
@pytest.mark.parametrize('order', ['MSB', 'LSB'])
@pytest.mark.parametrize('active', ['LOW', 'HIGH'])
def test_spi_all_modes_orders_cs_numpy(mode, order, active):
    _, frames = SPIDecoder(cpol=mode//2, cpha=mode%2, bit_order=order, cs_active=active).decode(
        *spi_signal(mode, order, active), start_idx=-5)
    assert len(frames) == 1
    assert frames[0]['mosi_val'] == 0x9F and frames[0]['miso_val'] == 0x55


def test_spi_cs_deasserted_at_sample_edge_is_not_sampled():
    clock = [0, 1]*8
    bits = [1]*16
    cs = [0]*15 + [1]  # eighth rising edge is outside the selected transaction
    assert SPIDecoder().decode(clock, bits, bits, cs)[1] == []
    assert SPIDecoder().decode(np.array([]))[1] == []
    assert SPIDecoder().decode([0, 1], np.array([]))[1] == []


@pytest.mark.parametrize('decoder,args', [
    (I2CDecoder(0), ([1, 0], [1, 0])),
    (SPIDecoder(0), ([0, 1],)),
    (UARTDecoder(0), ([1, 0],)),
])
def test_invalid_decoder_rate_returns_no_frames(decoder, args):
    assert decoder.decode(*args)[1] == []
