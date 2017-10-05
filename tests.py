import unittest
import copy
import json
import time
import urllib.request as requests
from Limit import Limit
from Endpoint import Endpoint
from Platform import Platform

config_path = 'config.json'
server_connection = 'http://'
time_precision = 2 # 3 normally works on my slow computer, but sometimes fails, so I settled on 2

summoner_url_template = 'https://na1.api.riotgames.com/lol/summoner/v3/summoners/by-name/{name}'
match_url_template = 'https://na1.api.riotgames.com/lol/match/v3/matches/{matchid}'
static_champions_url = 'https://na1.api.riotgames.com/lol/static-data/v3/champions?dataById=false'
static_champion_url = 'https://na1.api.riotgames.com/lol/static-data/v3/champions/{id}'
static_summonerspells_url = 'https://na1.api.riotgames.com/lol/static-data/v3/summoner-spells?dataById=false'
static_summonerspell_url = 'https://na1.api.riotgames.com/lol/static-data/v3/summoner-spells/{id}'
static_items_url = 'https://na1.api.riotgames.com/lol/static-data/v3/items'
fake_name = 'BillyBob'

headers = {
            'Connection': 'keep-alive', 
            'transfer-encoding': 'chunked', 
            'X-Method-Rate-Limit': '270:60', 
            'Vary': 'Accept-Encoding', 
            'Access-Control-Allow-Headers': 'Content-Type', 
            'X-NewRelic-App-Data': 'PxQFWFFSDwQTV1hXBggDV1QTGhE1AwE2QgNWEVlbQFtcC2VOchRAFgtba04hJmweXAEABUJUGhBXHFFWFicPDnwHWQVNXWRdQAxNCF4PQCQLRGQUCw5XXVUWQ04HHwdKVB8HAlteU1IIVhRPCRQWC1EHWlEGUVJQBw8BVANQWhEcAgAORFRq', 
            'X-App-Rate-Limit': '100:120,20:1', 
            'Access-Control-Allow-Origin': '*', 
            'Date': 'Wed, 20 Sep 2017 02:13:18 GMT', 
            'Content-Type': 'application/json;charset=utf-8', 
            'Access-Control-Allow-Methods': 'GET, POST, DELETE, PUT', 
            'X-Method-Rate-Limit-Count': '1:60', 
            'Content-Encoding': 'gzip', 
            'X-App-Rate-Limit-Count': '1:120,1:1'
        }


def rtime(timestamp=None, precision=time_precision):
    # precision 3 normally works on my computer, but occassionally fails.
    # I'd rather not have occassional false failures
    if timestamp == None:
        timestamp = time.time()
    return round(timestamp, precision)


class TestLimit(unittest.TestCase):
    def setUp(self):
        self.seconds = 0.1
        self.limit_count = 1
        self.limit = Limit(seconds=self.seconds, cap=self.limit_count, used=0)
        
    def test_init(self):
        self.assertRaises(Exception, Limit)
        self.assertTrue(self.limit.ready())
        self.assertEqual(rtime(self.limit.nextReady()), rtime(time.time() + self.seconds))
        self.assertEqual(self.limit.used, 0)
        
    def test_use(self):
        self.limit.use()
        self.assertEqual(rtime(self.limit.nextReady()), rtime(time.time() + self.seconds))
        self.assertEqual(self.limit.used, 1)
        self.limit.use()
        self.limit.use()
        self.assertEqual(self.limit.used, 3)
        
    def test_ready(self):
        start_time = time.time()
        self.seconds = 0.1
        self.limit = Limit(seconds=self.seconds, cap=1, used=1)
        self.assertFalse(self.limit.ready())
        self.assertEqual(self.limit.used, 1)
        self.assertTrue(self.limit.nextReady() > start_time)
        self.assertEqual(rtime(self.limit.nextReady()), rtime(time.time() + self.seconds))
        
        time.sleep(self.seconds)
        self.assertTrue(self.limit.ready())
        self.limit.use()
        self.assertEqual(self.limit.used, 1)
        
    def test_verifyCount(self):
        self.limit = Limit(self.seconds, 5, 0)
        self.assertEqual(self.limit.used, 0)
        self.limit.use()
        self.assertEqual(self.limit.used, 1)
        self.limit.verifyCount(1)
        self.assertEqual(self.limit.used, 1)
        self.limit.use()
        self.limit.verifyCount(1)
        self.assertEqual(self.limit.used, 2)
        self.limit.verifyCount(4)
        self.assertEqual(self.limit.used, 4)
        
        self.assertRaises(IndexError, self.limit.verifyCount, 6)
        
        
        
        
