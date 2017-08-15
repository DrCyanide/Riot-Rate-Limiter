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

platform_lock = Lock()
#platforms = {}
platforms = None

ticker_condition = None

synced = {'condition': None, 'list': None}
requested = {'condition': None, 'list': None}

class MyHTTPHandler(http.server.BaseHTTPRequestHandler): 
    def do_GET(self):
        self.handleRequest()

    def do_PUT(self):
        self.handleRequest()
        
    def do_POST(self):
        self.handleRequest()
        
    def handleRequest(self):
        global synced        
        
        security_pass = self.checkSecurity()
        if not security_pass:
            return
        
        data = {}
        data['url'] = self.headers.get('url')
        data['return_url'] = self.headers.get('return_url')
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
        print('%s count: %s'%(platform_slug, platforms[platform_slug].count))
        
        # Notify ticker
        ticker_condition.acquire()
        ticker_condition.notify()
        ticker_condition.release()
        
        #if self.command.upper() == 'GET' and False: 
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
    print('Adding data to %s'%platform_slug)
    print('Add before: %s'%platforms)
    
    p = platforms[platform_slug]
    p.addData(data)
    platforms.update([(platform_slug,p)])
    print('Add after: %s'%platforms)
    
def getData(platform_slug, platforms):
    # See addData comment
    #global platforms
    print('Getting data from %s'%platform_slug)
    print('Get before: %s'%platforms)
    
    p = platforms[platform_slug]
    data = p.get()
    platforms.update([(platform_slug,p)])
        
def identifyPlatform(url):
    split_url = url.lower().split('/')
    try:
        platform = (split_url[2].split('.')[0])
    except:
        platform = 'unknown'
    return platform
    
          

def Ticker(running, platforms, ticker_condition):
    print('Ticker Started')
    while running.is_set():
        next_run = None
        print('Platforms: %s'%platforms)
        for platform_slug in platforms.keys():
            if platforms[platform_slug].available():
                print('%s available'%platform_slug)
            else:
                print('%s not available'%platform_slug)
            next = platforms[platform_slug].timeNextAvailable()
            if next_run == None or next < next_run:
                next_run = next
                # TODO: Skip the rest if next_run is now, handle that
                
        if next_run == None:
            print("Ticker didn't find anything, sleeping")
            ticker_condition.acquire()
            ticker_condition.wait()
            ticker_condition.release()
            continue
        else:
            print('Ticker found something')
        
        now = time.time()
        if next_run > now:
            time.sleep(next_run - now)
        
        for platform_slug in platforms.keys():
            if platforms[platform_slug].available():
                print('Platforms from Ticker: %s'%platforms)
                #data = getData(platform_slug)
                data = getData(platform_slug, platforms)
                print('Got Data: %s'%data)
                
    print('Ticker shutting down')

def readConfig():
    global config
    try:
        with open(config_path) as f:
            data = f.read()
            try:
                config = json.loads(data)
            except ValueError as e:
                print('Error reading config file, malformed JSON:')
                print('\t{}'.format(e))
                exit(0)
    except Exception as e:
        print('An error occurred while trying to read the config file:')
        print('\t{}'.format(e))
        exit(0)
    
    
    
    
#def init_processes():
#    global synced, platform_queues
#    manager = SyncManager()
#    manager.start()
#    
#    for platform in config['riot_games']['platforms']:
#        platform_queues[platform] = {
#            'static_queue': manager.Queue(),
#            'static_condition': manager.Condition(),
#            'static_last_call': time.time(),
#            
#            'limited_queue': manager.Queue(),
#            'limited_condition': manager.Condition(),
#            'limited_last_call': time.time(),
#            
#            'rate_limits':[],
#                # {'limit': x, 'seconds': y, 'used': z}
#            'endpoint_limits':{'last_call': time.time(), 'limits':[]} # AKA: method limits
#                # limits = [{'limit': x, 'seconds': y, 'used': z}]
#        }
#    
#    synced['condition'] = manager.Condition()
#    synced['list'] = manager.list()
    
    

    
def main():
    #global server
    global ticker_condition, platforms
    readConfig()
    #init_processes()
    #init_limits()
    
    manager = SyncManager()
    manager.start()
    running = manager.Event()
    running.set()
    platforms = manager.dict()
    ticker_condition = manager.Condition()
    
    ticking = Process(target=Ticker, args=(running, platforms, ticker_condition))
    ticking.deamon = True
    ticking.start()
    
    #start_all()
    server = http.server.HTTPServer((config['server']['host'], config['server']['port']), MyHTTPHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping server...')        
    
if __name__ == "__main__":
    main()        
