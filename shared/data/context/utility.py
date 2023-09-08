"""
    Utility functions to pack up some odds-n-ends

"""

from shared.tools.thread import findThreads
from shared.tools.thread import async
from time import sleep



#####################
# regex match helpers

import re

def re_match_groupdict(pattern, value, flags=0):
    match = re.match(pattern, value, flags)
    if match:
        return match.groupdict()
    else:
        return {}

def re_match_extract(pattern, value, name):
    return re_match_groupdict(pattern, value).get(name)


######################
# random identifer gen

import random
import string

def random_id(length=4):
    return ''.join(random.choice(string.hexdigits[:16]) for x in range(length))


def apply_jitter(delay, jitter_fraction):
    width = int((delay * jitter_fraction) * 1000)
    offset = random.randint(-width, width) / 1000.0
    return delay + offset


#####################
# thorough error logs

import traceback
from java.lang import Exception as JavaException

def formatted_traceback(exception, exc_tb=None):
    if exception is None:
        return ''
    if isinstance(exception, Exception): # use the output of sys.exc_info()
        return ''.join(traceback.format_exception(type(exception), exception, exc_tb))
    elif isinstance(exception, JavaException):
        return java_full_stack(exception)
    else:
        return repr(exception)


####################
# Make lookup easier
#  (avoid getattr)

class DictLikeAccessMixin(object):
    
    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError('%r is not accessible from Kernel Context' % (item,))

    def __setitem__(self, item, value):
        try:
            setattr(self, item, value)
        except AttributeError:
            raise KeyError('%r is not accessible from Kernel Context' % (item,))            


####################
# jailbreaking stack

import sys

from shared.tools.thread import getThreadFrame

class NameNotFoundError(NameError): pass # maybe should be a KeyError?
class ObjectNotFoundError(ValueError): pass
class TypeNotFoundError(ValueError): pass
    

def get_from_thread(thread, object_type, get_all_instances=False):
    """
    Get object from the thread, searching from the root frame up.
    
    Returns on the first frame that yields a result, and on the first object it finds in local scope.
    IFF get_all_instances is set, then expect a list, otherwise it'll return the first instance.

    On failure to find anything it throws a NotFoundError.
    """
    instances = []
    frame = getThreadFrame(thread)
    stack = [frame]
    while frame.f_back:
        stack.append(frame.f_back)
        frame = frame.f_back
    try:
        for frame in reversed(stack):
            for value in frame.f_locals.values():
                if isinstance(value, object_type):
                    if get_all_instances:
                        instances.append(value)
                    else:
                        return value
            if instances:
                return instances
        else:
            raise TypeNotFoundError
    except: 
        # frames that continued execution and are now defunct/missing/gc'd can throw errors, too 
        # (but ignore them, since they won't have the object we're looking for)
        raise TypeNotFoundError('Type %r not found in execution stack' % (object_type,))