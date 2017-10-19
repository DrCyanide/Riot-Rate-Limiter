import unittest
import copy
import time
from Limit import Limit
from Endpoint import Endpoint
from Platform import Platform
import platform

config_path = 'config.json'
server_connection = 'http://'
time_precision = 2  # 3 normally works on my slow computer, but sometimes fails, so I settled on 2

summoner_url_template = 'https://na1.api.riotgames.com/lol/summoner/v3/summoners/by-name/{name}'
match_url_template = 'https://na1.api.riotgames.com/lol/match/v3/matches/{matchid}'
static_champions_url = 'https://na1.api.riotgames.com/lol/static-data/v3/champions?dataById=false'
static_champion_url = 'https://na1.api.riotgames.com/lol/static-data/v3/champions/{id}'
static_summoner_spells_url = 'https://na1.api.riotgames.com/lol/static-data/v3/summoner-spells?dataById=false'
static_summoner_spell_url = 'https://na1.api.riotgames.com/lol/static-data/v3/summoner-spells/{id}'
static_items_url = 'https://na1.api.riotgames.com/lol/static-data/v3/items'
fake_name = 'BillyBob'

headers = {
            'Connection': 'keep-alive', 
            'transfer-encoding': 'chunked', 
            'X-Method-Rate-Limit': '270:60', 
            'Vary': 'Accept-Encoding', 
            'Access-Control-Allow-Headers': 'Content-Type',
            'X-App-Rate-Limit': '100:120,20:1', 
            'Access-Control-Allow-Origin': '*', 
            'Date': 'Mon, 9 Oct 2017  05:30:25 GMT',
            'Content-Type': 'application/json;charset=utf-8', 
            'Access-Control-Allow-Methods': 'GET, POST, DELETE, PUT', 
            'X-Method-Rate-Limit-Count': '1:60', 
            'Content-Encoding': 'gzip', 
            'X-App-Rate-Limit-Count': '1:120,1:1'
        }


def get_date_header():
    # https://stackoverflow.com/a/2073189/1381157
    windows_format = '%a, %#d %b %Y  %H:%M:%S %Z'
    linux_format = '%a, %-d %b %Y  %H:%M:%S %Z'
    if 'windows' in platform.system().lower():
        date_format = windows_format
    else:
        date_format = linux_format

    new_header = copy.copy(headers)
    new_header['Date'] = time.strftime(date_format, time.gmtime())
    return new_header


def rtime(timestamp=None, precision=time_precision):
    # precision 3 normally works on my computer, but occassionally fails.
    # I'd rather not have occassional false failures
    if timestamp is None:
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
        self.assertEqual(rtime(self.limit.next_ready()), rtime(time.time() + self.seconds))
        self.assertEqual(self.limit.used, 0)
        
    def test_use(self):
        self.limit.use()
        self.assertEqual(rtime(self.limit.next_ready()), rtime(time.time() + self.seconds))
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
        self.assertTrue(self.limit.next_ready() > start_time)
        self.assertEqual(rtime(self.limit.next_ready()), rtime(time.time() + self.seconds))
        
        time.sleep(self.seconds)
        self.assertTrue(self.limit.ready())
        self.limit.use()
        self.assertEqual(self.limit.used, 1)
        
    def test_verifyCount(self):
        self.limit = Limit(self.seconds, 5, 0)
        self.assertEqual(self.limit.used, 0)
        self.limit.use()
        self.assertEqual(self.limit.used, 1)
        self.limit.verify_count(1)
        self.assertEqual(self.limit.used, 1)
        self.limit.use()
        self.limit.verify_count(1)
        self.assertEqual(self.limit.used, 2)
        self.limit.verify_count(4)
        self.assertEqual(self.limit.used, 4)
        
        self.assertRaises(IndexError, self.limit.verify_count, 6)
        

