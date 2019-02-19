import http.server
import json
from multiprocessing import Lock
from multiprocessing import Process
from multiprocessing.managers import SyncManager
import time
import datetime
import urllib.request
import urllib.error
import traceback
import sys

from Platform import Platform

config_path = 'config.json'
config = None
api_key = ''

platform_lock = Lock()
platforms = None

ticker_condition = None
get_dict = None
get_condition = None

logTimes = False
startTime = None


def CreateSyncHTTPHandler(manager):
    class MyHTTPHandler(http.server.BaseHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super(MyHTTPHandler, self).__init__(*args, **kwargs)
            self.manager = manager

        def do_OPTIONS(self):  # For CORS requests
            self.send_response(200, "ok")
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS')

            # self.send_header('Access-Control-Allow-Origin', '*')  wasn't working
            allowed_headers = ["X-Url", "X-Return-Url", "Content-Type", "X-Info"]
            for header in allowed_headers:
                self.send_header("Access-Control-Allow-Headers", header)
            self.end_headers()

        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            http.server.BaseHTTPRequestHandler.end_headers(self)

        def do_GET(self):
            self.handle_request()

        def do_PUT(self):
            self.handle_request()
            
        def do_POST(self):
            self.handle_request()
            
        def handle_request(self):
            global platforms
            global startTime
            security_pass = self.check_security()
            if not security_pass:
                return
            
            if logTimes:
                startTime = time.time()
                print('Start: %s' % startTime)
            
            data = {}
            data['url'] = self.headers.get('X-Url')
            if data['url']is None:
                self.send_response(400)
                self.wfile.write(('No X-Url header detected\n').encode('utf-8'))
                self.end_headers()
                return
            
            data['method'] = self.command.upper()
            data['return_url'] = self.headers.get('X-Return-Url')
            data['info'] = self.headers.get('X-Info')

            # The Riot API has no commands where you just send data, so no return_url = error
            if  data['method'] in ['PUT','POST'] and (data['return_url'] is None):
                self.send_response(404)
                self.wfile.write(('No X-Return-Url specified on a %s request\n' % data['method']).encode('utf-8'))
                self.end_headers()
                return
                
            platform_slug = identify_platform(data['url'])
            if platform_slug in platforms.keys():
                platform_lock.acquire()
                platforms, added = add_data(data, platforms)
                platform_lock.release()
            else:
                platform_lock.acquire()
                #platforms[platform_slug] = Platform(manager, slug=platform_slug, )
                platforms.update([(platform_slug, Platform(manager, slug=platform_slug, endpoints=config['riot_games']['endpoints']))])  
                platforms, added = add_data(data, platforms)
                platform_lock.release()
            # print('%s count: %s'%(platform_slug, platforms[platform_slug].count))
            
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
                            print('End: %s' % (t-startTime))
    
                        # TODO: Cleanup retrieved data so it doesn't keep taking up memory
                        return
                        
            self.send_response(200)
            self.end_headers()

        def check_security(self):
            intruder = False
            IP = self.address_string()
            if len(config['security']['whitelist']) > 0:
                if not IP in config['security']['whitelist']:
                    intruder = True
            if len(config['security']['blacklist']) > 0:
                if IP in config['security']['blacklist']:
                    intruder = True
            if intruder:
                print('Unauthorized access detected from %s' % IP)
                self.send_response(404)
                self.end_headers()
            return not intruder

    return MyHTTPHandler

    
def add_data(data, platforms, at_front=False, max_attempts=3):
    # Returns platforms and if it was added
    # syncmanager dicts require the update() command to be run
    # before anything will be saved. The normal 'addData()' method
    # won't result in the object being pickled again, thus it will
    # look like there was no update.
    if 'attempts' not in data:
        data['attempts'] = 0
    data['attempts'] += 1
    
    if data['attempts'] >= max_attempts:
        return platforms, False
        
    platform_slug = identify_platform(data['url'])
    platform = platforms[platform_slug]
    platform.add_data(data, at_front)
    platforms.update([(platform_slug,platform)])
    print('Added data (total in platform %s: %s)' % (platform_slug, platforms[platform_slug].count))

    return platforms, True
    
    
def get_data(platform_slug, platforms):
    # See add_data comment
    platform = platforms[platform_slug]
    data = platform.get()
    platforms.update([(platform_slug,platform)])
    print('Removed data (total in platform %s: %s)' % (platform_slug, platforms[platform_slug].count))
    return platforms, data
    
    
def identify_platform(url):
    split_url = url.lower().split('/')
    try:
        platform = (split_url[2].split('.')[0])
    except:
        platform = 'unknown'
    return platform


def handle_return(data, get_condition, get_dict, reply_condition, reply_queue):
    try:
        if data['method'] == 'GET':
            get_condition.acquire()
            get_dict.update([(data['url'], data['response'])])
            get_condition.notify_all()  # we don't have a specific response listening
            get_condition.release()
        else:
            reply_condition.acquire()
            reply_queue.put(data)
            reply_condition.notify()
            reply_condition.release()
    except Exception as e:
        print('Exception in handle_return')
        print(e)


def notify_if_not_done(platforms, ticker_condition):
    for slug in platforms.keys():
        platform = platforms[slug]
        if platform.count > 0:
            ticker_condition.acquire()
            ticker_condition.notify()
            ticker_condition.release()
            return
    # print('No remaining requests')


def handle_response(response, data, platforms, platform_lock, reply_condition, reply_queue, get_condition, get_dict, ticker_condition):
    headers = dict(response.headers)
    platform_slug = identify_platform(data['url'])

    platform_lock.acquire()
    platform = platforms[platform_slug]
    # if '120' in platform.platform_limits:
    #     print("Existing Limit: %s" % (platform.platform_limits['120'].used))
    platform.handle_response_headers(data['url'], headers)  # Handles delays on it's own
    platforms.update([(platform_slug,platform)])
    platform_lock.release()

    data['response'] = response.read()
    data['code'] = response.code

    notify_if_not_done(platforms, ticker_condition)
    if response.code == 200:
        print('200 return')
        handle_return(data, get_condition, get_dict, reply_condition, reply_queue)
    else:
        print('%s return' % response.code)
    # TODO: handle the error (500, 403, 404, 429, 401)
    if response.code == 429:  # Rate Limit Issue
        platform_lock.acquire()
        print('429 debugging - Available: %s Used: %s Limit Ready: %s' % (platform.available(), platform.platform_limits['120'].used, platform.platform_limits['120'].ready()))
        platforms, added = add_data(data, platforms, at_front=True)
        platform_lock.release()

        if not added:
            handle_return(data, get_condition, get_dict, reply_condition, reply_queue)

        else:
            #print('Retrying!')
            notify_if_not_done(platforms, ticker_condition)

    # elif e.code == 500:
    #   Internal server issue
    #   platform.handleDelay(url, headers)
    #   retry
    # elif e.code == 401:
    #   Invalid API Key
    #   stop?
    # elif e.code == 403:
    #   Blacklisted or Internal server issue
    #   retry?

    else:
        # Unknown error
        handle_return(data, get_condition, get_dict, reply_condition, reply_queue)

    return platforms


def poker(running, platforms, ticker_condition):
    print('Poker started')
    try:
        while running.is_set():
            time.sleep(config['poke']['delay'])
            notify_if_not_done(platforms, ticker_condition)

    except KeyboardInterrupt:
        # Manual Shutdown
        pass
    print('Poker shut down')


def ticker(running, platforms, ticker_condition, r_queue, r_condition):
    print('Ticker started')
    try:
        while running.is_set():
            # print('Ticker scan')
            run_now = False
            if platforms.keys() == None:
                print("No platform slugs yet")
                ticker_condition.acquire()
                ticker_condition.wait()
                ticker_condition.release()
                continue

            for platform_slug in platforms.keys():
                platform_lock.acquire()
                platform = platforms[platform_slug]
                if platform.available():
                    run_now = True
                    platform_lock.release()
                    break
                platform_lock.release()

            if not run_now:
                # print("Ticker didn't find anything, sleeping")

                ticker_condition.acquire()
                ticker_condition.wait()
                ticker_condition.release()
                continue
            #('Ticker found something!')
            
            # sleep until rate/method limits are OK
            # now = time.time()
            # if next_run > now:
            #     time.sleep(next_run - now)
            # else:
            #     print('No sleep!\n\tNow: %s\n\tNext:%s' % (now, next_run))
            
            for platform_slug in platforms.keys():
                platform_lock.acquire()
                # print('Checking %s...' % platform_slug)
                if platforms[platform_slug].available():
                    # print('Request debugging - Available: %s Used: %s Limit Ready: %s' % (
                    #     platforms[platform_slug].available(), 
                    #     -1 if len(platforms[platform_slug].platform_limits) == 0 else platforms[platform_slug].platform_limits['120'].used,
                    #     -1 if len(platforms[platform_slug].platform_limits) == 0 else platforms[platform_slug].platform_limits['120'].ready()
                    #     )
                    # )
                    platforms, data = get_data(platform_slug, platforms)
                    # TODO: 
                    # Check the retriever queue or the idle retrievers to make sure
                    # that things don't get overloaded. Log when unable to keep up

                    r_condition.acquire()
                    r_queue.put(data)
                    r_condition.notify()
                    r_condition.release()
                platform_lock.release()
        print('Ticker shut down')
        
    except KeyboardInterrupt:
        # Manual Shutdown
        pass


def retriever(running, api_key, platforms, r_queue, r_condition, get_dict, get_condition, reply_queue, reply_condition, ticker_condition, platform_lock):
    print('Retriever started')
    try:
        while running.is_set():
            data = {}
            r_condition.acquire()
            if r_queue.qsize() == 0:
                r_condition.wait()
                r_condition.release()
                continue
            else:
                data = r_queue.get()
                r_condition.release()

            if data == None:
                # ran into a crash when r_queue gave back None.
                continue

            # TODO:
            # Some way to test without using up rate limit? Dummy mode?
            try:
                print('%s - Requesting %s' % (datetime.datetime.now().strftime('%m-%d-%y %H:%M:%S'), data['url']))
                r = urllib.request.Request(data['url'], headers={'X-Riot-Token': api_key})
                response = urllib.request.urlopen(r)
                platforms = handle_response(response, data, platforms, platform_lock, reply_condition, reply_queue, get_condition, get_dict, ticker_condition)

            except urllib.error.HTTPError as e:
                print('Error from API: %s' % e)
                platforms = handle_response(e, data, platforms, platform_lock, reply_condition, reply_queue,
                                            get_condition, get_dict, ticker_condition)

            except urllib.error.URLError as e:
                print('Invalid URL: %s' % data['url'])
                print('Reason: %s' % e.reason)
                data['code'] = 404
                data['response'] = 'Invalid URL'.encode('utf-8')
                handle_return(data, get_condition, get_dict, reply_condition, reply_queue)

            except Exception as e:
                # TODO: Have this return a 500 code in the response for this server, not a 500 from Riot's servers
                print('Other error: %s' % e)
                print(traceback.format_exc())
                print('URL: %s' % data['url'])
                data['code'] = 500
                data['response'] = 'Rate Limiter server error'.encode('utf-8')
                handle_return(data, get_condition, get_dict, reply_condition, reply_queue)

        print('Retriever shut down')
    except KeyboardInterrupt:
        # Manual Shutdown
        pass   
    
    
def outbound(running, reply_queue, reply_condition):
    try:
        while running:
            if reply_queue.qsize() == 0:
                reply_condition.acquire()
                reply_condition.wait()
                reply_condition.release()
            
            if reply_queue.qsize() == 0:
                continue
            try:
                data = reply_queue.get()
                
                request = urllib.request.Request(data['return_url'], data['response'], method='POST')
                request.add_header('X-Url', data['url'])
                request.add_header('X-Code', '%s' % data['code'])
                if data['info'] is not None:
                    request.add_header('X-Info', data['info'])
                # print('Sending data to app for URL "%s"'% data['url'])
                urllib.request.urlopen(request)
                # print('App accepted data')
            except Exception as e:
                print('Outbound error: %s' % e)
    except KeyboardInterrupt:
        # Manual Shutdown
        pass


def read_config():
    global config, api_key
    try:
        with open(config_path) as f:
            data = f.read()
            try:
                config = json.loads(data)
                api_key = config['riot_games']['api_key'].strip()
            except ValueError as e:
                print('Error reading config file, malformed JSON:')
                print('\t{}'.format(e))
                exit(0)
    except Exception as e:
        print('An error occurred while trying to read the config file:')
        print('\t{}'.format(e))
        exit(0)
    

def main():
    # global server
    global ticker_condition, platforms
    global get_dict, get_condition

    # Only works with 3.6+, checking version
    version = sys.version.split(' ')[0].split('.')
    invalid = False
    if int(version[0]) < 3:
        invalid = True
    elif int(version[0]) == 3:
        if int(version[1]) < 6:
            invalid = True
    if invalid:
        print('Invalid version of Python. Requires Python 3.6 or newer')
        return

    read_config()
    
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
    r_args = (running, api_key, platforms, r_queue, r_condition, get_dict, get_condition, reply_queue, reply_condition, ticker_condition, platform_lock)
    for i in range(config['threads']['api_threads']):
        r = Process(target=retriever, args=r_args, name='Retriever_%s'%i)
        r.deamon = True
        r_list.append(r)
        r.start()
        
    ticking_args = (running, platforms, ticker_condition, r_queue, r_condition)
    ticking = Process(target=ticker, args=ticking_args, name='Ticker')
    ticking.deamon = True
    ticking.start()

    poking_args = (running, platforms, ticker_condition)
    poking = Process(target=poker, args=poking_args, name='Poker')
    poking.daemon = True
    poking.start()

    handler = CreateSyncHTTPHandler(manager)
    #server = http.server.HTTPServer( (config['server']['host'], config['server']['port']), MyHTTPHandler)
    server = http.server.HTTPServer( (config['server']['host'], config['server']['port']), handler)
    # server.set_manager(manager) # Need another way to pass this in, since HTTPServer doesn't have it...
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping server...')        


if __name__ == "__main__":
    main()        