class TestEndpoint(unittest.TestCase):
    def setUp(self):
        self.endpoint = Endpoint()
        self.default_data = {'url':match_url_template.format(matchid=1)}

        
    def test_identifyEndpoint(self):
        e = Endpoint.identifyEndpoint(summoner_url_template.format(name=fake_name))
        self.assertTrue(e == 'lol/summoner/v3/summoners/by-name')
        e = Endpoint.identifyEndpoint(match_url_template.format(matchid='3'))
        self.assertTrue(e == 'lol/match/v3/matches')
        e = Endpoint.identifyEndpoint(match_url_template.format(matchid='324'))
        self.assertTrue(e == 'lol/match/v3/matches')
        e = Endpoint.identifyEndpoint(static_champions_url)
        self.assertTrue(e == 'lol/static-data/v3/champions')
        
        
    def test_limitsDefined(self):
        endpoint = Endpoint()
        self.assertFalse(endpoint.limitsDefined)
        endpoint.handleResponseHeaders(headers)
        self.assertTrue(endpoint.limitsDefined)
        endpoint.limits = {}
        self.assertFalse(endpoint.limitsDefined)
    
        
    def test_addData(self):
        self.assertRaises(Exception, self.endpoint.addData, ({'other':'thing'},))
        
        self.endpoint.addData(self.default_data)
        self.assertEqual(self.endpoint.count, 1)
        
        # Endpoint should prevent adding data that doesn't match
        self.assertRaises(Exception, self.endpoint.addData, ({'other':'thing'},))
        self.assertRaises(Exception, self.endpoint.addData, ({'url':summoner_url_template.format(name=fake_name)},))
        
        # Check order
        m2 = {'url':match_url_template.format(matchid=2)}
        m3 = {'url':match_url_template.format(matchid=3)}
        self.endpoint.addData(m2)
        self.assertEqual(self.endpoint.count, 2)
        self.endpoint.addData(m3)
        self.assertEqual(self.endpoint.count, 3)
        
        self.assertEqual(self.endpoint.get(), self.default_data)
        self.assertEqual(self.endpoint.get(), m2)
        self.assertEqual(self.endpoint.get(), m3)
        
        # Test adding data atFront
        self.assertEqual(self.endpoint.count, 0)
        self.endpoint.addData(self.default_data, atFront=True)
        self.endpoint.addData(m2, atFront=True)
        self.endpoint.addData(m3, atFront=True)
        
        self.assertEqual(self.endpoint.get(), m3)
        self.assertEqual(self.endpoint.get(), m2)
        self.assertEqual(self.endpoint.get(), self.default_data)
        
        
    def test_available(self):
        self.assertFalse(self.endpoint.available())
        for i in range(1,4):
            self.endpoint.addData({'url':match_url_template.format(matchid=i)})
        self.assertTrue(self.endpoint.available())
        self.assertTrue(self.endpoint.available())
        self.endpoint.get()
        self.assertTrue(self.endpoint.available()) # No limit set, still available
        self.endpoint.handleResponseHeaders(headers)
        self.endpoint.get()
        self.assertTrue(self.endpoint.available())
        self.endpoint.get()
        self.assertFalse(self.endpoint.available())
        self.assertFalse(self.endpoint.available())
        
        
    def test_getUsage(self):
        self.assertEqual(self.endpoint.getUsage(), 'No limits defined')
        
        self.endpoint.handleResponseHeaders(headers)
        count, seconds = headers['X-Method-Rate-Limit'].split(':')
        used, seconds = headers['X-Method-Rate-Limit-Count'].split(':')
        used = int(used)
        self.assertEqual(self.endpoint.getUsage(), '%s:%s'%(used,count))
        
        self.endpoint.addData(self.default_data)
        self.endpoint.get()
        self.assertEqual(self.endpoint.getUsage(), '%s:%s'%(used+1,count))
        
        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit-Count'] = '0:%s'%seconds
        self.endpoint.handleResponseHeaders(new_headers)
        self.assertEqual(self.endpoint.getUsage(), '%s:%s'%(used+1,count)) # Limit assumes 0 is old data
        
        
    def test_nextReady(self):
        self.assertEqual(rtime(self.endpoint.nextReady()), rtime())        
        self.endpoint.handleResponseHeaders(headers)
        self.endpoint.addData(self.default_data)
        self.assertEqual(rtime(self.endpoint.nextReady()), rtime())
        
        count, seconds = headers['X-Method-Rate-Limit'].split(':')
        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit-Count'] = '%s:%s'%(count,seconds)
        self.endpoint.handleResponseHeaders(new_headers)
        self.assertTrue(len(self.endpoint.limits) > 0)
        self.assertFalse(self.endpoint.available())
        self.assertEqual(rtime(self.endpoint.limits[seconds].start), rtime())
        self.assertEqual(rtime(self.endpoint.nextReady()), rtime(time.time() + int(seconds)))
        
        
    def test_count(self):
        self.assertEqual(self.endpoint.count, 0)
        
        self.endpoint.addData(self.default_data)
        self.assertEqual(self.endpoint.count, 1)
        
        self.endpoint.addData(self.default_data)     
        self.endpoint.addData(self.default_data)
        self.endpoint.addData(self.default_data)
        self.assertEqual(self.endpoint.count, 4)
        
        self.endpoint.get()
        self.assertEqual(self.endpoint.count, 3)
        
        
        
    
