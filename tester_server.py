import http.server
import json
import time

config_path = 'config.json'
method_limits = {}
rate_limits = []

class MyHTTPHandler(http.server.BaseHTTPRequestHandler): 
    def do_GET(self):
        # Imitate the Riot API, returning data with headers
        available, source, seconds = getAvailable(self.path)
        if available:
            self.generate_response(200)
        else:
            self.generate_response(429, source, seconds)
        
    
    def do_POST(self):
        # Collect responses from RateLimiter
        print('Got message')
        content_len = int(self.headers.getheader('content-length', 0))
        print('\t{url} - {code}\n\t{body}'.format(url=self.headers.get('url'), code=self.headers.get('code'), body=self.rfile.read(content_len)))
        pass
        
    def do_PUT(self):
        # Modify server mode to Normal (tries to imitate normal conditions) or Error (throw random errors)
        pass
        
    def generate_response(self, code, source=None, seconds=None):
        headers = getRateLimit(self.path)
        headers.update(getMethodLimit(self.path))
        #headers = dict(zip(getRateLimit(self.path), getMethodLimit(self.path)))
        if code == 429:
            headers['X-Rate-Limit-Type'] = source
            if seconds != None:
                headers['Retry-After'] = seconds
        body = self.generate_body(code) 
        
        self.send_response(200)
        for header in headers.keys():
            self.send_header(header, headers[header])
        self.end_headers()
        self.wfile.write(json.dumps(body).encode('utf-8'))
        
    def generate_body(self, code):
        body = {}
        return body
    
    
class Limit():
    def __init__(self, seconds=0, limit=-1):
        self.seconds = seconds
        self.limit = limit
        self.used = 0
        self.start = None

    def available(self):
        if self.start == None:
            return True
        if self.used < self.limit:
            return True
        # used >= limit
        if (time.time() - self.seconds) > self.start:
            return True
        
    def timeLeft(self):
        t = (self.start + self.seconds) - time.time()
        if t < 0:
            return 0 # already reset
        else:
            return t
        
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
        limits.append('%s:%s'%(limit.limit, limit.seconds))
        counts.append('%s:%s'%(limit.used, limit.seconds))
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
        limits.append('%s:%s'%(limit.limit, limit.seconds))
        counts.append('%s:%s'%(limit.used, limit.seconds))
    headers = {
        'X-Method-Rate-Limit':','.join(limits), 
        'X-Method-Rate-Limit-Count':','.join(counts)
        }
    return headers
        
        
def getAvailable(url=None):
    # Sources from the X-Rate-Limit-Type field
    seconds = None
    for limit in rate_limits:
        if not limit.available():
            if seconds == None or seconds < limit.timeLeft():
                seconds = limit.timeLeft()
    if seconds != None:
        return (False, 'application', seconds)
        
    if url != None:
        if not url in method_limits:
            newMethodLimit(url)
        for limit in method_limits[url]:
            if not limit.available():
                if seconds == None or seconds < limit.timeLeft():
                    seconds = limit.timeLeft()
    if seconds != None:
        return (False, 'method', seconds)
        
    return (True, 'service', seconds)
        
        
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
        port = int(config['server']['port']) + 1
    except Exception as e:
        print('Unable to set test server port: %s'%e)
        
    server = http.server.HTTPServer(('127.0.0.1', port), MyHTTPHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping server...') 
        
        
if __name__ == '__main__':
    startServer()
    
        
    
        

