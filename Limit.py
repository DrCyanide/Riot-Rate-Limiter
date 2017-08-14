import time

class Limit():
    def __init__(self, seconds=-1, limit=-1, used=0):
        self.seconds, self.limit, self.used = self._formatNumbers(seconds, limit, used)
        self.start = time.time()

        
    def _formatNumbers(self, seconds=None, limit=None, used=None):
        if seconds != None and type(seconds) != float:
            seconds = float(seconds)
        if limit != None and type(limit) != int:
            limit = int(limit)
        if used != None and type(used) != int:
            used = int(used)
        return seconds, limit, used
        
        
    def ready(self):
        if self.limit < 0 or self.used < self.limit:
            return True
        else:
            if (self.start + self.seconds) < time.time():
                # Time Limit reset
                self.used = 0
                return True
        return False
                
                
    def setLimit(self, seconds, limit):
        self.seconds, self.limit, temp = self._formatNumbers(seconds, limit)
    
    
    def setUsed(self, used):
        temp1, temp2, self.used = self._formatNumbers(used=used)
        
        
    def use(self):
        if self.used == 0:
            self.start = time.time()
        self.used += 1

        
    def getResetTime(self):
        return self.start + self.seconds