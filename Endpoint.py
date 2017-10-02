import time
from collections import deque
from Limit import Limit

class Endpoint():
    def __init__(self, name='', first_request=None):
        self.name = name
        self.data_deque = deque()
        self.limits = {}
        
        self.delay = False
        self.delay_end = None
        
        self.default_retry_after = 1
        
        if first_request == None:
            self.first_request = time.time()
        else:
            self.first_request = first_request
        
    @classmethod
    def identifyEndpoint(cls, url):
        if '?' in url: # Remove the query string
            url = url[:url.find('?')]
        url = url.lower()
        split_url = url.split('/')
        endpoint = ''
        try:
            split_url = split_url[3:] # remove region
            if 'by-name' in split_url: 
                endpoint = '/'.join(split_url[:-1]) # Ignore the player name itself
            else:
                non_numeric = []
                for segment in split_url:
                    if not segment.isnumeric():
                        non_numeric.append(segment)
                endpoint = '/'.join(non_numeric)
        except:
            endpoint = 'BadEndpoint'
        return endpoint
      
    @property
    def limitsDefined(self):
        if len(self.limits.keys()) > 0:
            return True
        return False
            
      
    def handleResponseHeaders(self, headers):
        if 'X-Rate-Limit-Type' in headers:
            self._handleDelay(headers)
            
        if 'X-Method-Rate-Limit' in headers: 
            self._verifyLimits(headers)
                
        if 'X-Method-Rate-Limit-Count' in headers: 
            self._verifyCounts(headers)
            
            
    def _handleDelay(self, delay_end):
        limit_type = headers['X-Rate-Limit-Type'].lower()
        retry_after = self.default_retry_after
        if 'Retry-After' in headers:
            retry_after = float(headers['Retry-After'])
        
        if limit_type in ['service', 'method']:
            self.delay = True
            # https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
            date_format = '%a, %d %b %Y  %H:%M:%S %Z' # Not certain on %d, might be unpadded
            response_time = datetime.datetime.strptime(headers['Date'], date_format)
            response_time = response_time + datetime.timedelta(seconds=float(headers['Retry-After']))
            self.delay_end = time.mktime(response_time.timetuple())
      
      
    def _verifyLimits(self, headers):
        try:
            if 'X-Method-Rate-Limit' in headers:
                h_limits = headers['X-Method-Rate-Limit'].split(',')
                old_limits = set(self.limits.keys())
                
                for limit in h_limits:
                    requests, seconds = limit.split(':')
                    if seconds in self.limits:
                        if self.limits[seconds].cap != requests:
                            old_limits.remove(seconds)
                    else:
                        self.limits[seconds] = Limit(seconds, requests)
                        
                # Delete extra limits
                for seconds in old_limits:
                    self.limits.pop(seconds)
        except Exception as e:
            print('Endpoint - setLimit: e'%e)
    
    
    def _verifyCounts(self, headers):
        try:
            if 'X-Method-Rate-Limit-Count' in headers:
                limits = headers['X-Method-Rate-Limit-Count'].split(',')
                for limit in limits:
                    used, seconds = limit.split(':')
                    if seconds in self.limits:
                        self.limits[seconds].verifyCount(int(used))
        except Exception as e:
            print('Endpoint - _verifyCounts: %s'%e)
                
        
    def addData(self, data, atFront=False):
        if not 'url' in data:
            raise Exception('Invalid URL, required for addData')
        name = Endpoint.identifyEndpoint(data['url'])
            
        if self.name == '':
            self.name = name
        else:
            if self.name != name:
                raise Exception('Invalid URL, does not match endpoint')

        if atFront:
            self.data_deque.appendleft(data)
        else:
            self.data_deque.append(data)

        
        
    def available(self):
        if self.count == 0:
            return False
        for limit_str in self.limits:
            if not self.limits[limit_str].ready():
                return False
        if self.delay:
            if time.time() < self.delay_end:
                return False
            else:
                self.delay = False
        return True
        
    def getUsage(self):
        strs = []
        if len(self.limits.keys()) == 0:
            return 'No limits defined'
        for limit_str in self.limits:
            s = '%s:%s'%(self.limits[limit_str].used, self.limits[limit_str].cap)
            strs.append(s)
        return ','.join(strs)
    
    @property
    def count(self):
        return len(self.data_deque)
    
    
    def nextReady(self):
        if self.delay:
            if time.time() > self.delay_end:
                self.delay = False
        r_time = time.time()
        for limit in self.limits:
            if not self.limits[limit].ready():
                next = self.limits[limit].nextReady()
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
                
        for limit in self.limits:
            self.limits[limit].use()
            
        data = self.data_deque.popleft()
        return data
         
        
