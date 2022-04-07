"""
    Memoize functions - but only within the same function call

from time import sleep

    
@memoize_for_call_stack
def do_thing(x, y=3):
print '<< direct call: ', x, y
return x + y


print '=== no defaults ==='
do_thing(10)
do_thing(10)
print '=== all args ==='
do_thing(10,6)
do_thing(10,6)
print '=== args kwargs ==='
do_thing(10, y=34)
do_thing(10, y=34)
print '=== all kwargs ==='
do_thing(x=2, y=10)
do_thing(x=2, y=10)


print 'testing timeout'
sleep(11)
print 'after timeout'
do_thing(10)
print 'testing failsafe'
do_thing([1,2],[3,4])
"""
import sys
from datetime import datetime, timedelta
from functools import wraps



def root_stack_frame(max_depth = 100):
    for size in range(2, max_depth):
        try:
            frame = sys._getframe(size)
            size += 1
        except ValueError:
            return frame
    else:
        raise RuntimeError('Failed to find root stack')


def arg_hash(args, kwargs):
    return hash((args, frozenset(kwargs.items())))
    

def memoize(function):
    """Memoize outputs.
    
    Note that this does _not_ expire the cache, so switch to the 
    shared.tools.cache decorator if occasional culling is needed.
    """
    @wraps(function)
    def memoized(*args, **kwargs):
        
        # in the event something unhashable was sent, this'll failsafe      
        key_state = 0
        try:
            memo_key = arg_hash(args, kwargs)
            if memo_key not in memoized.cache:
                key_state = 1
            else:
                key_state = 2
        except TypeError:
            key_state = 0
        
        # failsafe or cache the result if needed...
        if key_state == 0:
            # failsafe and simply run the function
            print 'cache fail'
            return function(*args, **kwargs)
        elif key_state == 1:
            # cache the fresh entry
            print 'adding cache'
            memoized.cache[memo_key] = function(*args, **kwargs)
        # ... and return the result
        return memoized.cache[memo_key]
    
    memoized.cache = {}
    
    return memoized



#CALLSTACK_CACHE_EXPIRATION = timedelta(minutes=10)
CALLSTACK_CACHE_EXPIRATION = timedelta(seconds=10)


def memoize_for_call_stack(function):
    """Memoize outputs, but only within the callstack's context.
    
    This will leave the last values in the cache potentially,
      so there's an implicit assumption that this is getting called
      frequently.
    """
    @wraps(function)
    def memoized_call(*args, **kwargs):
        context = root_stack_frame()
        
        now = datetime.now()
        
        # check for any expired entries first
        expired = []
        for c_key, t_out in memoized_call.timeout.items():
            if now - t_out > CALLSTACK_CACHE_EXPIRATION:
                expired.append(c_key)
        # ... and cull them
        for c_key in expired:
            del memoized_call.cache[c_key]
            del memoized_call.timeout[c_key]
        
        # init the cache for this callstack
        if context not in memoized_call.cache:
            memoized_call.cache[context] = {}
            memoized_call.timeout[context] = now
        
        # in the event something unhashable was sent, this'll failsafe      
        key_state = 0
        try:
            memo_key = arg_hash(args, kwargs)
            if memo_key not in memoized_call.cache[context]:
                key_state = 1
            else:
                key_state = 2
        except TypeError:
            key_state = 0
        
        # failsafe or cache the result if needed...
        if key_state == 0:
            # failsafe and simply run the function
            return function(*args, **kwargs)
        elif key_state == 1:
            # cache the fresh entry
            memoized_call.cache[context][memo_key] = function(*args, **kwargs)
        # ... and return the result
        return memoized_call.cache[context][memo_key]
    
    memoized_call.cache = {}
    memoized_call.timeout = {}
    
    return memoized_call
