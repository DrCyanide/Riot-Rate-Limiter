import json
import time
import urllib.request as requests
from Limit import Limit
from Endpoint import Endpoint
from Platform import Platform

config_path = 'config.json'
server_connection = 'http://'


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
    summoner_url = 'https://na1.api.riotgames.com/lol/summoner/v3/summoners/by-name/SomeSummonerName'
    endpoint_str = Endpoint.identifyEndpoint(summoner_url)
    assert(endpoint_str == 'lol/summoner/v3/summoners/by-name')
    
    static_url = 'https://na1.api.riotgames.com/lol/static-data/v3/champions?locale=en_US&dataById=false'
    endpoint_str = Endpoint.identifyEndpoint(static_url)
    assert(endpoint_str == 'lol/static-data/v3/champions')
    
    # There was an issue with id's 1 through 9 ending with a '/'
    match_example = 'https://na1.api.riotgames.com/lol/match/v3/matches/'
    for i in range(1, 50):
        url = '%s%s'%(match_example, i)
        assert(Endpoint.identifyEndpoint(url) == 'lol/match/v3/matches')
    
    endpoint = Endpoint()
    assert(endpoint.limitsDefined == False)
    assert(endpoint.count == 0)
    assert(endpoint.available() == False) # No urls
    assert(endpoint.name == '')
    
    endpoint.addURL(summoner_url)
    assert(endpoint.count == 1)
    assert(endpoint.available())
    assert(endpoint.name == 'lol/summoner/v3/summoners/by-name')
    assert(endpoint.get() == summoner_url)
    assert(endpoint.count == 0)
    assert(endpoint.get() == None)
    
    assert_raises(endpoint.addURL, [static_url])
    
    endpoint.addURL(summoner_url)
    endpoint.addURL(summoner_url)
    assert(endpoint.count == 2)
    assert(endpoint.available())
    
    headers = {'X-Method-Rate-Limit':'1:0.1,10:1', 'X-Method-Rate-Limit-Count':'0:0.1,9:1'}
    assert(endpoint.limitsDefined == False)
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
    endpoint.addURL(summoner_url)
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
    assert(platform.get() == (None, True, False))
    
    summoner_url = 'https://na1.api.riotgames.com/lol/summoner/v3/summoners/by-name/SomeSummonerName'
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
    assert(platform.get() == (static_url, True, True))
    assert(platform.count == 1)
    assert(platform.static_count == 0)
    assert(platform.get() == (summoner_url, True, True))
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
    assert(platform.get() == (summoner_url, True, True))
    assert(platform.get() == (champ_mastery_url, True, True))
    assert(platform.get() == (summoner_url, True, True))
    assert(platform.get() == (champ_mastery_url, True, True))
    
    
    headers = {'X-Method-Rate-Limit':'1:0.1,10:1', 
               'X-Method-Rate-Limit-Count':'0:0.1,9:1',
               'X-App-Rate-Limit':'5:0.1,40:1', 
               'X-App-Rate-Limit-Count':'0:0.1,39:1'}
    platform.setLimit(headers)
    platform.setCount(headers)
    assert(platform.rateLimitOK())
    platform.addURL(summoner_url)
    platform.addURL(summoner_url)
    assert(platform.get() == (summoner_url, False, True))
    assert(platform.rateLimitOK() == False)
    assert(platform.get() == (None, False, False))
    
    platform = Platform()
    platform.addURL(summoner_url)
    platform.addURL(summoner_url)
    platform.setLimitAndCount(headers)
    assert(platform.rateLimitOK())
    assert(platform.get() == (summoner_url, False, True))
    assert(platform.rateLimitOK() == False)
    platform.addURL(summoner_url)
    assert(platform.get() == (None, False, False))

   
    platform = Platform()
    platform.addURL(summoner_url)
    platform.addURL(summoner_url)
    platform.setEndpointLimit(summoner_url, headers)
    platform.setEndpointCount(summoner_url, headers)
    assert(platform.get() == (summoner_url, True, False))
    assert(platform.get() == (None, True, False))
    
    platform = Platform()
    platform.addURL(summoner_url)
    platform.setEndpointLimitAndCount(summoner_url, headers)
    assert(platform.get() == (summoner_url, True, False))
    
    platform = Platform()
    platform.addURL(summoner_url)
    platform.setLimitAndCount(headers)
    platform.setEndpointLimitAndCount(summoner_url, headers)
    assert(platform.get() == (summoner_url, False, False))
    
    print('Platform tests pass')


