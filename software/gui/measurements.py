#!/usr/bin/env python3
"""software/gui/measurements.py
Module đo đạc và thống kê tự động tín hiệu số (Automated Channel Measurements)
cho các kênh đầu vào (CH0..CH7):
- Tần số (Frequency): f_mean, f_min, f_max
- Chu kỳ (Period): T_mean, T_min, T_max
- Độ rộng xung dương (Positive Pulse Width: t_high)
- Độ rộng xung âm (Negative Pulse Width: t_low)
- Hệ số xung (Duty Cycle %): t_high / T * 100%
- Thống kê chuyển mức logic (Transitions): Số sườn lên (Rising), sườn xuống (Falling)
"""

from typing import Dict, Any, List, Union
import numpy as np


def measure_channel_signal(samples: Union[np.ndarray, List[int]], sample_rate: float) -> Dict[str, Any]:
    """
    Phân tích và tính toán các thông số đo đạc tự động từ mảng mẫu tín hiệu số 32KB.
    
    Args:
        samples: Mảng giá trị logic (0 hoặc 1), độ dài thường là 32768.
        sample_rate: Tần số lấy mẫu (Hz), ví dụ 1_000_000.0 (1 MHz) hoặc 6_000_000.0 (6 MHz).
        
    Returns:
        Dict chứa các thông số đo đạc: state, freq, period, duty_cycle, t_high, t_low, transitions...
    """
    if len(samples) == 0 or sample_rate <= 0:
        return {
            "state": "NO_DATA",
            "num_transitions": 0,
            "num_rising": 0,
            "num_falling": 0,
            "freq_mean": 0.0,
            "period_mean": 0.0,
            "duty_mean": 0.0,
            "thigh_mean": 0.0,
            "thigh_min": 0.0,
            "tlow_mean": 0.0,
            "tlow_min": 0.0,
        }

    arr = np.asarray(samples, dtype=np.uint8)
    diff = np.diff(arr.astype(np.int8))
    rising = np.where(diff == 1)[0] + 1
    falling = np.where(diff == -1)[0] + 1

    num_rising = len(rising)
    num_falling = len(falling)
    num_transitions = num_rising + num_falling

    # Trường hợp 1: Tín hiệu đứng yên không chuyển mức
    if num_transitions == 0:
        val = int(arr[0])
        return {
            "state": "CONSTANT_HIGH" if val == 1 else "CONSTANT_LOW",
            "num_transitions": 0,
            "num_rising": 0,
            "num_falling": 0,
            "freq_mean": 0.0,
            "period_mean": 0.0,
            "duty_mean": 100.0 if val == 1 else 0.0,
            "thigh_mean": 0.0,
            "thigh_min": 0.0,
            "tlow_mean": 0.0,
            "tlow_min": 0.0,
        }

    # 1. Tính chu kỳ Period (T) từ các sườn xung liên tiếp
    periods = []
    if num_rising >= 2:
        periods.extend(np.diff(rising) / sample_rate)
    elif num_falling >= 2:
        periods.extend(np.diff(falling) / sample_rate)

    if periods:
        p_mean = float(np.mean(periods))
        p_min = float(np.min(periods))
        p_max = float(np.max(periods))
        freq_mean = (1.0 / p_mean) if p_mean > 0 else 0.0
    else:
        p_mean = p_min = p_max = 0.0
        freq_mean = 0.0

    # 2. Tính độ rộng xung dương (t_high)
    high_widths = []
    for r in rising:
        f_after = falling[falling > r]
        if len(f_after) > 0:
            high_widths.append((f_after[0] - r) / sample_rate)

    # 3. Tính độ rộng xung âm (t_low)
    low_widths = []
    for f in falling:
        r_after = rising[rising > f]
        if len(r_after) > 0:
            low_widths.append((r_after[0] - f) / sample_rate)

    thigh_mean = float(np.mean(high_widths)) if high_widths else 0.0
    thigh_min = float(np.min(high_widths)) if high_widths else 0.0

    tlow_mean = float(np.mean(low_widths)) if low_widths else 0.0
    tlow_min = float(np.min(low_widths)) if low_widths else 0.0

    # 4. Tính Duty Cycle (%)
    if p_mean > 0 and thigh_mean > 0:
        duty_mean = (thigh_mean / p_mean) * 100.0
    elif (thigh_mean + tlow_mean) > 0:
        duty_mean = (thigh_mean / (thigh_mean + tlow_mean)) * 100.0
    else:
        duty_mean = float(np.mean(arr)) * 100.0

    duty_mean = max(0.0, min(100.0, duty_mean))

    return {
        "state": "TOGGLING",
        "num_transitions": num_transitions,
        "num_rising": num_rising,
        "num_falling": num_falling,
        "freq_mean": freq_mean,
        "period_mean": p_mean,
        "period_min": p_min,
        "period_max": p_max,
        "thigh_mean": thigh_mean,
        "thigh_min": thigh_min,
        "tlow_mean": tlow_mean,
        "tlow_min": tlow_min,
        "duty_mean": duty_mean,
    }


