import time


class Limit:
    def __init__(self, seconds, cap, used=0):
        # Limit is only created after you used it once and got a response
        self.seconds = float(seconds)
        self.cap = int(cap)
        self.used = int(used)
        self.start = time.time()

    def ready(self):
        if self.used < self.cap or self.cap < 0:
            return True
        else:
            if self.used >= self.cap:
                if (self.start + self.seconds) < time.time():
                    return True
                return False
            return True

    def next_ready(self):
        return self.start + self.seconds

    def use(self):
        if (self.start + self.seconds) < time.time():
            self.used = 0
            self.start = time.time()
        self.used += 1

    def verify_count(self, count):
        if count <= self.used:
            return
        if count > self.cap:
            raise IndexError('Limit exceeded')
        self.used = count
