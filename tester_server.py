import http.server
import json
import time

config_path = 'config.json'
method_limits = {}
rate_limits = []

class MyHTTPHandler(http.server.BaseHTTPRequestHandler): 
    def do_GET(self):
        # Imitate the Riot API, returning data with headers
        if available(self.path):
            self.generate_response(200)
        else:
            self.generate_response(429)
    
    def do_POST(self):
        # Collect responses from RateLimiter
        pass
        
    def generate_response(self, code):
        headers = dict(zip(getRateLimit(self.path), getMethodLimit(self.path)))
        self.generate_body(code) 
        
    
    
class Limit():
    def __init__(self, seconds=0, limit=-1):
        self.seconds = seconds
        self.limit = limit
        self.used = 0
        self.start = None

    def available(self):
        if self.start == None:
            return True
        if self.used < limit:
            return True
        # used >= limit
        if (time.time() - self.seconds) > self.start:
            return True
        
    def use(self): 
        if self.start == None:
            self.start = time.time()
        if (time.time() - self.seconds) > self.start:
            self.start = time.time()
            self.used = 0
        self.used += 1
        
        

def newMethodLimit(url):
    global method_limits
    method_limits[url] = [Limit(seconds=5, limit=10), Limit(seconds=1, limit=1)]

def getRateLimit(url):
    # Assumes only one platform for testing
    global rate_limits
    if len(rate_limits) == 0:
        rate_limits.append(Limit(seconds=1, limit=3))
        rate_limits.append(Limit(seconds=5, limit=10))
    limits = []
    counts = []
    for limit in rate_limits:
        limit.use()
        limits.append('%s:%s'%(limit.limit, limit.second))
        counts.append('%s:%s'%(limit.used, limit.second))
    headers = {
        'X-App-Rate-Limit':','.join(limits), 
        'X-App-Rate-Limit-Count':','.join(counts)
        }
    return headers
    
def getMethodLimit(url):
    if not url in method_limits:
        newMethodLimit(url)
    # Get the right URL
    limits = []
    counts = []
    for limit in method_limits[url]:
        limit.use()
        limits.append('%s:%s'%(limit.limit, limit.second))
        counts.append('%s:%s'%(limit.used, limit.second))
    headers = {
        'X-Method-Rate-Limit':','.join(limits), 
        'X-Method-Rate-Limit-Count':','.join(counts)
        }
    return headers
        
        
def available(url=None):
    for limit in rate_limits:
        if not limit.available():
            return (False, 'rate')
    if url != None:
        for limit in method_limits[url]:
            if not limit.available():
                return (False, 'method')
    return (True, 'all')
        
        
def generate_200(url):
    headers = {
        "Content-Type": "application/json;charset=utf-8"
    }
    body = ''
    code = 200
    return code, headers, body
        
def generate_403(url):
    headers = {}
    body = ''
    code = 403
    return code, headers, body
        
def generate_429(url):
    headers = {}
    body = ''
    code = 429
    return code, headers, body
        
def generate_500(url):
    headers = {}
    body = ''
    code = 500
    return code, headers, body
        
        
def startServer():
    port = 8000
    try:
        with open(config_path) as f:
            data = f.read()
            try:
                config = json.loads(data)
            except ValueError as e:
                print('Error reading config file, malformed JSON:')
                print('\t{}'.format(e))
                exit(0)
        port = config['server']['port'] + 1
    except Exception as e:
        print('Unable to set test server port: %s'%e)
        
    server = http.server.HTTPServer('127.0.0.1', port, MyHTTPHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping server...') 
        
        
if __name__ == '__main__':
    startServer()
    
        
    
        

