import time
import datetime
from Limit import Limit
from Endpoint import Endpoint


class Platform():
    def __init__(self, slug=''):
        self.slug = slug
        self.delay = False
        self.delay_end = None

        self.static_endpoints = {}
        self.static_count = 0

        self.limited_endpoints = {}
        self.limited_count = 0
        self.ordered_limited_endpoints = []
        self.last_limited_endpoint = ''

        self.platform_limits = {}

    @property
    def count(self):
        return self.static_count + self.limited_count

    def has_url(self):
        if self.count > 0:
            return True
        return False

    def add_data(self, data, atFront=False):
        # data is a dict with url inside, but other info too
        endpoint_str = Endpoint.identify_endpoint(data['url'])
        if 'static' in endpoint_str:
            if not endpoint_str in self.static_endpoints:
                self.static_endpoints[endpoint_str] = Endpoint()
            self.static_endpoints[endpoint_str].add_data(data, atFront)
            self.static_count += 1
        else:
            if not endpoint_str in self.limited_endpoints:
                self.limited_endpoints[endpoint_str] = Endpoint()
                self.ordered_limited_endpoints.append(endpoint_str)
            self.limited_endpoints[endpoint_str].add_data(data, atFront)
            self.limited_count += 1

    def rate_limit_ok(self):
        # Whether the Platform is inside it's rate limit
        for limit_str in self.platform_limits:
            if not self.platform_limits[limit_str].ready():
                return False
        if self.delay:
            now = time.time()
            if now < self.delay_end:
                return False
            else:
                self.delay = False
        return True

    def handle_response_headers(self, url, headers):
        # Handle X-Rate-Limit-Type
        if 'X-Rate-Limit-Type' in headers:
            limit_type = headers['X-Rate-Limit-Type'].lower()
            if limit_type == 'application':
                self._handle_delay(headers)

        # Check that X-App-Rate-Limit didn't change
        if 'X-App-Rate-Limit' in headers:
            self._verify_limits(headers)

        # Check that X-App-Rate-Limit-Count is still OK
        if 'X-App-Rate-Limit-Count' in headers:
            self._verify_counts(headers)

        # Pass to the endpoint
        endpoint_str = Endpoint.identify_endpoint(url)
        if 'static' in endpoint_str:
            self.static_endpoints[endpoint_str].handle_response_headers(headers)
        else:
            self.limited_endpoints[endpoint_str].handle_response_headers(headers)

    def _handle_delay(self, headers):
        # Identify type of delay
        limit_type = headers['X-Rate-Limit-Type']
        delay_end = time.time() + 1  # default to 1 second in the future
        if 'Retry-After' in headers:
            # https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
            date_format = '%a, %d %b %Y  %H:%M:%S %Z'  # Not certain on %d, might be unpadded
            response_time = datetime.datetime.strptime(headers['Date'], date_format)
            response_time = response_time + datetime.timedelta(seconds=float(headers['Retry-After']))
            delay_end = time.mktime(response_time.timetuple())

        if limit_type.lower() == 'application':  # Set delay in the Platform
            self.delay = True
            self.delay_end = delay_end
            return


    def _verify_limits(self, headers):
        try:
            h_limits = headers['X-App-Rate-Limit'].split(',')
            old_limits = set(self.platform_limits.keys())
            for limit in h_limits:
                requests, seconds = limit.split(':')
                if seconds in self.platform_limits:
                    if self.platform_limits[seconds].cap != requests:
                        old_limits.remove(seconds)
                else:
                    self.platform_limits[seconds] = Limit(seconds, requests)

            for seconds in old_limits:
                self.platform_limits.pop(seconds)
        except Exception as e:
            print('Platform - verifyLimits: %s' % e)


    def _verify_counts(self, headers):
        try:
            if not 'X-App-Rate-Limit-Count' in headers:
                return
            h_limits = headers['X-App-Rate-Limit-Count'].split(',')
            for limit in h_limits:
                used, seconds = limit.split(':')
                if seconds in self.platform_limits:
                    self.platform_limits[seconds].verify_count(int(used))
        except Exception as e:
            print('Platform - verifyLimits: %s' % e)

    """def getResetTime(self):
        r_time = time.time()
        for limit_str in self.platform_limits:
            if not self.platform_limits[limit_str].ready():
                t = self.platform_limits[limit_str].getResetTime()
                if t > r_time:
                    r_time = t
        return r_time
    """

    # nextReady() only matters if you've trying not to infinitely loop in the Ticker.
    # Why not have the ticker pause if all return not ready?


    def _soonest_available(self, endpoints):
        soonest = None
        for endpoint_str in endpoints:
            if endpoints[endpoint_str].count == 0:
                continue
            if endpoints[endpoint_str].available():
                return time.time()
            else:
                if soonest == None:
                    soonest = endpoints[endpoint_str].time_next_available()
                else:
                    t = endpoints[endpoint_str].time_next_available()
                    if t < soonest:
                        soonest = t
        return soonest

    """def time_next_available(self):
        # Return the time when the next request will be available
        # Factors in Method Limits
        # Use this so the Ticker isn't constantly hammering Platform
        if self.delay:
            if time.time() < self.delay_end:
                return self.delay_end
            else:
                self.delay = False
        if self.static_count > 0:
            return self._soonest_available(self.static_endpoints)
        elif self.limited_count > 0:
            if self.rate_limit_ok():
                return self._soonest_available(self.limited_endpoints)
            else:
                return self.getResetTime()
        else:
            return None  # No records!"""

    def available(self):
        if self.delay:
            if time.time() < self.delay_end:
                return self.delay_end
            else:
                self.delay = False
        if self.static_count > 0:
            for endpoint_str in self.static_endpoints:
                if self.static_endpoints[endpoint_str].available():
                    return True
        elif self.limited_count > 0 and self.rate_limit_ok:
            for endpoint_str in self.limited_endpoints:
                if self.limited_endpoints[endpoint_str].available():
                    # print(endpoint_str)
                    return True
        return False

    def get_usage(self):
        usage = {'static': {}, 'limited': {}}
        for endpoint_str in self.static_endpoints:
            usage['static'][endpoint_str] = self.static_endpoints[endpoint_str].get_usage()
        for endpoint_str in self.limited_endpoints:
            usage['limited'][endpoint_str] = self.limited_endpoints[endpoint_str].get_usage()
        return usage

    def get_search_order(self):
        if self.last_limited_endpoint == '':
            return self.ordered_limited_endpoints

        i = self.ordered_limited_endpoints.index(self.last_limited_endpoint) + 1
        if i >= len(self.ordered_limited_endpoints):
            i = 0
        search_order = self.ordered_limited_endpoints[i:] + self.ordered_limited_endpoints[:i]
        return search_order

    def get(self):
        if not self.available():
            raise Exception('Platform %s not available' % self.slug)

        try:
            if self.static_count > 0:
                # Static data effects multiple other calls, so these always get priority
                for endpoint_str in self.static_endpoints:
                    endpoint = self.static_endpoints[endpoint_str]
                    if endpoint.available() and endpoint.count > 0:
                        self.static_count -= 1
                        return endpoint.get()

            elif self.limited_count > 0 and self.rate_limit_ok():
                search_order = self.get_search_order()  # Used to rotate which gets pulled from
                for endpoint_str in search_order:
                    endpoint = self.limited_endpoints[endpoint_str]
                    if endpoint.available() and endpoint.count > 0:
                        self.last_limited_endpoint = endpoint.name
                        self.limited_count -= 1

                        for seconds in self.platform_limits:
                            self.platform_limits[seconds].use()

                        return endpoint.get()

        except Exception as e:
            print('Platform %s: Exception getting obj\n%s' % (self.slug, e))
