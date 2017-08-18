import http.server
import json
import multiprocessing
from multiprocessing import Lock
from multiprocessing import Process
from multiprocessing.queues import Empty
from multiprocessing.managers import SyncManager
import time
from collections import deque
import urllib.request as requests

from Platform import Platform

config_path = "config.json"
config = None
api_key = ''

platform_lock = Lock()
#platforms = {}
platforms = None

ticker_condition = None


class MyHTTPHandler(http.server.BaseHTTPRequestHandler): 
    def do_GET(self):
        self.handleRequest()

    def do_PUT(self):
        self.handleRequest()
        
    def do_POST(self):
        self.handleRequest()
        
    def handleRequest(self):
        security_pass = self.checkSecurity()
        if not security_pass:
            return
        
        data = {}
        data['url'] = self.headers.get('url')
        data['method'] = self.command.upper()
        data['return_url'] = self.headers.get('return_url')
        # TODO: If method == PUT/POST, it needs return_url.
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
        
        #if data['method'] == 'GET': 
        #    # GET = Synchronous, PUT/POST = Asynchronous
        #    keep_waiting = True
        #    while keep_waiting:
        #        synced['condition'].acquire()
        #        synced['condition'].wait()
        #        synced['condition'].release()
        #    
        #        for reply in synced['list']:
        #            if reply['url'] == data['url']:
        #                keep_waiting = False
        #                # TODO: Return this reply, then remove it from the list later
        #                #       Emphasis on 'later', since it's possible for multiple 
        #                #       requests to have the same url
        #                #       Add to a cleanup queue?
        #
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
        
        # sleep until rate/method limits are OK
        now = time.time()
        if next_run > now:
            time.sleep(next_run - now)
        
        for platform_slug in platforms.keys():
            if platforms[platform_slug].available():
                #print('Platforms from Ticker: %s'%platforms)
                data, platform = getData(platform_slug, platforms)
                #print('Got Data:')
                #print(data)
                
                # TODO: 
                # Check the retriever queue or the idle retrievers to make sure
                # that things don't get overloaded. Log when unable to keep up
                r_condition.acquire()
                r_queue.put(data)
                print('r_queue size: %s'%r_queue.qsize())
                r_condition.notify()
                r_condition.release()
                
    print('Ticker shut down')


def retriever(running, platforms, r_queue, r_condition):
    print('Retriever started')
    while running.is_set():
        data = {}
        r_condition.acquire()
        if r_queue.qsize() == 0:
            r_condition.wait()
            r_condition.release()
        else:
            data = retriver_queue.pop()
            r_condition.release()
        
        # TODO:
        # Create the request, adding the rate limit key to the headers
        # Some sort of way for me to test without using up rate limit?
        try:
            print('Data pulled: %s'%data)
            #r = urllib.request.Request(data['url'], headers={'api_key': api_key})
            #response = urllib.request.urlopen(r)
            # TODO: handle the 200
            
        except Exception as e:
            print('Error! %s'%e)
            # TODO: handle the error (500, 403, 404, 429)
        
    print('Retriever shut down')
    
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
    readConfig()
    
    manager = SyncManager()
    manager.start()
    
    running = manager.Event()
    running.set()
    
    platforms = manager.dict()
    ticker_condition = manager.Condition()
    
    r_queue = manager.Queue()
    r_condition = manager.Condition()
    
    response_queue = manager.Queue() # used for PUT/POST requests
    sync_data = manager.dict() # used for the GET requests
    
    #TODO:
    # start responder
    
    #TODO: convert to pool
    r_pool = Pool(processes=config['threads']['api_threads'])
    r_args = (running, platforms, r_queue, r_condition)
    #retrieving = Process(target=retriever, args=r_args, deamon=True, name='Retriever')
    #retrieving.start()
    r_pool.apply_async(retriever, args=r_args)
    
    ticking_args = (running, platforms, ticker_condition, r_queue, r_condition)
    ticking = Process(target=ticker, args=ticking_args, deamon=True, name='Ticker')
    ticking.start()
    
    #start_all()
    server = http.server.HTTPServer(
        (config['server']['host'], config['server']['port']), MyHTTPHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping server...')        
    
if __name__ == "__main__":
    main()        
