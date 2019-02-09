import time


class Limit:
    def __init__(self, seconds, cap=-1, used=0):
        # Limit is only created after you used it once and got a response
        self.seconds = float(seconds)
        self.cap = int(cap)
        self.used = int(used)
        self.start = time.time()

    def ready(self):
        if self.used < self.cap or self.cap < 0:
            return True
        elif self.used >= self.cap:
            if self.next_ready() < time.time():
                return True
            return False
        # Shouldn't be hit

    def next_ready(self):
        return self.start + self.seconds

    def use(self):
        if self.next_ready() < time.time():
            self.used = 0
            self.start = time.time()
        self.used += 1

    def verify_count(self, count):
        if count < self.used:
            self.used = count
        if count > self.cap and self.cap > -1:
            self.used = count
            raise IndexError('Limit exceeded (%s out of %s / %s)' % (count, self.cap, self.seconds))
        
