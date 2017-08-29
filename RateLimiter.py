import http.server
import json
import multiprocessing
from multiprocessing import Lock
from multiprocessing import Pool
from multiprocessing import Process
from multiprocessing.queues import Empty
from multiprocessing.managers import SyncManager
import time
from collections import deque
import urllib.request
import urllib.error
import traceback

from Platform import Platform

config_path = 'config.json'
config = None
api_key = ''

platform_lock = Lock()
platforms = None

ticker_condition = None
get_dict = None
get_condition = None

logTimes = True
startTime = None

class MyHTTPHandler(http.server.BaseHTTPRequestHandler): 
    def do_OPTIONS(self): # For CORS requests
        self.send_response(200, "ok")
        #self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Headers", "X-Url")
        self.send_header("Access-Control-Allow-Headers", "X-Return-Url")
        
        self.end_headers()

    def end_headers (self):
        self.send_header('Access-Control-Allow-Origin', '*')
        http.server.BaseHTTPRequestHandler.end_headers(self)

    def do_GET(self):
        self.handleRequest()

    def do_PUT(self):
        self.handleRequest()
        
    def do_POST(self):
        self.handleRequest()
        
    def handleRequest(self):
        global startTime
        security_pass = self.checkSecurity()
        if not security_pass:
            return
        
        if logTimes:
            startTime = time.time()
            print('Start: %s'%startTime)
        
        data = {}
        data['url'] = self.headers.get('X-Url')
        if data['url'] == None:
            self.send_response(400)
            self.wfile.write('No X-Url header detected')
            self.end_headers()
            return
        
        data['method'] = self.command.upper()
        data['return_url'] = self.headers.get('X-Return-Url')
        
        # The Riot API has no commands where you just send data, so no return_url = error
        if  data['method'] in ['PUT','POST'] and (data['return_url'] == None):
            self.send_response(404)
            self.end_headers()
            return
            
        platform_slug = identifyPlatform(data['url'])
        if platform_slug in platforms:
            platform_lock.acquire()
            addData(platform_slug, data)
            platform_lock.release()
        else:
            platform_lock.acquire()
            platforms[platform_slug] = Platform(slug=platform_slug)
            addData(platform_slug, data)
            platform_lock.release()
        #print('%s count: %s'%(platform_slug, platforms[platform_slug].count))
        
        # Notify ticker
        ticker_condition.acquire()
        ticker_condition.notify()
        ticker_condition.release()
        
        if data['method'] == 'GET': 
            # GET = Synchronous, PUT/POST = Asynchronous
            keep_waiting = True
            while keep_waiting:
                get_condition.acquire()
                get_condition.wait()
                get_condition.release()
        
                if data['url'] in get_dict.keys():
                    keep_waiting = False
                    outbound_data = get_dict[data['url']]
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(outbound_data)                   
                    if logTimes:
                        t = time.time()
                        print('End: %s'%(t-startTime))
 
                    # TODO: Cleanup retrieved data so it doesn't keep taking up memory
                    return
                    
        self.send_response(200)
        self.end_headers()
    
    
    def checkSecurity(self):
        intruder = False
        IP = self.address_string()
        if len(config['security']['whitelist']) > 0:
            if not IP in config['security']['whitelist']:
                intruder = True
        if len(config['security']['blacklist']) > 0:
            if IP in config['security']['blacklist']:
                intruder = True
        if intruder:
            print('Unauthorized access detected from %s'%IP)
            self.send_response(404)
            self.end_headers()
        return not intruder
        
        
def addData(platform_slug, data):
    # syncmanager dicts require the update() command to be run
    # before anything will be saved. The normal 'addData()' method
    # won't result in the object being pickled again, thus it will
    # look like there was no update.
    global platforms
    p = platforms[platform_slug]
    p.addData(data)
    platforms.update([(platform_slug,p)])
    
    
def getData(platform_slug, platforms):
    # See addData comment
    #global platforms
    p = platforms[platform_slug]
    data = p.get()
    platforms.update([(platform_slug,p)])
    return data
    
    
def identifyPlatform(url):
    split_url = url.lower().split('/')
    try:
        platform = (split_url[2].split('.')[0])
    except:
        platform = 'unknown'
    return platform
    

def ticker(running, platforms, ticker_condition, r_queue, r_condition):
    print('Ticker started')
    while running.is_set():
        next_run = None
        for platform_slug in platforms.keys():
            if platforms[platform_slug].available():
                next_run = platforms[platform_slug].timeNextAvailable()
                break # at least one platform ready
            else:
                next = platforms[platform_slug].timeNextAvailable()
                if next_run == None or next < next_run:
                    next_run = next
            
                
        if next_run == None:
            #print("Ticker didn't find anything, sleeping")
            ticker_condition.acquire()
            ticker_condition.wait()
            ticker_condition.release()
            continue
        #else:
        #    print('Ticker found something')
        
        #if logTimes:
        #    t = time.time()
        #    print('Ticker: %s'%(t-startTime))
        
        # sleep until rate/method limits are OK
        now = time.time()
        if next_run > now:
            time.sleep(next_run - now)
        
        for platform_slug in platforms.keys():
            if platforms[platform_slug].available():
                #print('Platforms from Ticker: %s'%platforms)
                data = getData(platform_slug, platforms)
                #print('Got Data:')
                #print(data)
                
                # TODO: 
                # Check the retriever queue or the idle retrievers to make sure
                # that things don't get overloaded. Log when unable to keep up
                r_condition.acquire()
                r_queue.put(data)
                #print('r_queue size: %s'%r_queue.qsize())
                r_condition.notify()
                r_condition.release()
                
    print('Ticker shut down')


