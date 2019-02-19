import time
from Limit import Limit
import HeaderTools


class Endpoint:
    def __init__(self, manager, name='', first_request=None):
        self.name = name
        self.data_deque = manager.list()
        self.limits = manager.dict()
        
        self.delay = False
        self.delay_end = None
        
        self.default_retry_after = 1
        
        if first_request is None:
            self.first_request = time.time()
        else:
            self.first_request = first_request


    @classmethod
    def identify_endpoint(cls, url):
        if '?' in url:  # Remove the query string
            url = url[:url.find('?')]
        url = url.lower()
        split_url = url.split('/')
        try:
            split_url = split_url[3:]  # remove region
            if 'by-name' in split_url or 'by-summoner': 
                return '/'.join(split_url[:-1])  # Ignore the player name itself
            else:
                non_numeric = []
                for segment in split_url:
                    if not segment.isnumeric():
                        non_numeric.append(segment)
                return '/'.join(non_numeric)
        except Exception as e:
            return 'BadEndpoint'
      
    @property
    def limits_defined(self):
        if len(self.limits.keys()) > 0:
            return True
        return False

    def handle_response_headers(self, headers, code=200):
        if 'X-Rate-Limit-Type' in headers or (400 <= code <= 500):
            self._handle_delay(headers)
        if 'X-Method-Rate-Limit' in headers:
            self._verify_limits(headers)
        if 'X-Method-Rate-Limit-Count' in headers:
            self._verify_counts(headers)

    def _handle_delay(self, headers):
        limit_type = headers.get('X-Rate-Limit-Type', 'service').lower()
        if limit_type in ['service', 'method']:
            self.delay = True
            self.delay_end = HeaderTools.retry_after_time(headers, self.default_retry_after)

    def _verify_limits(self, headers):
        try:
            if 'X-Method-Rate-Limit' in headers:
                h_limits = HeaderTools.split_limits(headers, 'X-Method-Rate-Limit')
                old_limits = set(self.limits.keys())
                for cap, seconds in h_limits:
                    if seconds in self.limits.keys():
                        old_limits.remove(seconds)
                        if self.limits[seconds].cap != int(cap):
                            print("Old limit didn't match cap - %s vs %s" % (self.limits[seconds].cap, cap))
                            self.limits.update([(seconds, Limit(seconds, cap))])
                            
                    else:
                        # self.limits[seconds] = Limit(seconds, cap)
                        self.limits.update([(seconds, Limit(seconds, cap))])
                        
                # Delete extra limits
                for seconds in old_limits:
                    print('Old limit removed? %s / %s' % (self.limits[seconds].cap, seconds))
                    self.limits.pop(seconds)
        except Exception as e:
            print('Endpoint - verifyLimits: e' % e)

    def _verify_counts(self, headers):
        try:
            if 'X-Method-Rate-Limit-Count' not in headers:
                return
            h_limits = HeaderTools.split_limits(headers, 'X-Method-Rate-Limit-Count')
            for used, seconds in h_limits:
                if seconds in self.limits.keys():
                    limit = self.limits[seconds]
                    limit.verify_count(int(used))
                    self.limits.update([(seconds, limit)])
                else:
                    print("Endpoint - Didn't find %s in limit, present in header" % seconds)
        except Exception as e:
            print('Endpoint - _verifyCounts: %s' % e)

    def add_data(self, data, front=False):
        if 'url' not in data:
            raise Exception('Invalid URL, required for addData')
        name = Endpoint.identify_endpoint(data['url'])
            
        if self.name == '':
            self.name = name
        else:
            if self.name != name:
                raise Exception('Invalid URL, does not match endpoint')

        if front:
            self.data_deque.insert(0, data)
        else:
            self.data_deque.append(data)

    def available(self):
        if self.count == 0:
            # print('Endpoint not available, no data')
            return False
        for seconds in self.limits.keys():
            limit = self.limits[seconds]
            if not limit.ready():
                print('Endpoint not available, limit issue')
                return False
        if self.delay:
            if time.time() < self.delay_end:
                return False
            else:
                self.delay = False
        return True

    def get_usage(self):
        strs = []
        if len(self.limits.keys()) == 0:
            return 'No limits defined'
        for seconds in sorted(self.limits.keys()):
            # This isn't completely accurate, will pause after the last request, even if the time has elapsed
            s = '%s:%s' % (self.limits[seconds].used, self.limits[seconds].cap)
            strs.append(s)
        return ','.join(strs)

    @property
    def count(self):
        return len(self.data_deque)

    def next_ready(self):
        if self.delay:
            if time.time() > self.delay_end:
                self.delay = False
        r_time = time.time()
        for seconds in self.limits.keys():
            limit = self.limits[seconds] 
            if not limit.ready():
                next = limit.next_ready()
                if next > r_time:
                    r_time = next
        if self.delay and r_time < self.delay_end:
            r_time = self.delay_end
        return r_time

    def get(self):
        if self.count == 0:
            return None
            
        if not self.available():
            return None
                
        for seconds in self.limits.keys():
            limit = self.limits[seconds]
            limit.use()
            self.limits.update([(seconds, limit)])
            
        data = self.data_deque.pop(0)
        return data
