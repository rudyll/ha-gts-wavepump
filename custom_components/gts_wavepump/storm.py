"""Transient storm setpoints derived from the immutable daily tidal baseline."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class StormTarget:
    power: int
    baseline_power: int
    weather_power: int
    clipped: bool


def valid_number(value, lower, upper):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and lower <= value <= upper)


def daily_baseline(saved, current_powers, weather_gain):
    if not valid_number(weather_gain, 100, 200):
        raise ValueError("storm cannot override attenuation or an unknown tidal gain")
    if saved is None:
        if weather_gain != 100:
            raise ValueError("original daily baseline missing; never reverse a clipped curve")
        saved = current_powers
    if (not isinstance(saved, (list, tuple)) or len(saved) != 24 or
            any(type(power) is not int or not 0 <= power <= 99 for power in saved)):
        raise ValueError("complete valid original24-hour baseline required")
    return list(saved)


def storm_target(baseline, hour, gain, weather_gain, power_ceiling):
    baseline = daily_baseline(baseline, None, weather_gain)
    if type(hour) is not int or not 0 <= hour < 24:
        raise ValueError("valid local schedule hour required")
    if not valid_number(gain, 100, 200) or gain < weather_gain:
        raise ValueError("storm gain must be100..200 and not below current weather gain")
    if type(power_ceiling) is not int or not 1 <= power_ceiling <= 99:
        raise ValueError("storm power ceiling must be1..99")
    base = baseline[hour]
    if base == 0:
        raise ValueError("daily baseline is off in this hour; no storm start")
    normal = min(99, round(base * weather_gain / 100))
    if normal > power_ceiling:
        raise ValueError("storm cap is below weather output; keep tidal operation")
    requested = round(base * gain / 100)
    power = min(99, power_ceiling, requested)
    return StormTarget(power, base, normal, power < requested)