def testScenario():
    print('Starting scenario tests...')
    # Mimic a normal flow
    
    platform = Platform()
    summoner_url = 'https://na1.api.riotgames.com/lol/summoner/v3/summoners/by-name/SomeSummonerName'
    platform.addURL(summoner_url)
    assert(platform.count == 1)
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == summoner_url)
    assert(platform_limit_needed == True)
    assert(endpoint_limit_needed == True)
    
    headers = {'X-Method-Rate-Limit':'1:0.1,10:1', 
               'X-Method-Rate-Limit-Count':'1:0.1,1:1',
               'X-App-Rate-Limit':'5:0.1,40:1', 
               'X-App-Rate-Limit-Count':'1:0.1,1:1'}
    platform.setLimitAndCount(headers)
    platform.setEndpointLimitAndCount(url, headers)
    assert(platform.available() == False) # Method limit hit
    matchlist_url = 'https://na1.api.riotgames.com/lol/match/v3/matchlists/by-account/123456789'
    platform.addURL(matchlist_url)
    assert(platform.available()) # New endpoint without a method limit hit
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == matchlist_url)
    assert(platform_limit_needed == False)
    assert(endpoint_limit_needed == True)
    
    headers = {'X-Method-Rate-Limit':'1:0.1,10:1', 
               'X-Method-Rate-Limit-Count':'1:0.1,1:1',
               'X-App-Rate-Limit':'5:0.1,40:1', 
               'X-App-Rate-Limit-Count':'2:0.1,2:1'}
    platform.setEndpointLimitAndCount(url, headers)
    assert(platform.available() == False) # Method limit hit
    match_example = 'https://na1.api.riotgames.com/lol/match/v3/matches/'
    #print('Generating Matches')
    for matchid in range(1, 50):
        url = '%s%s'%(match_example, matchid)
        #print('%s -> %s'%(url, Endpoint.identifyEndpoint(url)))
        platform.addURL(url)
    assert(platform.count == 49)
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == '%s%s'%(match_example,1))
    assert(platform_limit_needed == False)
    assert(endpoint_limit_needed == True)
    
    headers = {'X-Method-Rate-Limit':'1:0.1,5:1', # Note: 5 per 1 second
               'X-Method-Rate-Limit-Count':'1:0.1,1:1',
               'X-App-Rate-Limit':'5:0.1,40:1', 
               'X-App-Rate-Limit-Count':'3:0.1,3:1'}
    platform.setEndpointLimitAndCount('%s%s'%(match_example,1), headers)
    #print('Checking available')
    #print(platform.getUsage())
    assert(platform.available() == False) # Method limit 1:0.1, 1:1
    time.sleep(0.1) # Time = 0.1
    assert(platform.available())
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == '%s%s'%(match_example,2))
    assert(platform_limit_needed == False)
    assert(endpoint_limit_needed == False)
    
    assert(platform.available() == False) # Method limit 1:0.1, 2:1
    time.sleep(0.1) # Time = 0.2
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == '%s%s'%(match_example,3))
    assert(platform_limit_needed == False)
    assert(endpoint_limit_needed == False)
    
    assert(platform.available() == False) # Method limit 1:0.1, 3:1
    time.sleep(0.1) # Time = 0.3
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == '%s%s'%(match_example,4))
    assert(platform_limit_needed == False)
    assert(endpoint_limit_needed == False)
    
    assert(platform.available() == False) # Method limit 1:0.1, 4:1
    time.sleep(0.1) # Time = 0.4
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == '%s%s'%(match_example,5))
    assert(platform_limit_needed == False)
    assert(endpoint_limit_needed == False)
    
    assert(platform.available() == False) # Method Limit 1:0.1, 5:1
    time.sleep(0.1) # Time = 0.5
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == None)
    assert(platform_limit_needed == False)
    assert(endpoint_limit_needed == False)
    
    assert(platform.available() == False) # Method Limit 0:0.1, 5:1
    time.sleep(0.1) # Time = 0.6
    assert(platform.available() == False) # Method Limit 0:0.1, 5:1
    time.sleep(0.1) # Time = 0.7
    assert(platform.available() == False) # Method Limit 0:0.1, 5:1
    time.sleep(0.1) # Time = 0.8
    assert(platform.available() == False) # Method Limit 0:0.1, 5:1
    time.sleep(0.1) # Time = 0.9
    assert(platform.available() == False) # Method Limit 0:0.1, 5:1
    time.sleep(0.1) # Time = 1.0
    assert(platform.available()) # Method Limit 0:0.1, 0:1
    
    # Check that requests from other platforms still go through just fine without causing a delay
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == '%s%s'%(match_example,6))
    platform.addURL(summoner_url)
    assert(platform.available())
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == summoner_url)
    assert(platform.available() == False)
    time.sleep(0.1)
    url, platform_limit_needed, endpoint_limit_needed = platform.get()
    assert(url == '%s%s'%(match_example,7))
    
    print('First 8 manual tests passed, the rest should be staggered')
    # Automatically continue
    next = 8
    while platform.count > 0:
        url, platform_limit_needed, endpoint_limit_needed = grabWhenReady(platform)
        assert(url == '%s%s'%(match_example, next))
        print(next)
        next += 1
    
    print('Scenario tests pass')
    
