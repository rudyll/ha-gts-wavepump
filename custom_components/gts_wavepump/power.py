"""Raw pump bytes and App display percentages are distinct units."""
import math


def valid_number(value, lower, upper):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and lower <= value <= upper)


def display_power(raw, software_version):
    if type(raw) is not int or not 0 <= raw <= 99 or type(software_version) is not int:
        raise ValueError("verified raw power and software version required")
    return raw + 20 if software_version > 4 and raw else raw


def gain_limit(baseline, software_version, output_ceiling=None):
    if (not isinstance(baseline, (list, tuple)) or len(baseline) != 24
            or any(type(p) is not int or not 0 <= p <= 99 for p in baseline)):
        raise ValueError("complete raw daily baseline required")
    if type(software_version) is not int:
        raise ValueError("verified firmware required")
    cap = 119 if software_version > 4 else 99
    if output_ceiling is not None:
        if type(output_ceiling) is not int or not 1 <= output_ceiling <= cap:
            raise ValueError("invalid App-display output ceiling")
        cap = output_ceiling
    peak = max(display_power(p, software_version) for p in baseline)
    return cap * 100 // peak if peak else 100


def scale_curve(baseline, gain, software_version, output_ceiling=None):
    limit = gain_limit(baseline, software_version, output_ceiling)
    if not valid_number(gain, 10, limit):
        raise ValueError("gain exceeds actual daily-baseline headroom")
    if gain == 100:
        return list(baseline)
    offset = 20 if software_version > 4 else 0
    result = []
    for raw in baseline:
        if raw == 0:
            result.append(0)
            continue
        # Conservative integer setpoints; no segment-specific peak clipping.
        app = math.floor(display_power(raw, software_version) * gain / 100)
        result.append(max(1, app - offset))
    return result
