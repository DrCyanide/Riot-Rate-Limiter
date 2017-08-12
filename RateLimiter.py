import http.server
import json
import multiprocessing
from multiprocessing import Process
from multiprocessing.queues import Empty
from multiprocessing.managers import SyncManager
import time
from collections import deque
import urllib.request as requests

config_path = "config.json"
config = None

# Syncmanager variables
platform_queues = {}

synced = {'condition': None, 'list': None}
requested = {'condition': None, 'list': None}

class MyHTTPHandler(http.server.BaseHTTPRequestHandler): 
    def do_GET(self):
        self.handle_request()

    def do_PUT(self):
        self.handle_request()
        
    def do_POST(self):
        self.handle_request()
        
    def handle_request(self):
        global synced        
        
        security_pass = self.check_security()
        if not security_pass:
            return
        
        data = {}
        data['url'] = self.headers.get('url')
        data['return_url'] = self.headers.get('return_url')
        data['region'], data['endpoint'] = identify_region_endpoint(data['url'])
        
        # acquire requested condition, then add to the api
        
        #sort_lock.acquire()
        #sort_queue.put(data)
        #sort_lock.notify()
        #sort_lock.release()
        
        if self.command.upper() == 'GET' and False: 
            # GET = Synchronous, PUT/POST = Asynchronous
            keep_waiting = True
            while keep_waiting:
                synced['condition'].acquire()
                synced['condition'].wait()
                synced['condition'].release()
            
                for reply in synced['list']:
                    if reply['url'] == data['url']:
                        keep_waiting = False
                        # TODO: Return this reply, then remove it from the list later
                        #       Emphasis on 'later', since it's possible for multiple 
                        #       requests to have the same url
                        #       Add to a cleanup queue?

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
            print('Unauthorized access detected from %s'%IP)
            self.send_response(404)
            self.end_headers()
        return not intruder
        
        
def identify_region_endpoint(url):
    url = url[:url.find('?')].lower() # Remove the query string
    split_url = url.split()
    try:
        region = (split_url[2].split('.')[0])
    except:
        region = 'unknown'
    endpoint = ''
    try:
        if not 'by-name' in split_url:
            for segment in split_url[2:]:
                if not segment.isnumeric():
                    endpoint += segment + '/'
        else:
            endpoint = '/'.join(split_url[2:-1]) # Ignore the player name itself
    except:
        endpoint = 'no endpoint'
    return (region, endpoint)


# Read the rate limit and method limit from a response
def set_rate_limits(platform_id, endpoint, headers):
    global platform_queues
    
    split_limits = []
    split_limits_usage = [] 
    split_methods = []
    split_methods_usage = []
    
    split_lists = [split_limits, split_limits_usage, split_method, split_method_usage]
    split_headers = ['X-App-Rate-Limit', 'X-App-Rate-Limit-Count', 'X-Method-Rate-Limit', 'X-Method-Rate-Limit-Count']
    
    for i in range(len(split_lists)):
        if split_headers[i] in headers:
            split_lists[i] = headers[split_headers[i]].split(',')

    for platform in platform_queues.keys():
        # Add Rate Limit if it doesn't exist for a given platform
        if len(platform_queues[platform]['rate_limits']) == 0:
            for i in range(len(split_limits)):
                limit, seconds = split_limits[i].split(':')
                used = 0
                if platform == platform_id:
                    used = split_limits_usage[i].split(':')[0]
                rate_limit = {'limit': limit, 'seconds': seconds, 'used': used}
                platform_queues[platform]['rate_limits'].append(rate_limit)
                
        # Add Endpoint/Method Limit if it doesn't exist for a given platform
        if not endpoint in platform_queues[platform]['endpoint_limits']['limits']:
            for i in range(len(split_methods)):
                limit, seconds = split_methods[i].split(':')
                used = 0
                if platform == platform_id:
                    used = split_methods_usage[i].split(':')[0]
                method_limit = {'limit': limit, 'seconds': seconds, 'used': used}
                platform_queues[platform]['endpoint_limits']['limits'][endpoint].append(method_limit)
                    
def read_config():
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
    
    
def init_processes():
    global synced, platform_queues
    manager = SyncManager()
    manager.start()
    
    for platform in config['riot_games']['platforms']:
        platform_queues[platform] = {
            'static_queue': manager.Queue(),
            'static_condition': manager.Condition(),
            'static_last_call': time.time(),
            
            'limited_queue': manager.Queue(),
            'limited_condition': manager.Condition(),
            'limited_last_call': time.time(),
            
            'rate_limits':[],
                # {'limit': x, 'seconds': y, 'used': z}
            'endpoint_limits':{'last_call': time.time(), 'limits':[]} # AKA: method limits
                # limits = [{'limit': x, 'seconds': y, 'used': z}]
        }
    
    synced['condition'] = manager.Condition()
    synced['list'] = manager.list()
    
    

    
def main():
    #global server
    read_config()
    init_processes()
    #init_limits()
    
    #start_all()
    server = http.server.HTTPServer((config['server']['host'], config['server']['port']), MyHTTPHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping server...')        
    
if __name__ == "__main__":
    main()        