def grabWhenReady(platform):
    next = platform.timeNextAvailable()
    if next == None:
        print('No next time available, no records!')
        return 
    if next > time.time():
        time.sleep(next - time.time())
    return platform.get()
    
    
def readConfig():
    with open(config_path) as f:
        data = f.read()
        try:
            config = json.loads(data)
            return config
        except ValueError as e:
            print('Error reading config file, malformed JSON:')
            print('\t{}'.format(e))
            exit(0)
    
def testRateLimiter():
    config = readConfig()
    server_url = '%s%s:%s'%(server_connection, config['server']['host'], config['server']['port'])

    output = input('Display output? (y/n, default=n): ')
    if len(output) > 0 and 'y' in output.lower() :
        output = True
    else:
        output = False

    while True:
        input('Press enter to issue request')

        r = requests.Request(server_url)
        r.add_header('X-Url',target_url)
        response = requests.urlopen(r)
        if output:
            print(response.read().decode('utf-8'))


def issueRequest(server_url, target_url, method='GET', response_url=''):
    r = requests.Request(server_url, method=method)
    r.add_header('X-Url', target_url)
    r.add_header('X-Return-Url', response_url)
    try:
        response = requests.urlopen(r)
        return response
    except Exception as e:
        return e
        
def testWithFakeServer():
    config = readConfig()
    server_url = 'http://%s:%s'%(config['server']['host'], int(config['server']['port']))
    test_server_url = 'http://%s:%s'%(config['server']['host'], int(config['server']['port']) + 1)
    
    while True:
        try:
            print('1) Issue GET request')
            print('2) Issue POST requests')
            print('3) Set Test Server mode')
            choice = int(input('Choice: '))
            if choice == 1: # GET
                # TODO: Allow multiple fake commands to be issued
                print('Firing GET commands.\nPress CTRL+C to return to the previous menu')
                
                try:
                    while True:
                        input('Press enter to issue query')
                        response = issueRequest(server_url, '%s/some/path/'%test_server_url, 'GET', test_server_url)
                        print(response.read().decode('utf-8'))

                except KeyboardInterrupt:
                    print()
                    continue
                except Exception as e:
                    print('Error while handling request, aborting.\n\t%s'%e)
            elif choice == 2: # POST
                print('Firing POST commands. Check test_server.py for responses.\nPress CTRL+C to return to the previous menu')
                
                try:
                    while True:
                        input('Press enter to issue query')
                        response = issueRequest(server_url, '%s/some/path/'%test_server_url, 'POST', test_server_url)
                except KeyboardInterrupt:
                    print()
                    continue
                except Exception as e:
                    print('Error while handling request, aborting.\n\t%s'%e)
            elif choice == 3: # PUT mode
                pass
            else:
                print('Unrecognized input')
            
        except KeyboardInterrupt:
            print()
            break
        
if __name__ == '__main__':
    print('1) Regression Testing')
    print('2) Live Testing')
    choice = input('Test Mode: ')
    if choice == '1':
        testLimit()
        testEndpoint()
        testPlatform()
        testScenario()
    elif choice == '2':
        print('Please ensure that RateLimiter.py and tester_server are running in seprate consoles')
        #testRateLimiter()
        testWithFakeServer()
    
