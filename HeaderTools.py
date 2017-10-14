import datetime
import time
import math

def format_date(headers):
    # https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
    date_format = '%a, %d %b %Y  %H:%M:%S %Z'  # Not certain on %d, might be un-padded
    response_time = datetime.datetime.strptime(headers['Date'], date_format)
    # strptime doesn't save the timezone, and the servers return in GMT (basically UTC)
    return response_time


def retry_after_time(headers, default_retry_after=1):
    # Has issues with retry_after's shorter than 1 second,
    # but the documentation says that X-Retry-Ater will be in seconds
    response_time = format_date(headers)
    retry_after = math.ceil(float(headers.get('X-Retry-After', default_retry_after)))
    response_time = response_time + datetime.timedelta(seconds=retry_after)
    local_time = time.mktime(time.localtime())
    #offset = time.mktime(time.gmtime()) - local_time  # GMT conversion # was being effected by timezone
    offset = time.mktime(datetime.datetime.utcnow().timetuple()) - local_time  # GMT conversion
    localized_time = time.mktime(response_time.timetuple()) - offset
    return localized_time


def split_limits(headers, key):
    str_limits = headers.get(key).split(',')
    limits = []
    for limit in str_limits:
        value, seconds = limit.split(':')
        limits.append((value, seconds))
    return limits