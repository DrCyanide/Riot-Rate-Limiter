import time
import datetime
from Limit import Limit
from Endpoint import Endpoint
import HeaderTools

class Platform:
    def __init__(self, slug=''):
        self.slug = slug
        self.delay = False
        self.delay_end = None
        self.default_retry_after = 1

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

    def add_data(self, data, front=False):
        # data is a dict with url inside, but other info too
        endpoint_str = Endpoint.identify_endpoint(data['url'])
        if 'static' in endpoint_str:
            if endpoint_str not in self.static_endpoints:
                self.static_endpoints[endpoint_str] = Endpoint()
            self.static_endpoints[endpoint_str].add_data(data, front)
            self.static_count += 1
        else:
            if endpoint_str not in self.limited_endpoints:
                self.limited_endpoints[endpoint_str] = Endpoint()
                self.ordered_limited_endpoints.append(endpoint_str)
            self.limited_endpoints[endpoint_str].add_data(data, front)
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

    def handle_response_headers(self, url, headers, code=200):
        # Handle X-Rate-Limit-Type
        if 'X-Rate-Limit-Type' in headers or (400 <= code <= 500):
            self._handle_delay(headers)

        # Check that X-App-Rate-Limit didn't change
        if 'X-App-Rate-Limit' in headers:
            try:
                self._verify_limits(headers)
            except Exception as e:
                print('Platform - Exception verifying limits - %s' % e)

        # Check that X-App-Rate-Limit-Count is still OK
        if 'X-App-Rate-Limit-Count' in headers:
            try:
                self._verify_counts(headers)
            except Exception as e:
                print('Platform - Exception verifying counts - %s' % e)

        # Pass to the endpoint
        endpoint_str = Endpoint.identify_endpoint(url)
        if 'static' in endpoint_str:
            if endpoint_str in self.static_endpoints:
                self.static_endpoints[endpoint_str].handle_response_headers(headers, code)
            else:
                raise Exception('Invalid response URL: endpoint was not called')
        else:
            if endpoint_str in self.limited_endpoints:
                self.limited_endpoints[endpoint_str].handle_response_headers(headers, code)
            else:
                raise Exception('Invalid response URL: endpoint was not called')

    def _handle_delay(self, headers):
        # Identify type of delay
        limit_type = headers.get('X-Rate-Limit-Type', 'service').lower()
        if limit_type.lower() == 'application':  # Set delay in the Platform. Service/Method handled at Endpoint level
            self.delay = True
            self.delay_end = HeaderTools.retry_after_time(headers, self.default_retry_after)

    def _verify_limits(self, headers):
        if 'X-App-Rate-Limit' not in headers:
            return
        h_limits = HeaderTools.split_limits(headers, 'X-App-Rate-Limit')
        old_limits = set(self.platform_limits.keys())
        for requests, seconds in h_limits:
            if seconds in self.platform_limits:
                old_limits.remove(seconds)
                if self.platform_limits[seconds].cap != requests:
                    self.platform_limits[seconds] = Limit(seconds, requests)
            else:
                self.platform_limits[seconds] = Limit(seconds, requests)

        for seconds in old_limits:
            self.platform_limits.pop(seconds)
        

    def _verify_counts(self, headers):
        if 'X-App-Rate-Limit-Count' not in headers:
            return
        h_limits = HeaderTools.split_limits(headers, 'X-App-Rate-Limit-Count')
        for used, seconds in h_limits:
            if seconds in self.platform_limits:
                try:
                    self.platform_limits[seconds].verify_count(int(used))
                except Exception as e:
                    print('Platform - Failed Limit -  (%s out of %s / %s)' % (used, self.platform_limits[seconds].cap, seconds))
            # else should be handled by _verify_limits() being called first


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

    # noinspection PyMethodMayBeStatic
    def _soonest_available(self, endpoints):
        soonest = None
        for endpoint_str in endpoints:
            if endpoints[endpoint_str].count == 0:
                continue
            if endpoints[endpoint_str].available():
                return time.time()
            else:
                if soonest is None:
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
        # if self.delay:
        #     if time.time() < self.delay_end:
        #         return self.delay_end # Ticker is looking for a True/False for available, why am I returning a Time?
        #     else:
        #         self.delay = False
        if self.static_count > 0:
            print("Wasn't Static API Depricated?")
            for endpoint_str in self.static_endpoints:
                if self.static_endpoints[endpoint_str].available():
                    return True
        elif self.limited_count > 0 and self.rate_limit_ok():
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
