import time

class Limit():
    def __init__(self, seconds=-1, limit=-1, used=0):
        self.seconds = seconds
        self.limit = limit
        self.used = used
        self.start = time.time()

    def ready(self):
        if self.used < self.limit or self.limit < 0:
            return True
        else:
            if (self.start + self.seconds) < time.time():
                # Time Limit reset
                self.used = 0
                return True
            if self.used < self.limit:
                return True
            else:
                return False
        
    def use(self):
        if self.used == 0:
            self.start = time.time()
        self.used += 1

    def resetTime(self):
        return self.start + self.seconds