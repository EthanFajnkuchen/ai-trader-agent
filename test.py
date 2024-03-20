from datetime import datetime

class Object:
    def __init__(self):
        self.obj = {}

obj = Object()

def test():
    obj.obj = {'a': 1, 'b': 2}

def stop():
    global obj
    obj = Object()

test()
print(obj.obj)

stop()
print(obj.obj)

end_time_str = "15:30"
end_time = datetime.now().replace(hour=int(end_time_str.split(":")[0]), minute=int(end_time_str.split(":")[1]), second=0, microsecond=0)
str_end_time = str(end_time)
print(end_time)

end_time_dt = datetime.strptime(str_end_time, "%Y-%m-%d %H:%M:%S")
print(end_time_dt)
