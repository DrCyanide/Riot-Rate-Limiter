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
static_summonerspells_url = 'https://na1.api.riotgames.com/lol/static-data/v3/summoner-spells?dataById=false'
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
        self.limit = Limit(seconds=self.seconds, limit=self.limit_count, used=0)
        
    def test_defaultInit(self):
        self.limit = Limit()
        self.assertTrue(self.limit.ready())
        self.assertTrue(self.limit.getResetTime() < time.time())
        self.assertEqual(self.limit.used, 0)
        
    def test_use(self):
        self.limit.use()
        #self.assertTrue(self.limit.getResetTime() < time.time() + self.seconds)
        self.assertEqual(rtime(self.limit.getResetTime()), rtime(time.time() + self.seconds))
        self.assertEqual(self.limit.used, 1)
        self.limit.use()
        self.limit.use()
        self.assertEqual(self.limit.used, 3)
        
    def test_ready(self):
        start_time = time.time()
        self.seconds = 0.1
        self.limit = Limit(seconds=self.seconds, limit=1, used=1)
        self.assertFalse(self.limit.ready())
        self.assertEqual(self.limit.used, 1)
        self.assertTrue(self.limit.getResetTime() > start_time)
        #self.assertTrue(self.limit.getResetTime() < time.time() + self.seconds)
        self.assertEqual(rtime(self.limit.getResetTime()), rtime(time.time() + self.seconds))
        time.sleep(0.1)
        self.assertTrue(self.limit.ready())
        self.assertEqual(self.limit.used, 0)
        self.limit.use()
        self.assertEqual(self.limit.used, 1)

    def test_formatNumbers(self):
        seconds, limit, used = self.limit._formatNumbers()
        self.assertEqual(seconds, None)
        self.assertEqual(limit, None)
        self.assertEqual(used, None)
        
        seconds, limit, used = self.limit._formatNumbers(seconds='1', limit=12.0, used='5')
        self.assertEqual(seconds, 1)
        self.assertEqual(type(seconds), float)
        self.assertEqual(limit, 12)
        self.assertEqual(type(limit), int)
        self.assertEqual(used, 5)
        self.assertEqual(type(used), int)
        
    def test_setLimit(self):
        self.assertEqual(self.limit.limit, self.limit_count)
        self.limit.setLimit(seconds=10, limit=100)
        self.assertEqual(self.limit.limit, 100)
        self.assertEqual(self.limit.seconds, 10)
        self.assertEqual(self.limit.used, 0)
        
        self.limit.use()
        
        self.limit.setLimit(seconds=1, limit=90)
        self.assertEqual(self.limit.limit, 90)
        self.assertEqual(self.limit.seconds, 1)
        self.assertEqual(self.limit.used, 1)
        
    def test_setUsed(self):
        self.assertEqual(self.limit.used, 0)
        self.assertTrue(self.limit.ready())
        self.limit.setUsed(1)
        self.assertEqual(self.limit.used, 1)
        self.assertFalse(self.limit.ready())
        
    def test_getResetTime(self):
        self.limit.use()
        self.assertTrue(self.limit.getResetTime() > time.time())
        time.sleep(self.limit.seconds)
        self.assertFalse(self.limit.getResetTime() > time.time()) # still gives when it reset, which was in the past
        self.assertTrue(self.limit.ready())
        self.limit.use()
        self.assertTrue(self.limit.getResetTime() > time.time())
        
        
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
        endpoint.setLimit(headers)
        self.assertTrue(endpoint.limitsDefined)
        endpoint.limits = {}
        self.assertFalse(endpoint.limitsDefined)
        
    def test_setLimit(self):
        self.endpoint.setLimit(headers)
        self.assertEqual(self.endpoint.limits['60'].limit, 270)
        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit'] = '10:120,30:300'
        self.endpoint.setLimit(new_headers)
        self.assertFalse('60' in self.endpoint.limits)
        self.assertEqual(self.endpoint.limits['120'].limit, 10)
        self.assertEqual(self.endpoint.limits['300'].limit, 30)
        
    def test_setCount(self):
        self.endpoint.setLimit(headers)
        self.endpoint.setCount(headers)
        self.assertEqual(self.endpoint.limits['60'].used, 1)
        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit-Count'] = '4:60'
        self.endpoint.setCount(new_headers)
        self.assertEqual(self.endpoint.limits['60'].used, 4)
        
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
        self.endpoint.setLimit(headers)
        self.endpoint.get()
        self.assertTrue(self.endpoint.available())
        self.endpoint.get()
        self.assertFalse(self.endpoint.available())
        self.assertFalse(self.endpoint.available())
        
        
    def test_getUsage(self):
        self.assertEqual(self.endpoint.getUsage(), 'No limits defined')
        
        self.endpoint.setLimit(headers)
        count, seconds = headers['X-Method-Rate-Limit'].split(':')
        self.assertEqual(self.endpoint.getUsage(), '0:%s'%count)
        
        self.endpoint.addData(self.default_data)
        self.endpoint.get()
        self.assertEqual(self.endpoint.getUsage(), '1:%s'%count)
        
        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit-Count'] = '0:%s'%seconds
        self.endpoint.setCount(new_headers)
        self.assertEqual(self.endpoint.getUsage(), '0:%s'%count)
        
    def test_getResetTime(self):
        self.assertEqual(rtime(self.endpoint.getResetTime()), rtime())        
        self.endpoint.setLimit(headers)
        self.endpoint.addData(self.default_data)
        self.assertEqual(rtime(self.endpoint.getResetTime()), rtime())
        
        count, seconds = headers['X-Method-Rate-Limit'].split(':')
        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit-Count'] = '%s:%s'%(count,seconds)
        self.endpoint.setLimit(new_headers)
        self.endpoint.setCount(new_headers)
        self.assertTrue(len(self.endpoint.limits) > 0)
        self.assertFalse(self.endpoint.available())
        self.assertEqual(rtime(self.endpoint.limits[seconds].start), rtime())
        self.assertEqual(rtime(self.endpoint.getResetTime()), rtime(time.time() + int(seconds)))
        
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
        
        
    def test_timeNextAvailable(self):
        self.assertEqual(rtime(self.endpoint.timeNextAvailable()), rtime(self.endpoint.getResetTime()))
        
        self.endpoint.addData(self.default_data)
        self.assertEqual(rtime(self.endpoint.timeNextAvailable()), rtime())
        self.assertEqual(rtime(self.endpoint.timeNextAvailable()), rtime(self.endpoint.getResetTime()))

        self.endpoint.addData(self.default_data)
        delayTime = time.time() + 5
        self.endpoint.handleDelay(delayTime)
        self.assertEqual(rtime(self.endpoint.timeNextAvailable()), rtime(delayTime))
        
    
    def test_limitsDefined(self):
        self.assertFalse(self.endpoint.limitsDefined)
        self.endpoint.setLimit(headers)
        self.assertTrue(self.endpoint.limitsDefined)
        
    
class TestPlatform(unittest.TestCase):
    def setUp(self):
        self.platform = Platform()
        self.slug = 'na'
        
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
      
      
    def test_addData(self):
        # platform rotates between endpoints to get from, making it less predictable
        # The important thing is that the endpoints get rotated through, prioritizing static
        
        return
        # Need to modify this part of the code
        
        # Test adding static
        s1 = {'url':static_champions_url}
        s2 = {'url':static_summonerspells_url}
        s3 = {'url':static_items_url}
        self.platform.addData(s1)
        self.platform.addData(s2)
        self.platform.addData(s3)
        self.assertEqual(self.platform.static_count, 3)
        data, temp1, temp2 = self.platform.get()
        self.assertEqual(s1, data)
        data, temp1, temp2 = self.platform.get()
        self.assertEqual(s2, data)
        data, temp1, temp2 = self.platform.get()
        self.assertEqual(s3, data)
        
        # Test adding static atFront
        # Test adding various platforms
        # Test adding various platforms atFront
        pass
      
# RateLimiter

if __name__ == '__main__':
    unittest.main()

