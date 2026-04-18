import sys
import time
import orjson as json
from threading import Thread

class Logger:
    def __init__(self, path, mode, level):
        self.path = path
        self.mode = mode
        self.level = level
        self.LOG = []
        self.maxlen = 100000
        self.is_run = False
        t = Thread(target=self.start_saving)
        t.start()
    def start_saving(self):
        while self.is_run:
            file = open(self.path, self.mode)
            dat = ""
            for i in self.LOG:
                dat += i.to_str() + "\n"
            file.write(dat.encode("utf-8"))
            time.sleep(1)
    def add_message(self, message):
        if message.level> self.level:
            self.LOG.append(message)
            if len(self.LOG) > self.maxlen:
                self.LOG.pop(0)
            print(message.to_str())

    def get_log(self, min_level = -float("inf"), max_level = float("inf"), place = ("all"), service = ("all")):
        lg = []
        for i in self.LOG:
            if i.level > min_level and i.level < max_level:
                if (i.place in place and len(i.place)!= 0) or "all" in place:
                    if (i.service in service and len(i.service) != 0) or "all" in service:
                        lg.append(i)
        return lg
baselogger = None
def set_baselogger(bl):
    global baselogger
    baselogger = bl
def get_baselogger():
    global baselogger
    return baselogger
def set_is_running(i):
    global is_run
    is_run = i

class message:
    def __init__(self, level, text, place = "", service = ""):
        self.level = level
        self.text = text
        if type(place) != str:
            raise TypeError("place must be a string")
        self.place = place
        self.service = service
        self.time = time.time()
        if baselogger != None:
            baselogger.add_message(self)

    def to_str(self):
        lv = ""
        if self.level < 0:
            lv = "TERMINAL"
        elif self.level <=10:
            lv = "DEBUG"
        elif self.level <=20:
            lv = "INFO"
        elif self.level <=30:
            lv = "WARNING"
        elif self.level <=40:
            lv = "ERROR"
        elif self.level <=50:
            lv = "EXCEPTION"
        elif self.level <=100:
            lv = "CRITICAL"
        return f"{lv}, {time.ctime(self.time)}, {self.text}, {self.place}, {self.service}"

def debug(*args, place="", service="", sep = " "):
    text = ""
    for i in args:
        if type(i) == str:
            text += i
        else:
            text += str(i)
        text += sep
    message(10, text, place, service)
def info(*args, place="", service="", sep = " "):
    text = ""
    for i in args:
        if type(i) == str:
            text += i
        else:
            text += str(i)
        text += sep
    message(20, text, place, service)
def warning(*args, place="", service="", sep = " "):
    text = ""
    for i in args:
        if type(i) == str:
            text += i
        else:
            text += str(i)
        text += sep
    message(30, text, place, service)
def error(*args, place="", service="", sep = " "):
    text = ""
    for i in args:
        if type(i) == str:
            text += i
        else:
            text += str(i)
        text += sep
    message(40, text, place, service)
def exception(*args, place="", service="", sep = " "):
    text = ""
    for i in args:
        if type(i) == str:
            text += i
        else:
            text += str(i)
        text += sep
    message(50, text, place, service)
def critical(*args, place="", service="", sep = " "):
    text = ""
    for i in args:
        if type(i) == str:
            text += i
        else:
            text += str(i)
        text += sep
    message(100, text, place, service)

def terminal(*args, place="", service="", sep = " "):
    text = ""
    for i in args:
        if type(i) == str:
            text += i
        else:
            text += str(i)
        text += sep
    message(-10, text, place, service)

if __name__ == "__main__":
    baselogger = Logger("log.log", "wb", level=5)
    debug("something")
    critical("something")
    t = Thread(target = baselogger.start_saving())
    t.start()
    baselogger.is_run = False
    sys.exit()


