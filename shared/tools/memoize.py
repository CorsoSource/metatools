"""
    Memoize functions
    
    memoize                - remember results for any particular (hashable) inputs
    memoize_for_call_stack - same, but only within the same function call
                             (this is a uniquely Jython appropriate thing,
                              since one thread may execute many Python contexts)

"""

import sys
from datetime import datetime, timedelta
from functools import wraps


def memoize(function):
    """Memoize outputs.
    
    Note that this does _not_ expire the cache, so switch to the 
    shared.tools.cache decorator if occasional culling is needed.
    """
    @wraps(function)
    def wrapped_function(*args, **kwargs):
        # convert kwargs to args (with defaults), if any, since we can't key on a dict
        if kwargs:
            key_args = args + tuple( # default or kwargs
                kwargs.get(arg_name, default)
                for default, arg_name
                in zip(
                    function.func_defaults,
                    function.func_code.co_varnames[len(args):function.func_code.co_argcount],
                    )
                )
        else:
            key_args = args
        
        try: # to generate the hash of the args
            memo_key = hash(key_args)
        # failsafe and simply pass to function
        except TypeError:
            return function(*args, **kwargs)
        
        # if not memo_key in cache, calculate and add it
        if not memo_key in wrapped_function.memo_cache:
            value = function(*args, **kwargs)
            wrapped_function.memo_cache[memo_key] = value
        
        return wrapped_function.memo_cache[memo_key]
        
    wrapped_function.memo_cache = {}
    
    return wrapped_function



def root_stack_frame(max_depth = 100):
    for size in range(2, max_depth):
        try:
            frame = sys._getframe(size)
            size += 1
        except ValueError:
            return frame
    else:
        raise RuntimeError('Failed to find root stack')


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




def _run_example():
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
