import time
#from multiprocessing import Queue, Lock
#from multiprocessing import Lock
from collections import deque
from Limit import Limit

class Endpoint():
    def __init__(self, name='', first_request=None):
        self.name = name
        #self.url_queue = Queue()
        self.url_deque = deque()
        #self.lock = Lock()
        self.limits = {}
        
        self.delay = False
        self.delay_end = None
        
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
      
    def handleDelay(self, delay_end):
        if delay_end > time.time():
            self.delay_end = delay_end
            self.delay = True
      
    def setLimit(self, headers):
        try:
            if 'X-Method-Rate-Limit' in headers:
                limits = headers['X-Method-Rate-Limit'].split(',')
                for limit in limits:
                    requests, seconds = limit.split(':')
                    if seconds in self.limits:
                        self.limits[seconds].setLimit(seconds, requests)
                    else:
                        self.limits[seconds] = Limit(seconds, requests)
        except Exception as e:
            print('Endpoint - setLimit: e'%e)
    
    def setCount(self, headers):
        try:
            if 'X-Method-Rate-Limit-Count' in headers:
                limits = headers['X-Method-Rate-Limit-Count'].split(',')
                for limit in limits:
                    used, seconds = limit.split(':')
                    if seconds in self.limits:
                        self.limits[seconds].setUsed(used)
        except Exception as e:
            print('Endpoint - setCount: %s'%e)
                
    def addURL(self, url, atFront=False):
        # TODO: Add a way to add to the front of the deque
        if self.name == '':
            self.name = Endpoint.identifyEndpoint(url)
        else:
            if self.name != Endpoint.identifyEndpoint(url):
                raise Exception('Invalid URL, does not match endpoint')
        #self.lock.acquire()
        #self.url_queue.put(url)
        if atFront:
            self.url_deque.appendleft(url)
        else:
            self.url_deque.append(url)
        #self.lock.release()
        
    def addData(self, data, atFront=False):
        if self.name == '':
            self.name = Endpoint.identifyEndpoint(data['url'])
        else:
            if self.name != Endpoint.identifyEndpoint(data['url']):
                raise Exception('Invalid URL, does not match endpoint')
        #self.lock.acquire()
        #self.url_queue.put(url)
        if atFront:
            self.url_deque.appendleft(data)
        else:
            self.url_deque.append(data)
        #self.lock.release()
        
        
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
            s = '%s:%s'%(self.limits[limit_str].used, self.limits[limit_str].limit)
            strs.append(s)
        return ','.join(strs)
    
    @property
    def count(self):
        #return self.url_queue.qsize()
        return len(self.url_deque)
    
    def getResetTime(self):
        r_time = time.time()
        for limit in self.limits:
            if not self.limits[limit].ready():
                t = self.limits[limit].getResetTime()
                if t > r_time:
                    r_time = t
        return r_time
        
    def timeNextAvailable(self):
        if self.delay:
            return self.delay_end
        if self.available():
            return time.time()
        return self.getResetTime()
        
    def get(self):
        #self.lock.acquire()
        if self.count == 0:
            #self.lock.release()
            return None
            
        if not self.available():
            #self.lock.release()
            return None
                
        for limit in self.limits:
            self.limits[limit].use()
            
        #url = self.url_queue.get()
        url = self.url_deque.popleft()
        #self.lock.release()
        return url
         
        
