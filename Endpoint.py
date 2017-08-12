import time
from multiprocessing import Queue, Lock
from Limit import Limit

class Endpoint():
    def __init__(self, name='', first_request=None):
        self.name = name
        self.queue = Queue()
        self.lock = Lock()
        self.limits = {}
        
        if first_request == None:
            self.first_request = time.time()
        else:
            self.first_request = first_request
        
    @classmethod
    def identifyEndpoint(cls, url):
        url = url[:url.find('?')].lower() # Remove the query string
        split_url = url.split()
        endpoint = ''
        try:
            split_url = split_url[2:] # remove region
            if 'by-name' in split_url: 
                endpoint = '/'.join(split_url[:-1]) # Ignore the player name itself
            else:
                for segment in split_url:
                    if not segment.isnumeric():
                        endpoint += segment + '/'
        except:
            endpoint = 'BadEndpoint'
        return endpoint
      
    @property
    def limitsDefined(self):
        if len(self.limits.keys()) > 0:
            return True
        return False
      
    def setLimit(self, headers):
        if 'X-Method-Rate-Limit' in headers:
            limits = headers['X-Method-Rate-Limit'].split(',')
            for limit in limits:
                requests, seconds = limit.split(':')
                if seconds in self.limits:
                    self.limits[seconds].limit = requests
                else:
                    self.limits[seconds] = Limit(seconds, requests)
            
    
    def setCount(self, headers):
        if 'X-Method-Rate-Limit-Count' in headers:
            limits = headers['X-Method-Rate-Limit-Count'].split(',')
            for limit in limits:
                used, seconds = limit.split(':')
                if seconds in self.limits:
                    self.limits[seconds].used = used
                
                
    def add(self, url):
        if self.name == '':
            self.name = identifyEndpoint(url)
        self.lock.acquire()
        self.queue.add(url)
        self.lock.release()
        
        
    def available(self):
        for limit in self.limits:
            if not limit.ready():
                return False
        return True
        
    
    @property
    def count(self):
        return self.queue.qsize()
    
    def resetTime(self):
        r_time = time.time()
        for limit in self.limits:
            t = limit.resetTime()
            if t > r_time:
                r_time = t
        return r_time
        
        
    def get(self):
        self.lock.acquire()
        if self.queue.qsize() == 0:
            self.lock.release()
            return None
            
        if not self.available():
            self.lock.release()
            return None
                
        for limit in self.limits:
            limit.use()
            
        url = self.queue.pop()
        self.lock.release()
        return url
         
        