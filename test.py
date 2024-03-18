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