import unittest

import json
import time
import urllib.request as requests
from Limit import Limit
from Endpoint import Endpoint
from Platform import Platform

config_path = 'config.json'
server_connection = 'http://'

class TestLimit(unittest.TestCase):
    def setUp(self):
        self.seconds = 0.1
        self.limit_count = 1
        self.limit = Limit(seconds=self.seconds, limit=self.limit_count, used=0)
        
    def test_defaultInit(self):
        self.limit = Limit()
        self.assertTrue(self.limit.ready())
        self.assertTrue(self.limit.getResetTime() < time.time())
        self.assertTrue(self.limit.used == 0)
        
    def test_use(self):
        self.limit.use()
        self.assertTrue(self.limit.getResetTime() < time.time() + self.seconds)
        self.assertTrue(self.limit.used == 1)
        self.limit.use()
        self.limit.use()
        self.assertTrue(self.limit.used == 3)
        
    def test_ready(self):
        start_time = time.time()
        self.seconds = 0.1
        self.limit = Limit(seconds=self.seconds, limit=1, used=1)
        self.assertFalse(self.limit.ready())
        self.assertTrue(self.limit.used == 1)
        self.assertTrue(self.limit.getResetTime() > start_time)
        self.assertTrue(self.limit.getResetTime() < time.time() + self.seconds)
        time.sleep(0.1)
        self.assertTrue(self.limit.ready())
        self.assertTrue(self.limit.used == 0)
        self.limit.use()
        self.assertTrue(self.limit.used == 1)

    def test_formatNumbers(self):
        seconds, limit, used = self.limit._formatNumbers()
        self.assertTrue(seconds == None)
        self.assertTrue(limit == None)
        self.assertTrue(used == None)
        
        seconds, limit, used = self.limit._formatNumbers(seconds='1', limit=12.0, used='5')
        self.assertTrue(seconds == 1)
        self.assertTrue(type(seconds) == float)
        self.assertTrue(limit == 12)
        self.assertTrue(type(limit) == int)
        self.assertTrue(used == 5)
        self.assertTrue(type(used) == int)
        
    def test_setLimit(self):
        self.assertTrue(self.limit.limit == self.limit_count)
        self.limit.setLimit(seconds=10, limit=100)
        self.assertTrue(self.limit.limit == 100)
        self.assertTrue(self.limit.seconds == 10)
        self.assertTrue(self.limit.used == 0)
        
        self.limit.use()
        
        self.limit.setLimit(seconds=1, limit=90)
        self.assertTrue(self.limit.limit == 90)
        self.assertTrue(self.limit.seconds == 1)
        self.assertTrue(self.limit.used == 1)
        
    def test_setUsed(self):
        self.assertTrue(self.limit.used == 0)
        self.assertTrue(self.limit.ready())
        self.limit.setUsed(1)
        self.assertTrue(self.limit.used == 1)
        self.assertFalse(self.limit.ready())
        
    def test_getResetTime(self):
        self.limit.use()
        self.assertTrue(self.limit.getResetTime() > time.time())
        time.sleep(self.limit.seconds)
        self.assertFalse(self.limit.getResetTime() > time.time()) # still gives when it reset, which was in the past
        self.assertTrue(self.limit.ready())
        self.limit.use()
        self.assertTrue(self.limit.getResetTime() > time.time())
        
        
# Endpoint
# Platform
# RateLimiter

if __name__ == '__main__':
    unittest.main()