class TestEndpoint(unittest.TestCase):
    def setUp(self):
        self.endpoint = Endpoint()
        self.default_data = {'url': match_url_template.format(matchid=1)}

    def test_identify_endpoint(self):
        e = Endpoint.identify_endpoint(summoner_url_template.format(name=fake_name))
        self.assertTrue(e == 'lol/summoner/v3/summoners/by-name')
        e = Endpoint.identify_endpoint(match_url_template.format(matchid='3'))
        self.assertTrue(e == 'lol/match/v3/matches')
        e = Endpoint.identify_endpoint(match_url_template.format(matchid='324'))
        self.assertTrue(e == 'lol/match/v3/matches')
        e = Endpoint.identify_endpoint(static_champions_url)
        self.assertTrue(e == 'lol/static-data/v3/champions')

    def test_limits_defined(self):
        endpoint = Endpoint()
        self.assertFalse(endpoint.limits_defined)
        endpoint.handle_response_headers(headers)
        self.assertTrue(endpoint.limits_defined)
        endpoint.limits = {}
        self.assertFalse(endpoint.limits_defined)

    def test_add_data(self):
        self.assertRaises(Exception, self.endpoint.add_data, ({'other': 'thing'},))
        
        self.endpoint.add_data(self.default_data)
        self.assertEqual(self.endpoint.count, 1)
        
        # Endpoint should prevent adding data that doesn't match
        self.assertRaises(Exception, self.endpoint.add_data, ({'other': 'thing'},))
        self.assertRaises(Exception, self.endpoint.add_data, ({'url': summoner_url_template.format(name=fake_name)},))
        
        # Check order
        m2 = {'url': match_url_template.format(matchid=2)}
        m3 = {'url': match_url_template.format(matchid=3)}
        self.endpoint.add_data(m2)
        self.assertEqual(self.endpoint.count, 2)
        self.endpoint.add_data(m3)
        self.assertEqual(self.endpoint.count, 3)
        
        self.assertEqual(self.endpoint.get(), self.default_data)
        self.assertEqual(self.endpoint.get(), m2)
        self.assertEqual(self.endpoint.get(), m3)
        
        # Test adding data atFront
        self.assertEqual(self.endpoint.count, 0)
        self.endpoint.add_data(self.default_data, front=True)
        self.endpoint.add_data(m2, front=True)
        self.endpoint.add_data(m3, front=True)
        
        self.assertEqual(self.endpoint.get(), m3)
        self.assertEqual(self.endpoint.get(), m2)
        self.assertEqual(self.endpoint.get(), self.default_data)

    def test_available(self):
        self.assertFalse(self.endpoint.available())
        for i in range(1, 4):
            self.endpoint.add_data({'url': match_url_template.format(matchid=i)})
        self.assertTrue(self.endpoint.available())
        self.assertTrue(self.endpoint.available())
        self.endpoint.get()
        self.assertTrue(self.endpoint.available())  # No limit set, still available
        self.endpoint.handle_response_headers(headers)
        self.endpoint.get()
        self.assertTrue(self.endpoint.available())
        self.endpoint.get()
        self.assertFalse(self.endpoint.available())
        self.assertFalse(self.endpoint.available())

    def test_next_ready(self):
        self.assertEqual(rtime(self.endpoint.next_ready()), rtime())
        self.endpoint.handle_response_headers(headers)
        self.endpoint.add_data(self.default_data)
        self.assertEqual(rtime(self.endpoint.next_ready()), rtime())
        
        count, seconds = headers['X-Method-Rate-Limit'].split(':')
        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit-Count'] = '%s:%s' % (count, seconds)
        self.endpoint.handle_response_headers(new_headers)
        self.assertTrue(len(self.endpoint.limits) > 0)
        self.assertFalse(self.endpoint.available())
        self.assertEqual(rtime(self.endpoint.limits[seconds].start), rtime())
        self.assertEqual(rtime(self.endpoint.next_ready()), rtime(time.time() + int(seconds)))

    def test_count(self):
        self.assertEqual(self.endpoint.count, 0)
        
        self.endpoint.add_data(self.default_data)
        self.assertEqual(self.endpoint.count, 1)
        
        self.endpoint.add_data(self.default_data)
        self.endpoint.add_data(self.default_data)
        self.endpoint.add_data(self.default_data)
        self.assertEqual(self.endpoint.count, 4)
        
        self.endpoint.get()
        self.assertEqual(self.endpoint.count, 3)

    def test_handle_delay(self):
        self.endpoint.add_data(self.default_data)
        self.assertTrue(self.endpoint.available())
        self.endpoint._handle_delay(get_date_header())
        self.assertFalse(self.endpoint.available())
        time.sleep(self.endpoint.default_retry_after)
        self.assertTrue(self.endpoint.available())

        delay = 1
        new_headers = get_date_header()
        new_headers['X-Rate-Limit-Type'] = "Method"
        new_headers['X-Retry-After'] = '%s' % delay
        self.endpoint.add_data(self.default_data)
        self.endpoint.get()
        self.endpoint.handle_response_headers(new_headers)
        self.assertFalse(self.endpoint.available())
        time.sleep(delay)
        self.assertTrue(self.endpoint.available())

    def test_get_usage(self):
        self.assertEqual(self.endpoint.get_usage(), 'No limits defined')
        self.endpoint.handle_response_headers(headers)
        count, seconds = headers['X-Method-Rate-Limit'].split(':')
        used, seconds = headers['X-Method-Rate-Limit-Count'].split(':')
        used = int(used)
        self.assertEqual(self.endpoint.get_usage(), '%s:%s' % (used, count))

        self.endpoint.add_data(self.default_data)
        self.endpoint.get()
        self.assertEqual(self.endpoint.get_usage(), '%s:%s' % (used + 1, count))

        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit-Count'] = '0:%s' % seconds
        self.endpoint.handle_response_headers(new_headers)
        self.assertEqual(self.endpoint.get_usage(), '%s:%s' % (used + 1, count))  # Limit assumes 0 is old data

        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit'] = '10:1,100:5'
        new_headers['X-Method-Rate-Limit-Count'] = '1:1,5:5'
        self.endpoint.handle_response_headers(new_headers)
        self.assertEqual(self.endpoint.get_usage(), '1:10,5:100')
        self.endpoint.add_data({'url': match_url_template.format(matchid=1)})
        self.endpoint.get()
        self.assertEqual(self.endpoint.get_usage(), '2:10,6:100')


