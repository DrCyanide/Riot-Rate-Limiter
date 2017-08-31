
#WORK IN PROGRESS

This program is designed to run as a rate limiter and proxy for the Riot Games API. Your API Key will be added to the request by this program (running on the server's end), but you'll still need to tell it which URL you wish to access.

## Simple Mode: GET requests

This method is best for anything that requires a proxy (such as Javascript or mobile apps).

1. Update config.json to use your actual info
2. Run 'python RateLimiter.py' to start the server (or 'python3 RateLimiter.py', if you have both Python 2 and Python 3)
3. Issue an HTTP GET request with a header 'X-Url', the value of which is the URL you want to get back from the Riot API

For an example of this method, open webtest.html

## Fast Mode: POST requests

This method requires a 'X-Return-Url' header with the URL that will accept a POST command back with the data. This is intended for production servers that are trying to request many records at once.

This method is still being coded, usage instructions will come later.