class TestPlatform(unittest.TestCase):
    def setUp(self):
        self.slug = 'na'
        self.platform = Platform(self.slug)
        
        
    def test_countAndHasURL(self):
        self.assertEqual(self.platform.count, 0)
        self.assertFalse(self.platform.hasURL())
        
        self.platform.addData({'url':match_url_template.format(matchid=1)})
        self.assertEqual(self.platform.count, 1)
        self.assertTrue(self.platform.hasURL())
        
        self.platform.addData({'url':summoner_url_template.format(name=fake_name)})
        self.assertEqual(self.platform.count, 2)
        self.assertTrue(self.platform.hasURL())
                
        self.platform.addData({'url':static_champions_url})
        self.assertEqual(self.platform.count, 3)
        self.assertTrue(self.platform.hasURL())
        
        self.platform.get()
        self.assertEqual(self.platform.count, 2)
        self.assertTrue(self.platform.hasURL())
        
        self.platform.get()
        self.assertEqual(self.platform.count, 1)
        self.assertTrue(self.platform.hasURL())
        
        self.platform.get()
        self.assertEqual(self.platform.count, 0)
        self.assertFalse(self.platform.hasURL())
      
      
    def test_rateLimitOK(self):
        self.assertTrue(self.platform.rateLimitOK())
        # TODO: Add more conditions
        
      
    def test_addData_static_random(self):
        s1 = {'url':static_champions_url}
        s2 = {'url':static_summonerspells_url}
        s3 = {'url':static_items_url}
        s = [s1,s2,s3]
        self.platform.addData(s1)
        self.platform.addData(s2)
        self.platform.addData(s3)
        self.assertEqual(self.platform.static_count, 3)
        self.assertTrue(self.platform.get() in s)
        self.assertTrue(self.platform.get() in s)
        self.assertTrue(self.platform.get() in s)
        self.assertRaises(Exception, self.platform.get)
        
        
    def test_addData_static_sorted(self):
        c1 = {'url':static_champion_url.format(id=1)}
        c2 = {'url':static_champion_url.format(id=2)}
        c3 = {'url':static_champion_url.format(id=3)}
        self.platform.addData(c1)
        self.platform.addData(c2)
        self.platform.addData(c3)
        self.assertEqual(self.platform.static_count, 3)
        self.assertEqual(self.platform.get(), c1)
        self.assertEqual(self.platform.get(), c2)
        self.assertEqual(self.platform.get(), c3)
        self.assertRaises(Exception, self.platform.get)
        
        
    def test_addData_static_sorted_atFront(self):
        c1 = {'url':static_champion_url.format(id=1)}
        c2 = {'url':static_champion_url.format(id=2)}
        c3 = {'url':static_champion_url.format(id=3)}
        self.platform.addData(c1, atFront=True)
        self.platform.addData(c2, atFront=True)
        self.platform.addData(c3, atFront=True)
        self.assertEqual(self.platform.static_count, 3)
        self.assertEqual(self.platform.get(), c3)
        self.assertEqual(self.platform.get(), c2)
        self.assertEqual(self.platform.get(), c1)
        self.assertRaises(Exception, self.platform.get)
        
    
    def test_addData_limited_alternate(self):
        m1 = {'url':match_url_template.format(matchid=1)}
        m2 = {'url':match_url_template.format(matchid=2)}
        m3 = {'url':match_url_template.format(matchid=3)}
        s1 = {'url':summoner_url_template.format(name=1)}
        s2 = {'url':summoner_url_template.format(name=2)}
        s3 = {'url':summoner_url_template.format(name=3)}
        self.platform.addData(m1)
        self.platform.addData(m2)
        self.platform.addData(m3)
        self.platform.addData(s1)
        self.platform.addData(s2)
        self.platform.addData(s3)
        self.assertEqual(self.platform.limited_count, 6)
        self.assertEqual(self.platform.get(), m1)
        self.assertEqual(self.platform.get(), s1)
        self.assertEqual(self.platform.get(), m2)
        self.assertEqual(self.platform.get(), s2)
        self.assertEqual(self.platform.get(), m3)
        self.assertEqual(self.platform.get(), s3)
        self.assertRaises(Exception, self.platform.get)
        
    
    def test_addData_limited_sorted(self):
        m1 = {'url':match_url_template.format(matchid=1)}
        m2 = {'url':match_url_template.format(matchid=2)}
        m3 = {'url':match_url_template.format(matchid=3)}
        self.platform.addData(m1)
        self.platform.addData(m2)
        self.platform.addData(m3)
        self.assertEqual(self.platform.limited_count, 3)
        self.assertEqual(self.platform.get(), m1)
        self.assertEqual(self.platform.get(), m2)
        self.assertEqual(self.platform.get(), m3)
        self.assertRaises(Exception, self.platform.get)
        
        
    def test_addData_limited_sorted_atFront(self):
        m1 = {'url':match_url_template.format(matchid=1)}
        m2 = {'url':match_url_template.format(matchid=2)}
        m3 = {'url':match_url_template.format(matchid=3)}
        self.platform.addData(m1, atFront=True)
        self.platform.addData(m2, atFront=True)
        self.platform.addData(m3, atFront=True)
        self.assertEqual(self.platform.limited_count, 3)
        self.assertEqual(self.platform.get(), m3)
        self.assertEqual(self.platform.get(), m2)
        self.assertEqual(self.platform.get(), m1)
        self.assertRaises(Exception, self.platform.get)
        
      
# RateLimiter

if __name__ == '__main__':
    unittest.main()

