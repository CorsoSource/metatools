import sys

class MetaOverwatch(type):
    
    def __new__(cls, clsname, bases, attrs):
        for base in bases:
            event_map = getattr(base,'_event_map')
            if event_map:
                event_callbacks = set(event_map.values())
                break
        else:
            raise AttributeError('Base class(es) missing _event_map! This is needed to resolve what is needed.')
        
        for base in bases:
            configured_events = set(getattr(base, '_configured_events', set()))
            if configured_events:
                break
            
        for attr in attrs:
            if attr in event_callbacks:
                configured_events.add(attr)
        attrs['_configured_events'] = configured_events
        
        newclass = super(MetaOverwatch, cls).__new__(cls, clsname, bases, attrs)
        return newclass

class BlindOverwatch(object):
    """Template class that sets the basis for the rest."""
    _callback_function = lambda x: None
    _callback_current = lambda x: None
    
    _configured_events = set()

    _event_map = {
        'call':      '_call',
        'line':      '_line',
        'return':    '_return',
        'exception': '_exception',
        'c_call':      '_c_call',
        'c_return':    '_c_return',
        'c_exception': '_c_exception',
    }

    def dispatch(self, frame, event, arg):
        self._callback_function(None)
    
    #    # local trace funtions
    def _nop(self, _1=None,_2=None):
        pass

    def _call(self, frame, _=None):
        pass
    def _line(self, frame, _=None):
        pass
    def _return(self, frame, return_value):
        pass
    def _exception(self, frame, (exception, value, traceback)):
        pass

    def _c_call(self, frame, _=None):
        pass
    def _c_return(self, frame, return_value):
        pass
    def _c_exception(self, frame, (exception, value, traceback)):
        pass


class Overwatch(BlindOverwatch):
    __metaclass__ = MetaOverwatch
    __slots__ = ('_previous_callback', '_cb_retval')
        
    _callback_function = sys.settrace
    _callback_current  = sys.gettrace
    
    def __init__(self, replaceExisting=False):
        # Buffer any current callbacks, if desired
        if replaceExisting:
            self._previous_callback = None
        else:
            self._previous_callback = self._callback_current
        
        self._callbacks = dict((event,getattr(self,self._event_map[event]))
                               for event in self._configured_events)
        
        self._callback_function(self.dispatch)
        
    
    def dispatch(self, frame, event, arg):
        if self._previous_callback:
            self._previous_callback = self._previous_callback(frame, event, arg)
        
        self._cb_retval = self._callbacks.get(event,None)
        if self._cb_retval:
            if self._cb_retval(frame,arg) is None:
                del self._callbacks[event]
        
        if self._callbacks:
            return self.dispatch
        else:
            self._callback_function(self._previous_callback)
        

class InterceptException(Overwatch):
    def _exception(self, frame, (exception, error, traceback)):
        pass