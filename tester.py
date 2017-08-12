import json
import time
import urllib.request as requests
from Limit import Limit
from Endpoint import Endpoint
from Platform import Platform

config_path = 'config.json'
target_url = 'https://na1.api.riotgames.com/lol/champion-mastery/v3/champion-masteries/by-summoner/28341307'
server_url = 'http://'

def testLimit():
    limit = Limit()
    assert(limit.ready() == True)
    assert(limit.resetTime() < time.time())
    assert(limit.used == 0)
    limit.use()
    assert(limit.resetTime() < time.time() + 0.0001)
    assert(limit.used == 1)
    
    limit = Limit(seconds=0.1, limit=1, used=1)
    assert(limit.ready() == False)
    assert(limit.used == 1)
    time.sleep(0.1)
    assert(limit.ready() == True)
    assert(limit.used == 0)
    limit.use()
    assert(limit.used == 1)
    
    print('Limit tests pass')
    
def testEndpoint():
    print(Endpoint.identifyEndpoint(target_url))
    endpoint = Endpoint()
    print('Endpoint tests pass')
    
def testPlatform():
    print('Platform tests pass')


def testRateLimiter():
    with open(config_path) as f:
        data = f.read()
        try:
            config = json.loads(data)
            server_url += '%s:%s'%(config['server']['host'], config['server']['port'])
        except ValueError as e:
            print('Error reading config file, malformed JSON:')
            print('\t{}'.format(e))
            exit(0)

    while True:
        input('Press enter to issue request')

        r = requests.Request(server_url)
        r.add_header('url',target_url)
        #r.add_header('return_url', 'http://127.0.0.1')
        #r.add_header('api_name', 'test_1')
        requests.urlopen(r)

if __name__ == '__main__':
    testLimit()
    testEndpoint()
    #testPlatform()