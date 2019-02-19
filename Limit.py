import time


class Limit:
    def __init__(self, seconds=0, cap=-1, used=0):
        # Limit is only created after you used it once and got a response
        self.seconds = float(seconds)
        self.cap = int(cap)
        self.used = int(used)
        self.start = time.time()
        print('Finished Init of limit %s/%s' % (cap, seconds))

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
            #if self.seconds == 120:
            #    print('Resetting at %s used' % self.used)
            self.used = 0
            self.start = time.time()
        self.used += 1
        #if self.seconds == 120:
        #    print('Incremented used to %s' % self.used)

    def verify_count(self, count):
        if count > self.used:
            # Limit has been used more than expected
            #if self.seconds == 120:
            #print('Modifying used: %s -> %s' % (self.used, count))
            self.used = count
            #if self.seconds == 120:
            #print('Modified used: %s' % (self.used))
        if count > self.cap and self.cap > -1:
            self.used = count
            # raise IndexError('Limit exceeded (%s out of %s / %s)' % (count, self.cap, self.seconds))
            print('Limit exceeded (%s out of %s / %s)' % (count, self.cap, self.seconds)) # Don't want to raise because then it kills the update process
