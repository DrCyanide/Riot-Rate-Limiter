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
        self.limit = Limit(seconds=self.seconds, limit=1, used=0)
        
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
        pass
        
    def test_setUsed(self):
        pass
        
# Endpoint
# Platform
# RateLimiter

if __name__ == '__main__':
    unittest.main()

