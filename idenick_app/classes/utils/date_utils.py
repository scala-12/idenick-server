"""date utils"""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S%z'


def duration_to_str(duration: timedelta, show_positive_symbol: Optional[bool] = True) -> str:
    """duration to UTC string; min -99:59, max 99:59, else None"""
    seconds = duration.total_seconds()
    hours = abs(int(seconds // 3600))
    minutes = abs(int((seconds % 3600) // 60))

    result = None
    if seconds == 0:
        result = '00:00'
    elif hours < 99:
        result = ''
        if seconds > 0:
            if show_positive_symbol:
                result += '+'
        else:
            result += '-'

        if  hours < 10:
            result += '0'

        result += str(hours) + ':'

        if minutes < 10:
            result += '0'

        result += str(minutes)

    return result


def str_to_duration(value: str) -> Optional[timedelta]:
    """UTC string to duration"""
    result = None
    time = value.replace('−', '-')
    time_regexp = re.match(r'\s*([-+]?\d?\d):([0-5]\d)\s*$', time)
    if time_regexp is not None:
        hours = int(time_regexp.group(1).replace('+', ''))
        minutes = int(time_regexp.group(2)) * (-1 if hours < 0 else 1)
        result = timedelta(hours=hours, minutes=minutes)

    return result


@dataclass
class DateInfo:
    """Date info container"""

    def __init__(self, date: datetime, utc: Optional[str] = None):
        self.utc = None if utc is None else ('UTC' + utc)
        self.date = date

        time = date.strftime('%H:%M')
        day = date.strftime('%d.%m.%Y')
        week_day = date.strftime('%a')
        month = date.strftime('%B %Y')

        self.week_day = week_day
        self.day = day
        self.month = month
        self.time = time


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