def retriever(running, platforms, r_queue, r_condition, get_dict, get_condition, reply_queue, reply_condition):
    print('Retriever started')
    while running.is_set():
        data = {}
        r_condition.acquire()
        if r_queue.qsize() == 0:
            r_condition.wait()
            r_condition.release()
            continue
        else:
            data, platform_needs_limit, method_needs_limit = r_queue.get()
            r_condition.release()
            #if logTimes:
            #    t = time.time()
            #    print('Retriever start: %s'%(t-startTime))
        
        # TODO:
        # Some way to test without using up rate limit? Dummy mode?
        try:
            #print('Retriever - Data pulled: %s'%data)
            r = urllib.request.Request(data['url'], headers={'X-Riot-Token': api_key})
            response = urllib.request.urlopen(r)
            
            #if logTimes:
            #    t = time.time()
            #    print('Retriever end: %s'%(t-startTime))
                
            # handle 200 response
            if platform_needs_limit or method_needs_limit:
                headers = dict(zip(response.headers.keys(), response.headers.values()))
                platform_id = identifyPlatform(data['url'])
                platform = platforms[platform_id]
                if platform_needs_limit:
                    platform.setLimit(headers)
                if method_needs_limit:
                    platform.setEndpointLimit(data['url'], headers)
                platforms.update([(platform_id, platform)])
            
            response_body = response.read()
            if data['method'] == 'GET':
                get_condition.acquire()
                get_dict.update([(data['url'], response_body)])
                get_condition.notify_all() # we don't have a specific response listening
                get_condition.release()
            else:
                data['response'] = response_body
                data['code'] = '200'
                reply_condition.acquire()
                reply_queue.put(data)
                reply_condition.notify()
                reply_condition.release()
            
        except urllib.error.HTTPError as e:
            print('Error from API: %s'%e)
            # TODO: handle the error (500, 403, 404, 429)
        except Exception as e:
            print('Other error: %s'%e)
            print(traceback.format_exc())
            print('URL: %s'%data['url'])
            
        
    print('Retriever shut down')
    
    
def outbound(running, reply_queue, reply_condition):

    while running:
        reply_condition.acquire()
        reply_condition.wait()
        reply_condition.release()
        
        if reply_queue.qsize() == 0:
            continue
        try:
            data = reply_queue.get()
            
            request = urllib.request.Request(data['return_url'], data['response'], method='POST')
            request.add_header('url', data['url'])
            request.add_header('code', data['code'])
            urllib.request.urlopen(request)
        except Exception as e:
            print('Outbound error: %s'%e)
    
def readConfig():
    global config, api_key
    try:
        with open(config_path) as f:
            data = f.read()
            try:
                config = json.loads(data)
                api_key = config['riot_games']['api_key']
            except ValueError as e:
                print('Error reading config file, malformed JSON:')
                print('\t{}'.format(e))
                exit(0)
    except Exception as e:
        print('An error occurred while trying to read the config file:')
        print('\t{}'.format(e))
        exit(0)
    
    
    

    
def main():
    #global server
    global ticker_condition, platforms
    global get_dict, get_condition
    readConfig()
    
    manager = SyncManager()
    manager.start()
    
    running = manager.Event()
    running.set()
    
    platforms = manager.dict()
    ticker_condition = manager.Condition()
    
    r_queue = manager.Queue()
    r_condition = manager.Condition()
    
    # used for HTTP GET requests and their responses
    get_dict = manager.dict()
    get_condition = manager.Condition()
    
    # used for HTTP PUT and POST to issue their responses
    reply_queue = manager.Queue()
    reply_condition = manager.Condition()
    
    # A pool closes, don't want it to close.
    reply_list = []
    reply_args = (running, reply_queue, reply_condition)
    for i in range(config['threads']['return_threads']):
        r = Process(target=outbound, args=reply_args, name='Reply_%s'%i)
        r.deamon = True
        reply_list.append(r)
        r.start()
    
    # A pool closes, don't want it to close.
    r_list = []
    r_args = (running, platforms, r_queue, r_condition, get_dict, get_condition, reply_queue, reply_condition)
    for i in range(config['threads']['api_threads']):
        r = Process(target=retriever, args=r_args, name='Retriever_%s'%i)
        r.deamon = True
        r_list.append(r)
        r.start()
        
    ticking_args = (running, platforms, ticker_condition, r_queue, r_condition)
    ticking = Process(target=ticker, args=ticking_args, name='Ticker')
    ticking.deamon = True
    ticking.start()
    
    
    server = http.server.HTTPServer(
        (config['server']['host'], config['server']['port']), MyHTTPHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping server...')        
    
if __name__ == "__main__":
    main()        
