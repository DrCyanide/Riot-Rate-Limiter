import time
import datetime
#from multiprocessing import Lock
from Limit import Limit
from Endpoint import Endpoint

class Platform():
    def __init__(self, slug=''):
        self.slug = slug
        #self.lock = Lock()
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
        
    def hasURL(self):
        if self.count > 0:
            return True
        return False
        
        
    def addData(self, data, atFront=False):
        # data is a dict with url inside, but other info too
        endpoint_str = Endpoint.identifyEndpoint(data['url'])
        #self.lock.acquire()
        if 'static' in endpoint_str:
            if not endpoint_str in self.static_endpoints:
                self.static_endpoints[endpoint_str] = Endpoint()
            self.static_endpoints[endpoint_str].addData(data, atFront)
            self.static_count += 1
        else:
            if not endpoint_str in self.limited_endpoints:
                self.limited_endpoints[endpoint_str] = Endpoint()
                self.ordered_limited_endpoints.append(endpoint_str)
            self.limited_endpoints[endpoint_str].addData(data, atFront)
            self.limited_count += 1
        #self.lock.release()
        
        
    def rateLimitOK(self):
        # Whether the Platform is inside it's rate limit
        now = time.time()
        for limit_str in self.platform_limits:
            if not self.platform_limits[limit_str].ready():
                return False
        if self.delay:
            if now < self.delay_end:
                return False
            else:
                self.delay = False
        return True
           
           
    def handleHeaders(self, url, headers):
        # Check that X-App-Rate-Limit didn't change
        if 'X-App-Rate-Limit' in headers:
            limits = headers['X-App-Rate-Limit'].split(',')
            intervals = [limit.split(':')[1] for limit in limits]
            if sorted(intervals) != sorted(list(self.platform_limits.keys())):
                print('Platform limit changed: %s'%limits)
                self.platform_limits = {}
                self.setLimit(headers)
            
        # Check that X-App-Rate-Limit-Count is still OK
        if 'X-App-Rate-Limit-Count' in headers:
            counts = headers['X-App-Rate-Limit-Count'].split(',')
            intervals = [limit.split(':')[1] for limit in limits]
            counts = [limit.split(':')[0] for limit in limits]
            countLookup = dict(zip(intervals, counts))
            for seconds in self.platform_limits:
                if countLookup[seconds] > self.platform_limits[seconds].used:
                    self.setCount(headers)
                    break
           
        # Check for errors?
        
           
    def handleDelay(self, url, headers):
        # Identify type of delay
        limit_type = headers['X-Rate-Limit-Type']
        delay_end = time.time() + 1 # default to 1 second in the future
        if 'Retry-After' in headers:
            # https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
            date_format = '%a, %d %b %Y  %H:%M:%S %Z' # Not certain on %d, might be unpadded
            response_time = datetime.datetime.strptime(headers['Date'], date_format)
            response_time = response_time + datetime.timedelta(seconds=float(headers['Retry-After']))
            delay_end = time.mktime(response_time.timetuple())
        
        if limit_type == None or limit_type.lower() == 'service': # Assume on method level
            limit_type = 'method' # How's that for code reuse!
            
        if limit_type.lower() == 'application': # Set delay in the Platform
            self.delay = True
            self.delay_end = delay_end
            return
           
        if limit_type.lower() == 'method': # Set delay in the Endpoint
            endpoint_str = Endpoint.identifyEndpoint(url)
            if 'static' in endpoint_str:
                self.static_endpoints[endpoint_str].handleDelay(delay_end)
            else:
                self.limited_endpoints[endpoint_str].handleDelay(delay_end)
            
            
        
    def setLimit(self, headers):
        # Set self.limits
        #self.lock.acquire()
        limits = headers['X-App-Rate-Limit'].split(',')
        for limit in limits:
            requests, seconds = limit.split(':')
            if seconds in self.platform_limits:
                self.platform_limits[seconds].setLimit(seconds, requests)
            else:
                self.platform_limits[seconds] = Limit(seconds, requests)
        #self.lock.release()
       
    def setCount(self, headers):
        #self.lock.acquire()
        limits = headers['X-App-Rate-Limit-Count'].split(',')
        for limit in limits:
            used, seconds = limit.split(':')
            if seconds in self.platform_limits:
                self.platform_limits[seconds].setUsed(used)
        #self.lock.release()
    
    def setLimitAndCount(self, headers):
        self.setLimit(headers)
        self.setCount(headers)
                
                
    def setEndpointLimit(self, url, headers):
        #self.lock.acquire()
        endpoint_str = Endpoint.identifyEndpoint(url)
        if 'static' in endpoint_str:
            if not self.static_endpoints[endpoint_str].limitsDefined:
                self.static_endpoints[endpoint_str].setLimit(headers)
        else:
            if not self.limited_endpoints[endpoint_str].limitsDefined:
                self.limited_endpoints[endpoint_str].setLimit(headers)
        #self.lock.release()
    
    def setEndpointCount(self, url, headers):
        #self.lock.acquire()
        endpoint_str = Endpoint.identifyEndpoint(url)
        if 'static' in endpoint_str:
            self.static_endpoints[endpoint_str].setCount(headers)
        else:
            self.limited_endpoints[endpoint_str].setCount(headers)
        #self.lock.release()
        
    def setEndpointLimitAndCount(self, url, headers):
        self.setEndpointLimit(url, headers)
        self.setEndpointCount(url, headers)
        
        
    def getResetTime(self):
        r_time = time.time()
        for limit_str in self.platform_limits:
            if not self.platform_limits[limit_str].ready():
                t = self.platform_limits[limit_str].getResetTime()
                if t > r_time:
                    r_time = t
        return r_time
        
        
    def _soonestAvailable(self, endpoints):
        soonest = None
        for endpoint_str in endpoints:
            if endpoints[endpoint_str].count == 0:
                continue
            if endpoints[endpoint_str].available():
                return time.time()
            else:
                if soonest == None:
                    soonest = endpoints[endpoint_str].timeNextAvailable()
                else:
                    t = endpoints[endpoint_str].timeNextAvailable()
                    if t < soonest:
                        soonest = t
        return soonest
        

    def timeNextAvailable(self):
        # Return the time when the next request will be available
        # Factors in Method Limits
        # Use this so the Ticker isn't constantly hammering Platform
        if self.delay:
            if time.time() < self.delay_end:
                return self.delay_end
            else:
                self.delay = False
        if self.static_count > 0:
            return self._soonestAvailable(self.static_endpoints)
        elif self.limited_count > 0:
            if self.rateLimitOK():
                return self._soonestAvailable(self.limited_endpoints)
            else:
                return self.getResetTime()
        else:
            return None # No records!
        
        
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
        elif self.limited_count > 0 and self.rateLimitOK:
            for endpoint_str in self.limited_endpoints:
                if self.limited_endpoints[endpoint_str].available():
                    #print(endpoint_str)
                    return True
        return False
        
        
    def getUsage(self):
        usage = {'static':{}, 'limited':{}}
        for endpoint_str in self.static_endpoints:
            usage['static'][endpoint_str] = self.static_endpoints[endpoint_str].getUsage()
        for endpoint_str in self.limited_endpoints:
            usage['limited'][endpoint_str] = self.limited_endpoints[endpoint_str].getUsage()
        return usage
        
    def getSearchOrder(self):
        if self.last_limited_endpoint == '':
            return self.ordered_limited_endpoints
    
        i = self.ordered_limited_endpoints.index(self.last_limited_endpoint) + 1
        if i >= len(self.ordered_limited_endpoints):
            i = 0
        search_order = self.ordered_limited_endpoints[i:] + self.ordered_limited_endpoints[:i]
        return search_order
        
    def get(self):
        # Return data/URL that's limit OK to be run, and whether or not it needs a limit/count return
        obj = None
        endpoint_limit_needed = False
        platform_limit_needed = False
        
        # Need to modify this, since it should always verify after every call
        
        if not self.available():
            return obj, platform_limit_needed, endpoint_limit_needed
        
        #self.lock.acquire()
        try:
            if len(self.platform_limits.keys()) == 0:
                platform_limit_needed = True
                
            if self.static_count > 0:
                # Static data effects multiple other endpoints, so these always get priority
                for endpoint_str in self.static_endpoints:
                    endpoint = self.static_endpoints[endpoint_str]
                    if endpoint.available() and endpoint.count > 0:
                        obj = endpoint.get()
                        endpoint_limit_needed = not endpoint.limitsDefined
                        self.static_count -= 1
                        break
            elif self.limited_count > 0 and self.rateLimitOK():
                # Actually need to rotate these
                search_order = self.getSearchOrder()
                for endpoint_str in search_order:
                    endpoint = self.limited_endpoints[endpoint_str]
                    if endpoint.available() and endpoint.count > 0:
                        obj = endpoint.get()
                        endpoint_limit_needed = not endpoint.limitsDefined
                        self.last_limited_endpoint = endpoint.name
                        self.limited_count -= 1
                        break
                # Use the platform limit
                for limit in self.platform_limits:
                    self.platform_limits[limit].use()
        except Exception as e:
            print('Platform %s: Exception getting obj\n%s'%(self.slug, e))
        #self.lock.release()
        return obj, platform_limit_needed, endpoint_limit_needed
        
        
        
        