def format_si_val(value: float, unit: str = "s") -> str:
    """Định dạng giá trị kèm tiền tố SI chuẩn (s, ms, µs, ns hoặc Hz, kHz, MHz)."""
    if abs(value) < 1e-12:
        return f"0 {unit}"

    abs_v = abs(value)
    if unit == "Hz":
        if abs_v >= 1e6:
            return f"{value / 1e6:.3f} MHz"
        elif abs_v >= 1e3:
            return f"{value / 1e3:.3f} kHz"
        else:
            return f"{value:.1f} Hz"
    elif unit == "s":
        if abs_v >= 1.0:
            return f"{value:.3f} s"
        elif abs_v >= 1e-3:
            return f"{value * 1e3:.3f} ms"
        elif abs_v >= 1e-6:
            return f"{value * 1e6:.3f} µs"
        else:
            return f"{value * 1e9:.1f} ns"
    return f"{value:.2f} {unit}"


def format_measurement_results(res: Dict[str, Any]) -> Dict[str, str]:
    """Chuyển đổi kết quả đo đạc thành các chuỗi hiển thị đẹp mắt trên giao diện."""
    state = res.get("state", "NO_DATA")
    if state == "CONSTANT_HIGH":
        return {
            "state": "Constant HIGH (3.3V)",
            "freq": "N/A (No Clock)",
            "period": "N/A",
            "duty": "100.0 %",
            "thigh": "N/A",
            "tlow": "0.0 s",
            "transitions": "0 (Flat)",
            "min_pulse": "N/A"
        }
    elif state == "CONSTANT_LOW":
        return {
            "state": "Constant LOW (0V)",
            "freq": "N/A (No Clock)",
            "period": "N/A",
            "duty": "0.0 %",
            "thigh": "0.0 s",
            "tlow": "N/A",
            "transitions": "0 (Flat)",
            "min_pulse": "N/A"
        }
    elif state == "NO_DATA":
        return {
            "state": "No Data",
            "freq": "N/A",
            "period": "N/A",
            "duty": "N/A",
            "thigh": "N/A",
            "tlow": "N/A",
            "transitions": "0",
            "min_pulse": "N/A"
        }

    freq_val = res.get("freq_mean", 0.0)
    p_val = res.get("period_mean", 0.0)
    duty_val = res.get("duty_mean", 0.0)
    thigh_val = res.get("thigh_mean", 0.0)
    tlow_val = res.get("tlow_mean", 0.0)
    num_trans = res.get("num_transitions", 0)
    num_r = res.get("num_rising", 0)
    num_f = res.get("num_falling", 0)

    # Độ rộng xung tối thiểu (Min Pulse Width -> suy ra Baudrate nếu là UART)
    thigh_min = res.get("thigh_min", 0.0)
    tlow_min = res.get("tlow_min", 0.0)
    min_pulse = min(p for p in (thigh_min, tlow_min) if p > 0) if (thigh_min > 0 or tlow_min > 0) else 0.0

    min_pulse_str = format_si_val(min_pulse, "s")
    if min_pulse > 0:
        est_baud = 1.0 / min_pulse
        if 9600 <= est_baud <= 1_000_000:
            min_pulse_str += f" (~{int(round(est_baud / 100.0) * 100)} bps)"

    return {
        "state": f"Toggling ({num_trans} edges)",
        "freq": format_si_val(freq_val, "Hz") if freq_val > 0 else "N/A",
        "period": format_si_val(p_val, "s") if p_val > 0 else "N/A",
        "duty": f"{duty_val:.1f} %",
        "thigh": format_si_val(thigh_val, "s") if thigh_val > 0 else "N/A",
        "tlow": format_si_val(tlow_val, "s") if tlow_val > 0 else "N/A",
        "transitions": f"{num_trans} (↑{num_r} / ↓{num_f})",
        "min_pulse": min_pulse_str
    }


def find_most_active_channel(channels: List[Any]) -> int:
    """Tự động tìm kênh có nhiều xung chuyển mức nhất để hiển thị đo đạc mặc định."""
    max_edges = -1
    best_ch = 0
    for ch_i, ch_data in enumerate(channels):
        arr = np.asarray(ch_data, dtype=np.uint8)
        if len(arr) > 1:
            edges = int(np.sum(arr[:-1] != arr[1:]))
            if edges > max_edges:
                max_edges = edges
                best_ch = ch_i
    return best_ch
