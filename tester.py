import json
import time
import urllib.request as requests
from Limit import Limit
from Endpoint import Endpoint
from Platform import Platform

config_path = 'config.json'
target_url = 'https://na1.api.riotgames.com/lol/champion-mastery/v3/champion-masteries/by-summoner/28341307'
server_url = 'http://'


def assert_raises(function, args=[]):
    exception_test_pass = True
    try:
        function(*args)
        exception_test_pass = False
    except:
        pass
    if not exception_test_pass:
        raise Exception('assert_raises failed for %s, %s'%(function, args))


def testLimit():
    limit = Limit()
    assert(limit.ready())
    assert(limit.getResetTime() < time.time())
    assert(limit.used == 0)
    limit.use()
    assert(limit.getResetTime() < time.time() + 0.0001)
    assert(limit.used == 1)
    
    limit = Limit(seconds=0.1, limit=1, used=1)
    assert(limit.ready() == False)
    assert(limit.used == 1)
    time.sleep(0.1)
    assert(limit.ready())
    assert(limit.used == 0)
    limit.use()
    assert(limit.used == 1)
    
    print('Limit tests pass')
    
    
def testEndpoint():
    summoner_url = 'https://na1.api.riotgames.com/lol/summoner/v3/summoners/by-name/DrCyanide'
    endpoint_str = Endpoint.identifyEndpoint(summoner_url)
    assert(endpoint_str == 'lol/summoner/v3/summoners/by-name')
    
    static_url = 'https://na1.api.riotgames.com/lol/static-data/v3/champions?locale=en_US&dataById=false'
    endpoint_str = Endpoint.identifyEndpoint(static_url)
    assert(endpoint_str == 'lol/static-data/v3/champions')
    
    endpoint = Endpoint()
    assert(endpoint.limitsDefined == False)
    assert(endpoint.count == 0)
    assert(endpoint.available())
    assert(endpoint.name == '')
    
    endpoint.add(summoner_url)
    assert(endpoint.count == 1)
    assert(endpoint.available())
    assert(endpoint.name == 'lol/summoner/v3/summoners/by-name')
    assert(endpoint.get() == summoner_url)
    assert(endpoint.count == 0)
    assert(endpoint.get() == None)
    
    assert_raises(endpoint.add, [static_url])
    
    endpoint.add(summoner_url)
    endpoint.add(summoner_url)
    assert(endpoint.count == 2)
    assert(endpoint.available())
    
    headers = {'X-Method-Rate-Limit':'1:0.1,10:1', 'X-Method-Rate-Limit-Count':'0:0.1,9:1'}
    endpoint.setLimit(headers)
    assert(endpoint.available())
    assert(endpoint.limitsDefined)
    assert(endpoint.get() == summoner_url)
    assert(endpoint.get() == None) # Exceeded limit, returned nothing
    assert(endpoint.getResetTime() > time.time() + 0.01)
    time.sleep(0.1)
    assert(endpoint.getResetTime() < time.time())
    
    endpoint.setCount(headers)
    assert(endpoint.available())
    endpoint.add(summoner_url)
    assert(endpoint.get() == summoner_url)
    assert(endpoint.available() == False)
    assert(endpoint.get() == None) # Exceeded limit, returned nothing
    time.sleep(0.1)
    assert(endpoint.available() == False)
    time.sleep(0.9)
    assert(endpoint.available())
    
    print('Endpoint tests pass')
    
    
def testPlatform():
    platform = Platform()
    assert(platform.rateLimitOK())
    assert(platform.hasURL() == False)
    assert(platform.available() == False) # no URLS
    assert(platform.timeNextAvailable() == None)
    assert(platform.count == 0)
    assert(platform.getURL() == (None, True, False))
    
    summoner_url = 'https://na1.api.riotgames.com/lol/summoner/v3/summoners/by-name/DrCyanide'
    platform.addURL(summoner_url)
    assert(platform.count == 1)
    assert(platform.static_count == 0)
    assert(platform.limited_count == 1)
    assert(platform.timeNextAvailable() < time.time())
    assert(platform.available())
    
    static_url = 'https://na1.api.riotgames.com/lol/static-data/v3/champions?locale=en_US&dataById=false'
    platform.addURL(static_url)
    assert(platform.count == 2)
    assert(platform.static_count == 1)
    assert(platform.limited_count == 1)
    assert(platform.timeNextAvailable() < time.time())
    assert(platform.available())
    
    # When two are present, static should be pulled first
    assert(platform.getURL() == (static_url, True, True))
    assert(platform.count == 1)
    assert(platform.static_count == 0)
    assert(platform.getURL() == (summoner_url, True, True))
    assert(platform.count == 0)
    
    platform = Platform()
    champ_mastery_url = 'https://na1.api.riotgames.com/lol/champion-mastery/v3/champion-masteries/by-summoner/28341307'
    platform.addURL(summoner_url)
    platform.addURL(summoner_url)
    platform.addURL(champ_mastery_url)
    platform.addURL(champ_mastery_url)
    assert(platform.count == 4)
    assert(platform.last_limited_endpoint == '')
    # summoner_url was added first, so that endpoint gets pulled first
    # it then rotates to champ_mastery_url, the next endpoint added
    assert(platform.getURL() == (summoner_url, True, True))
    assert(platform.getURL() == (champ_mastery_url, True, True))
    assert(platform.getURL() == (summoner_url, True, True))
    assert(platform.getURL() == (champ_mastery_url, True, True))
    
    
    headers = {'X-Method-Rate-Limit':'1:0.1,10:1', 'X-Method-Rate-Limit-Count':'0:0.1,9:1',
               'X-App-Rate-Limit':'5:0.1,40:1', 'X-App-Rate-Limit-Count':'0:0.1,39:1'}
    platform.setLimit(headers)
    platform.setCount(headers)
    assert(platform.rateLimitOK())
    platform.addURL(summoner_url)
    platform.addURL(summoner_url)
    assert(platform.getURL() == (summoner_url, False, True))
    assert(platform.rateLimitOK() == False)
    assert(platform.getURL() == (None, False, False))
    
    platform = Platform()
    platform.addURL(summoner_url)
    platform.addURL(summoner_url)
    platform.setLimitAndCount(headers)
    assert(platform.rateLimitOK())
    assert(platform.getURL() == (summoner_url, False, True))
    assert(platform.rateLimitOK() == False)
    platform.addURL(summoner_url)
    assert(platform.getURL() == (None, False, False))
    
    
    platform = Platform()
    platform.addURL(summoner_url)
    platform.setEndpointLimit(summoner_url, headers)
    platform.setEndpointCount(summoner_url, headers)
    assert(platform.getURL() == (None, True, False))
    platform = Platform()
    platform.addURL(summoner_url)
    platform.setEndpointLimitAndCount(summoner_url, headers)
    assert(platform.getURL() == (None, True, False))
    
    platform = Platform()
    platform.addURL(summoner_url)
    platform.setLimitAndCount(headers)
    platform.setEndpointLimitAndCount(summoner_url, headers)
    assert(platform.getURL() == (None, False, False))
    
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
    testPlatform()
    # testRateLimiter()
    