import http.server
import json
import urllib.request
from multiprocessing import Process
from multiprocessing.managers import SyncManager

config_path = 'config.json'

# Read config to find port
# Listen on port
gamemode_summaries = None
champion_summaries = None
requested_matches = None


class MyResponseListener(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        print(self.headers)
        self.send_response(200)
        self.end_headers()


def handle_reply():
    # if url for summoner name, extract account id
    # if url for matchlist, look for match id's not in requested_matches
    pass


def start_sync_manager():
    global gamemode_summaries
    global champion_summaries
    global requested_matches
    manager = SyncManager()
    manager.start()

    gamemode_summaries = manager.dict([])
    champion_summaries = manager.dict([])
    requested_matches = manager.list([])


def scenario_manager(config, summoner_name, platform_slug, gamemode_summaries, champion_summaries, requested_matches):
    print('Running scenario: Find out the game modes and champions a summoner has played')
    limiter_url = 'http://{0}:{1}'.format(config['server']['host'], config['server']['port'])
    response_url = 'http://{0}:{1}'.format(config['server']['host'], config['server']['port'] + 1)

    summoner_by_name = 'https://{slug}.api.riotgames.com/lol/summoners/v3/summoners/by-name/{name}'
    issue_request(limiter_url, response_url, summoner_by_name.format(slug=platform_slug, name=summoner_name))


def issue_request(limiter_url, response_url, riot_url):
    r = urllib.request.Request(limiter_url, method='POST')
    r.add_header('X-Url', riot_url)
    r.add_header('X-Return-Url', response_url)
    try:
        response = urllib.request.urlopen(r)
        return response
    except Exception as e:
        return e


def main():
    summoner_name = ''
    while len(summoner_name) == 0:
        summoner_name = input('Summoner Name: ')

    platform_slug = input('Platform slug (default=na1): ')
    if len(platform_slug) == 0:
        platform_slug = 'na1'
    platform_slug = platform_slug.strip().lower()

    start_sync_manager()

    with open(config_path, 'r') as f:
        config = json.loads(f.read())

    server = http.server.HTTPServer((config['server']['host'], config['server']['port'] + 1), MyResponseListener)

    scenario_args = (config, summoner_name, platform_slug, gamemode_summaries, champion_summaries, requested_matches)
    sm = Process(target=scenario_manager, args=scenario_args, name='Scenario_Manager')
    sm.deamon = True
    sm.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Stopping scenario...')


if __name__ == '__main__':
    main()
