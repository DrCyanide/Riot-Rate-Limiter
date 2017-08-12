import time
from multiprocessing import Queue, Lock
from Limit import Limit
from Endpoint import Endpoint

class Platform():
    def __init__(self, slug):
        self.slug = slug
        self.lock = Lock()

        self.static_endpoints = {}
        self.static_count = 0
        
        self.limited_endpoints = {}
        self.limited_count = 0
        self.ordered_limited_endpoints = []
        self.last_limited_endpoint = ''
        
        self.platform_limits = {}
        
        self.last_endpoint = ''

        
    def addURL(self, url):
        endpoint = Endpoint.identifyEndpoint(url)
        self.lock.acquire()
        if 'static' in endpoint:
            if not endpoint in self.static_endpoints:
                self.static_endpoints[endpoint] = Endpoint()
            self.static_endpoints[endpoint].add(url)
            self.static_count += 1
        else:
            if not endpoint in self.limited_endpoints:
                self.limited_endpoints[endpoint] = Endpoint()
                self.ordered_limited_endpoints.append(endpoint)
            self.limited_endpoints[endpoint].add(url)
            self.limited_count += 1
        self.lock.release()
        
        
    def rateLimitOK(self):
        now = time.time()
        for limit in self.platform_limits:
            if not limit.ready():
                return False
        return True
           

    def hasURL(self):
        self.lock.acquire()
        if self.static_count > 0 or self.limited_count > 0:
            self.lock.release()
            return True
        self.lock.release()
        return False
        
        
    def setLimit(self, headers):
        # Set self.limits
        limits = headers['X-App-Rate-Limit'].split(',')
        for limit in limits:
            requests, seconds = limit.split(':')
            if seconds in self.platform_limits:
                self.platform_limits[seconds].limit = requests
            else:
                self.platform_limits[seconds] = Limit(seconds, requests)
       
       
    def setCount(self, headers):
        limits = headers['X-App-Rate-Limit-Count'].split(',')
        for limit in limits:
            used, seconds = limit.split(':')
            if seconds in self.platform_limits:
                self.platform_limits[seconds]['used'] = used

                
    def setEndpointLimit(self, url, headers):
        endpoint = Endpoint.identifyEndpoint(url)
        if 'static' in endpoint:
            if not self.static_endpoints[endpoint].limitsDefined:
                self.static_endpoints[endpoint].setLimit(headers)
        else:
            if not self.limited_endpoints[endpoint].limitsDefined:
                self.limited_endpoints[endpoint].setLimit(headers)
    
    
    def setEndpointCount(self, url, headers):
        endpoint = Endpoint.identifyEndpoint(url)
        if 'static' in endpoint:
            if not self.static_endpoints[endpoint].limitsDefined:
                self.static_endpoints[endpoint].setCount(headers)
        else:
            if not self.limited_endpoints[endpoint].limitsDefined:
                self.limited_endpoints[endpoint].setCount(headers)
        
        
    def soonestAvailable(self, endpoints):
        soonest = None
        for endpoint in endpoints:
            if endpoint.available():
                return time.time()
            else:
                if soonest == None:
                    soonest = endpoint.resetTime()
                else:
                    t = endpoint.resetTime()
                    if t < soonest:
                        soonest = t
        return soonest
        

    def timeNextAvailable(self):
        # Return the time when the next request will be available
        # Use this so the Ticker isn't constantly hammering Platform
        if self.static_count > 0:
            return self.soonestAvailable(self.static_endpoints)
        elif self.limited_count > 0 and self.rateLimitOK():
            return self.soonestAvailable(self.limited_endpoints)
        else:
            return None # No records!
        
        
    def getSearchOrder(self):
        i = self.ordered_limited_endpoints.index(self.last_limited_endpoint) + 1
        if i >= len(self.ordered_limited_endpoints):
            i = 0
        search_order = self.ordered_limited_endpoints[i:] + self.ordered_limited_endpoints[:i]
        return search_order
        
    def getURL(self):
        # Return a URL that's limit OK to be run, and whether or not it needs a limit/count return
        url = None
        endpoint_limit_needed = False
        platform_limit_needed = False
        
        if len(self.platform_limits.keys()) == 0:
            platform_limit_needed = True
            
        if self.static_count > 0:
            # Static data effects multiple other endpoints, so these always get priority
            for endpoint in self.static_endpoints:
                if endpoint.available() and endpoint.count > 0:
                    url = endpoint.get()
                    endpoint_limit_needed = not endpoint.limitsDefined
                    break
        elif self.limited_count > 0:
            # Actually need to rotate these
            if not self.last_queue == '':
                # Find the next one in the list
                search_order = self.getSearchOrder()
                for endpoint_str in search_order:
                    endpoint = self.limited_endpoints[endpoint_str]
                    if endpoint.available() and endpoint.count > 0:
                        url = endpoint.get()
                        endpoint_limit_needed = not endpoint.limitsDefined
                        self.last_queue = endpoint.name
                        break
            else:
                for endpoint in self.limited_endpoints:
                    if endpoint.available() and endpoint.count > 0:
                        url = endpoint.get()
                        endpoint_limit_needed = not endpoint.limitsDefined
                        self.last_queue = endpoint.name
                        break
                
        return url, platform_limit_needed, endpoint_limit_needed
        
        
        
        