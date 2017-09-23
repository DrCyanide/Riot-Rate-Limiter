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


def rtime(timestamp=None, precision=2):
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
        self.summoner_url_template = 'https://na1.api.riotgames.com/lol/summoner/v3/summoners/by-name/{name}'
        self.match_url_template = 'https://na1.api.riotgames.com/lol/match/v3/matches/{matchid}'
        self.static_url = 'https://na1.api.riotgames.com/lol/static-data/v3/champions?dataById=false'
        self.fake_name = 'BillyBob'
        self.endpoint = Endpoint()
        self.default_data = {'url':self.match_url_template.format(matchid=1)}
        self.headers = {
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

        
    def test_identifyEndpoint(self):
        e = Endpoint.identifyEndpoint(self.summoner_url_template.format(name=self.fake_name))
        self.assertTrue(e == 'lol/summoner/v3/summoners/by-name')
        e = Endpoint.identifyEndpoint(self.match_url_template.format(matchid='3'))
        self.assertTrue(e == 'lol/match/v3/matches')
        e = Endpoint.identifyEndpoint(self.match_url_template.format(matchid='324'))
        self.assertTrue(e == 'lol/match/v3/matches')
        e = Endpoint.identifyEndpoint(self.static_url)
        self.assertTrue(e == 'lol/static-data/v3/champions')
        
    def test_limitsDefined(self):
        endpoint = Endpoint()
        self.assertFalse(endpoint.limitsDefined)
        endpoint.setLimit(self.headers)
        self.assertTrue(endpoint.limitsDefined)
        endpoint.limits = {}
        self.assertFalse(endpoint.limitsDefined)
        
    def test_setLimit(self):
        self.endpoint.setLimit(self.headers)
        self.assertEqual(self.endpoint.limits['60'].limit, 270)
        new_headers = copy.copy(self.headers)
        new_headers['X-Method-Rate-Limit'] = '10:120,30:300'
        self.endpoint.setLimit(new_headers)
        self.assertFalse('60' in self.endpoint.limits)
        self.assertEqual(self.endpoint.limits['120'].limit, 10)
        self.assertEqual(self.endpoint.limits['300'].limit, 30)
        
    def test_setCount(self):
        self.endpoint.setLimit(self.headers)
        self.endpoint.setCount(self.headers)
        self.assertEqual(self.endpoint.limits['60'].used, 1)
        new_headers = copy.copy(self.headers)
        new_headers['X-Method-Rate-Limit-Count'] = '4:60'
        self.endpoint.setCount(new_headers)
        self.assertEqual(self.endpoint.limits['60'].used, 4)
        
    def test_addData(self):
        self.assertRaises(Exception, self.endpoint.addData, ({'other':'thing'},))
        self.endpoint.addData(self.default_data)
        self.assertEqual(self.endpoint.count, 1)
        self.assertRaises(Exception, self.endpoint.addData, ({'other':'thing'},))
        self.assertRaises(Exception, self.endpoint.addData, ({'url':self.summoner_url_template.format(name=self.fake_name)},))
        self.endpoint.addData({'url':self.match_url_template.format(matchid=2)})
        self.assertEqual(self.endpoint.count, 2)
        
    def test_available(self):
        self.assertFalse(self.endpoint.available())
        for i in range(1,4):
            self.endpoint.addData({'url':self.match_url_template.format(matchid=i)})
        self.assertTrue(self.endpoint.available())
        self.assertTrue(self.endpoint.available())
        self.endpoint.get()
        self.assertTrue(self.endpoint.available()) # No limit set, still available
        self.endpoint.setLimit(self.headers)
        self.endpoint.get()
        self.assertTrue(self.endpoint.available())
        self.endpoint.get()
        self.assertFalse(self.endpoint.available())
        self.assertFalse(self.endpoint.available())
        
        
    def test_getUsage(self):
        self.assertEqual(self.endpoint.getUsage(), 'No limits defined')
        
        self.endpoint.setLimit(self.headers)
        count, seconds = self.headers['X-Method-Rate-Limit'].split(':')
        self.assertEqual(self.endpoint.getUsage(), '0:%s'%count)
        
        self.endpoint.addData(self.default_data)
        self.endpoint.get()
        self.assertEqual(self.endpoint.getUsage(), '1:%s'%count)
        
        new_headers = copy.copy(self.headers)
        new_headers['X-Method-Rate-Limit-Count'] = '0:%s'%seconds
        self.endpoint.setCount(new_headers)
        self.assertEqual(self.endpoint.getUsage(), '0:%s'%count)
        
    def test_getResetTime(self):
        self.assertEqual(rtime(self.endpoint.getResetTime()), rtime())        
        self.endpoint.setLimit(self.headers)
        self.endpoint.addData(self.default_data)
        self.assertEqual(rtime(self.endpoint.getResetTime()), rtime())
        
        count, seconds = self.headers['X-Method-Rate-Limit'].split(':')
        new_headers = copy.copy(self.headers)
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
        self.endpoint.setLimit(self.headers)
        self.assertTrue(self.endpoint.limitsDefined)
        
    
class TestPlatform(unittest.TestCase):
    def setUp(self):
        pass
      
# RateLimiter

if __name__ == '__main__':
    unittest.main()