class TestPlatform(unittest.TestCase):
    def setUp(self):
        self.slug = 'na'
        self.platform = Platform(self.slug)

    def test_count_and_has_url(self):
        self.assertEqual(self.platform.count, 0)
        self.assertFalse(self.platform.has_url())
        
        self.platform.add_data({'url': match_url_template.format(matchid=1)})
        self.assertEqual(self.platform.count, 1)
        self.assertTrue(self.platform.has_url())
        
        self.platform.add_data({'url': summoner_url_template.format(name=fake_name)})
        self.assertEqual(self.platform.count, 2)
        self.assertTrue(self.platform.has_url())
                
        self.platform.add_data({'url': static_champions_url})
        self.assertEqual(self.platform.count, 3)
        self.assertTrue(self.platform.has_url())
        
        self.platform.get()
        self.assertEqual(self.platform.count, 2)
        self.assertTrue(self.platform.has_url())
        
        self.platform.get()
        self.assertEqual(self.platform.count, 1)
        self.assertTrue(self.platform.has_url())
        
        self.platform.get()
        self.assertEqual(self.platform.count, 0)
        self.assertFalse(self.platform.has_url())

    def test_rate_limit_ok(self):
        url = match_url_template.format(matchid=1)
        self.assertTrue(self.platform.rate_limit_ok())
        self.platform.add_data({'url': match_url_template.format(matchid=1)})
        self.platform.handle_response_headers(url, headers)
        self.assertTrue(self.platform.rate_limit_ok())
        new_headers = copy.copy(headers)
        new_headers['X-App-Rate-Limit'] = "1:0.01"
        new_headers['X-App-Rate-Limit-Count'] = "1:0.01"
        new_headers['X-Method-Rate-Limit'] = "5:1"
        new_headers['X-Method-Rate-Limit-Count'] = "1:1"
        self.platform.handle_response_headers(url, new_headers)
        self.assertFalse(self.platform.rate_limit_ok())
        time.sleep(0.01)
        self.assertTrue(self.platform.rate_limit_ok())
        self.platform.get()
        self.assertFalse(self.platform.rate_limit_ok())

    def test_handle_response_headers(self):
        url = match_url_template.format(matchid=1)
        endpoint_str = Endpoint.identify_endpoint(url)
        self.assertRaises(Exception, self.platform.handle_response_headers, (url, headers))
        self.platform.add_data({'url': url})
        self.assertEqual(self.platform.platform_limits, {})
        self.platform.handle_response_headers(url, headers)
        self.assertEqual(len(self.platform.platform_limits), 2)
        self.assertEqual(self.platform.platform_limits["1"].cap, 20)
        self.assertEqual(self.platform.platform_limits["1"].seconds, 1)
        self.assertEqual(self.platform.platform_limits["1"].used, 1)
        self.assertEqual(self.platform.platform_limits["120"].cap, 100)
        self.assertEqual(self.platform.platform_limits["120"].seconds, 120)
        self.assertEqual(self.platform.platform_limits["120"].used, 1)
        self.assertEqual(len(self.platform.limited_endpoints), 1)
        self.assertEqual(self.platform.limited_endpoints[endpoint_str].limits["60"].cap, 270)
        self.assertEqual(self.platform.limited_endpoints[endpoint_str].limits["60"].seconds, 60)
        self.assertEqual(self.platform.limited_endpoints[endpoint_str].limits["60"].used, 1)
        new_headers = copy.copy(headers)
        new_headers['X-App-Rate-Limit'] = "1:1"
        new_headers['X-App-Rate-Limit-Count'] = "1:1"
        new_headers['X-Method-Rate-Limit'] = "5:1"
        new_headers['X-Method-Rate-Limit-Count'] = "1:1"
        self.platform.handle_response_headers(url, new_headers)
        self.assertEqual(len(self.platform.platform_limits), 1)
        self.assertEqual(self.platform.platform_limits["1"].cap, 1)
        self.assertEqual(self.platform.platform_limits["1"].seconds, 1)
        self.assertEqual(self.platform.platform_limits["1"].used, 1)
        self.assertEqual(len(self.platform.limited_endpoints), 1)
        self.assertEqual(self.platform.limited_endpoints[endpoint_str].limits["1"].cap, 5)
        self.assertEqual(self.platform.limited_endpoints[endpoint_str].limits["1"].seconds, 1)
        self.assertEqual(self.platform.limited_endpoints[endpoint_str].limits["1"].used, 1)

    def test_add_data_static_random(self):
        s1 = {'url': static_champions_url}
        s2 = {'url': static_summoner_spells_url}
        s3 = {'url': static_items_url}
        s = [s1, s2, s3]
        self.platform.add_data(s1)
        self.platform.add_data(s2)
        self.platform.add_data(s3)
        self.assertEqual(self.platform.static_count, 3)
        self.assertTrue(self.platform.get() in s)
        self.assertTrue(self.platform.get() in s)
        self.assertTrue(self.platform.get() in s)
        self.assertRaises(Exception, self.platform.get)

    def test_add_data_static_sorted(self):
        c1 = {'url': static_champion_url.format(id=1)}
        c2 = {'url': static_champion_url.format(id=2)}
        c3 = {'url': static_champion_url.format(id=3)}
        self.platform.add_data(c1)
        self.platform.add_data(c2)
        self.platform.add_data(c3)
        self.assertEqual(self.platform.static_count, 3)
        self.assertEqual(self.platform.get(), c1)
        self.assertEqual(self.platform.get(), c2)
        self.assertEqual(self.platform.get(), c3)
        self.assertRaises(Exception, self.platform.get)

    def test_add_data_static_sorted_atFront(self):
        c1 = {'url': static_champion_url.format(id=1)}
        c2 = {'url': static_champion_url.format(id=2)}
        c3 = {'url': static_champion_url.format(id=3)}
        self.platform.add_data(c1, front=True)
        self.platform.add_data(c2, front=True)
        self.platform.add_data(c3, front=True)
        self.assertEqual(self.platform.static_count, 3)
        self.assertEqual(self.platform.get(), c3)
        self.assertEqual(self.platform.get(), c2)
        self.assertEqual(self.platform.get(), c1)
        self.assertRaises(Exception, self.platform.get)

    def test_add_data_limited_alternate(self):
        m1 = {'url': match_url_template.format(matchid=1)}
        m2 = {'url': match_url_template.format(matchid=2)}
        m3 = {'url': match_url_template.format(matchid=3)}
        s1 = {'url': summoner_url_template.format(name=1)}
        s2 = {'url': summoner_url_template.format(name=2)}
        s3 = {'url': summoner_url_template.format(name=3)}
        self.platform.add_data(m1)
        self.platform.add_data(m2)
        self.platform.add_data(m3)
        self.platform.add_data(s1)
        self.platform.add_data(s2)
        self.platform.add_data(s3)
        self.assertEqual(self.platform.limited_count, 6)
        self.assertEqual(self.platform.get(), m1)
        self.assertEqual(self.platform.get(), s1)
        self.assertEqual(self.platform.get(), m2)
        self.assertEqual(self.platform.get(), s2)
        self.assertEqual(self.platform.get(), m3)
        self.assertEqual(self.platform.get(), s3)
        self.assertRaises(Exception, self.platform.get)
    
    def test_add_data_limited_sorted(self):
        m1 = {'url': match_url_template.format(matchid=1)}
        m2 = {'url': match_url_template.format(matchid=2)}
        m3 = {'url': match_url_template.format(matchid=3)}
        self.platform.add_data(m1)
        self.platform.add_data(m2)
        self.platform.add_data(m3)
        self.assertEqual(self.platform.limited_count, 3)
        self.assertEqual(self.platform.get(), m1)
        self.assertEqual(self.platform.get(), m2)
        self.assertEqual(self.platform.get(), m3)
        self.assertRaises(Exception, self.platform.get)

    def test_add_data_limited_sorted_atFront(self):
        m1 = {'url': match_url_template.format(matchid=1)}
        m2 = {'url': match_url_template.format(matchid=2)}
        m3 = {'url': match_url_template.format(matchid=3)}
        self.platform.add_data(m1, front=True)
        self.platform.add_data(m2, front=True)
        self.platform.add_data(m3, front=True)
        self.assertEqual(self.platform.limited_count, 3)
        self.assertEqual(self.platform.get(), m3)
        self.assertEqual(self.platform.get(), m2)
        self.assertEqual(self.platform.get(), m1)
        self.assertRaises(Exception, self.platform.get)

    def test_available(self):
        self.assertFalse(self.platform.available())
        static_data_1 = {'url': static_items_url}
        limited_data_1 = {'url': match_url_template.format(matchid=100)}
        limited_data_2 = {'url': match_url_template.format(matchid=200)}
        self.platform.add_data(static_data_1)
        self.assertTrue(self.platform.available())
        self.platform.get()
        self.assertFalse(self.platform.available())
        self.platform.add_data(limited_data_1)
        self.assertTrue(self.platform.available())
        self.platform.add_data(limited_data_2)
        self.platform.get()
        self.assertTrue(self.platform.available())  # No response headers yet

        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit'] = '1:0.1'
        new_headers['X-Method-Rate-Limit-Count'] = '1:0.1'
        self.platform.handle_response_headers(match_url_template.format(matchid=100), new_headers, 200)
        self.assertFalse(self.platform.available())
        time.sleep(0.1)
        self.assertTrue(self.platform.available())

    def test_handle_delay(self):
        limited_data_1 = {'url': match_url_template.format(matchid=100)}
        limited_data_2 = {'url': match_url_template.format(matchid=200)}
        self.platform.add_data(limited_data_1)
        self.platform.add_data(limited_data_2)
        self.assertTrue(self.platform.available())
        self.platform.get()
        new_headers = get_date_header()
        new_headers['X-Method-Rate-Limit'] = '2:0.1'
        new_headers['X-Method-Rate-Limit-Count'] = '1:0.1'
        self.platform.handle_response_headers(match_url_template.format(matchid=100), new_headers, 429)
        self.assertFalse(self.platform.available())  # Should have a default delay
        time.sleep(1)
        self.assertTrue(self.platform.available())

    def test_get_usage(self):
        used = {'static': {}, 'limited': {}}
        self.assertEqual(self.platform.get_usage(), used)
        url = match_url_template.format(matchid=100)
        match_endpoint = Endpoint.identify_endpoint(url)
        used['limited'][match_endpoint] = 'No limits defined'
        self.platform.add_data({'url': url})
        self.assertEqual(self.platform.get_usage(), used)
        self.platform.handle_response_headers(url, headers)
        used['limited'][match_endpoint] = '1:270'
        self.assertEqual(self.platform.get_usage(), used)
        self.platform.get()
        used['limited'][match_endpoint] = '2:270'
        self.assertEqual(self.platform.get_usage(), used)

        # Static tests
        static_endpoint = Endpoint.identify_endpoint(static_champions_url)
        self.platform.add_data({'url': static_champions_url})
        used['static'][static_endpoint] = 'No limits defined'
        self.assertEqual(self.platform.get_usage(), used)
        self.platform.get()
        new_headers = copy.copy(headers)
        new_headers['X-Method-Rate-Limit-Count'] = '1:60,2:120'
        new_headers['X-Method-Rate-Limit'] = '7:60,10:120'
        used['static'][static_endpoint] = '1:7,2:10'
        self.platform.handle_response_headers(static_champions_url, new_headers)


if __name__ == '__main__':
    unittest.main()
