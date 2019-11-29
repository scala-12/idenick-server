"""date utils"""
import re
from datetime import timedelta
from typing import Optional


def duration_UTC_to_str(duration: timedelta) -> str:
    """duration to UTC string"""
    seconds = duration.total_seconds()
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)

    result = '00:00' if seconds == 0 else (('+' if seconds > 0 else '')
                                           + ('00' if hours == 0 else str(hours))
                                           + ':'
                                           + ('0' if minutes < 10 else '') + str(minutes))

    return result


def str_to_duration_UTC(value: str) -> Optional[timedelta]:
    """UTC string to duration"""
    result = None
    time = value.replace('−', '-')
    timezone = re.match(r'\s*([-+]?[01]?\d):([034][05])\s*$', time)
    if timezone is not None:
        hours = int(timezone.group(1).replace('+', ''))
        minutes = int(timezone.group(2)) * (-1 if hours < 0 else 1)
        result = timedelta(hours=hours, minutes=minutes)

    return result


UTC = [
    '+14:00',
    '+13:45',
    '+13:00',
    '+12:45',
    '+12:00',
    '+11:00',
    '+10:30',
    '+10:00',
    '+9:30',
    '+9:00',
    '+8:45',
    '+8:00',
    '+7:00',
    '+6:30',
    '+6:00',
    '+5:45',
    '+5:30',
    '+5:00',
    '+4:30',
    '+4:00',
    '+3:30',
    '+3:00',
    '+2:00',
    '+1:00',
    '00:00',
    '-1:00',
    '-2:00',
    '-2:30',
    '-3:00',
    '-3:30',
    '-4:00',
    '-4:30',
    '-5:00',
    '-6:00',
    '-7:00',
    '-8:00',
    '-8:30',
    '-9:00',
    '-9:30',
    '-10:00',
    '-11:00',
    '-12:00',
]
