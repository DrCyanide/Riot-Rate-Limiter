import datetime
import time


def format_date(headers):
    # https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
    date_format = '%a, %d %b %Y  %H:%M:%S %Z'  # Not certain on %d, might be un-padded
    response_time = datetime.datetime.strptime(headers['Date'], date_format)
    return response_time


def retry_after_time(headers, default_retry_after=1):
    response_time = format_date(headers)
    retry_after = float(headers.get('X-Retry-After', default_retry_after))
    response_time = response_time + datetime.timedelta(seconds=retry_after)
    return time.mktime(response_time.timetuple())


def split_limits(headers, key):
    str_limits = headers.get(key).split(',')
    limits = []
    for limit in str_limits:
        value, seconds = limit.split(':')
        limits.append((value, seconds))
    return limits