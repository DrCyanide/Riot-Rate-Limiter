import time
#from multiprocessing import Lock
from Limit import Limit
from Endpoint import Endpoint

class Platform():
    def __init__(self, slug=''):
        self.slug = slug
        #self.lock = Lock()

        self.static_endpoints = {}
        self.static_count = 0
        
        self.limited_endpoints = {}
        self.limited_count = 0
        self.ordered_limited_endpoints = []
        self.last_limited_endpoint = ''
        
        self.platform_limits = {}

        
    @property
    def count(self):
        print('Count for slug %s = %s, %s'%(self.slug, self.static_count + self.limited_count, self.limited_endpoints))
        return self.static_count + self.limited_count
        
    def hasURL(self):
        if self.count > 0:
            return True
        return False
        
        
    def addURL(self, url):
        endpoint_str = Endpoint.identifyEndpoint(url)
        #self.lock.acquire()
        if 'static' in endpoint_str:
            if not endpoint_str in self.static_endpoints:
                self.static_endpoints[endpoint_str] = Endpoint()
            self.static_endpoints[endpoint_str].addURL(url)
            self.static_count += 1
        else:
            if not endpoint_str in self.limited_endpoints:
                self.limited_endpoints[endpoint_str] = Endpoint()
                self.ordered_limited_endpoints.append(endpoint_str)
            self.limited_endpoints[endpoint_str].addURL(url)
            self.limited_count += 1
        #self.lock.release()
        
        
    def addData(self, data):
        # data is a dict with url inside, but other info too
        endpoint_str = Endpoint.identifyEndpoint(data['url'])
        #self.lock.acquire()
        if 'static' in endpoint_str:
            if not endpoint_str in self.static_endpoints:
                self.static_endpoints[endpoint_str] = Endpoint()
            self.static_endpoints[endpoint_str].addData(data)
            self.static_count += 1
        else:
            if not endpoint_str in self.limited_endpoints:
                self.limited_endpoints[endpoint_str] = Endpoint()
                self.ordered_limited_endpoints.append(endpoint_str)
            self.limited_endpoints[endpoint_str].addData(data)
            self.limited_count += 1
        #self.lock.release()
        print('Added data count: %s'%self.limited_count)
        
        
    def rateLimitOK(self):
        # Whether the Platform is inside it's rate limit
        now = time.time()
        for limit_str in self.platform_limits:
            if not self.platform_limits[limit_str].ready():
                return False
        return True
           
        
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
        
        
        
        