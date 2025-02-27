import inspect
from typing import Literal
import zmq
from tblib import Traceback
import sys
import multiprocessing.pool
import multiprocessing.context
def from_json(obj):
    """dummy"""
    return obj

MSG_TYPE = Literal['query', 'query_callable', 'data', 'exception', 'exit', 'timeout', 'callable']

def prepare_msg(obj, type: MSG_TYPE, args = None, kwargs = None):
    res = {'type': type, 'data': obj, 'args': args, 'kwargs': kwargs}
    if type in ['query', 'query_callable']:
        res['timeout'] = 5
    return res

CATASTROPHIC_TIMEOUT = 10

class StudentContext:
    def __init__(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.PAIR)
        self.socket.connect("tcp://localhost:5555")
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)
        self.has_connection = None
        
    def _query_student(self, query, timeout=CATASTROPHIC_TIMEOUT, args=None, kwargs=None, type: Literal['query', 'query_callable', 'ping'] = 'query'):
        if self.has_connection is False:
            raise RuntimeError("Connection to student code failed")
        
        self.socket.send_json(prepare_msg(query, args=args, kwargs=kwargs, type=type), flags=zmq.NOBLOCK)
        has_msg = dict(self.poller.poll(timeout * 1000)).get(self.socket) == zmq.POLLIN
        if has_msg:
            msg = self.socket.recv_json()
            if msg['type'] == 'pong':
                return
            if msg['type'] == 'data':
                return from_json(msg['data'])
            if msg['type'] == 'callable':
                return lambda *args, **kwargs: self._query_student(query, args=args, kwargs=kwargs, type='query_callable')

            if msg['type'] in ['exception', 'timeout']:
                tb = Traceback.from_dict(msg['data']['tb'])
                allowed_exceptions = {'ZeroDivisionError': ZeroDivisionError, 'NameError': NameError}
                
                if type == 'query_callable':
                    # format args and kwargs
                    args = ', '.join(map(repr, args))
                    kwargs = ', '.join(f"{k}={v!r}" for k, v in kwargs.items())
                    if args and kwargs:
                        args += ', '
                    formatted_query = f'`{query}({args}{kwargs})`'
                elif type == 'query':
                    formatted_query = f'`{query}`'
                
                if msg['type'] == 'timeout':
                    raise TimeoutError(f"Timeout executing {formatted_query}")
                else:
                    OriginalException = allowed_exceptions.get(msg['data']['et'], Exception)
                    student_exception = OriginalException(msg['data']['ev']).with_traceback(tb.as_traceback())
                    raise RuntimeError(f"Error executing {formatted_query}") from student_exception
        else:
            raise TimeoutError("Unexpected timeout")
        
    def exit(self):
        self.socket.send_json(prepare_msg(None, type='exit'))

    def ping(self):
        try:
            self._query_student(None, type='ping', timeout=0.5)
            self.has_connection = True
        except TimeoutError:
            self.has_connection = False

    def __getattr__(self, name):
        # determine if it is a callable
        return self._query_student(name)

    __getitem__ = __getattr__

# We implement timeouts on the student side so that we can continue serving queries
# even if the student's code is stuck in an infinite loop.

# We implement timeouts on the grader side if something horribly wrong happens -- but generally shouldn't trigger

def grading_harness(globals, locals):
    context = zmq.Context()
    socket = context.socket(zmq.PAIR)
    socket.bind("tcp://*:5555")

    while True:
        pool = multiprocessing.pool.ThreadPool(processes=1)
        msg = socket.recv_json()
        msg_type = 'exception'
        try:
            if msg['type'] == 'exit':
                sys.exit(0)

            if msg['type'] == 'ping':
                socket.send_json(prepare_msg(None, type='pong'))
                continue

            if msg['type'] == 'query':
                async_value = pool.apply_async(eval, args=(msg['data'], globals, locals))
            if msg['type'] == 'query_callable':
                async_value = pool.apply_async(eval(msg['data'], globals, locals), args=msg['args'], kwds=msg['kwargs'])
            

            value = async_value.get(timeout=msg['timeout'])
            if callable(value):
                socket.send_json(prepare_msg(value.__name__, type='callable'))
            else:
                socket.send_json(prepare_msg(value, type='data'))
        except SystemExit:
            raise
        except BaseException as exc:
            msg_type = 'exception'
            if isinstance(exc, multiprocessing.context.TimeoutError):
                pool.close()
                msg_type = 'timeout'
            
            et, ev, tb = sys.exc_info()
            tb_dict = Traceback(tb).to_dict()
            et_full = inspect.getmodule(et).__name__ + '.' + et.__name__
            response = {'tb': tb_dict, 'et': et_full, 'ev': str(ev)}
            socket.send_json(prepare_msg(response, type=msg_type))
