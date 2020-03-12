import sys, re
from copy import deepcopy
from collections import deque

from .overwatch import MetaOverwatch, Overwatch


# Make the interface slightly more generic
try:
    ipython_connection = get_ipython().__class__.__name__
    # jupyter
    if ipython_connection == 'ZMQInteractiveShell':
        from IPython.core.debugger import Tracer
        BreakpointFunction = Tracer()
    # terminal
    elif ipython_connection == 'TerminalInteractiveShell':
        from IPython.core.debugger import Tracer
        BreakpointFunction = Tracer()
    else:
        raise ImportError
except NameError, ImportError:
    import pdb
    BreakpointFunction = lambda : pdb.set_trace()


class Context(object):
    
    __slots__ = ('_locals', '_event', '_arg', '_caller', '_filename', '_line')
    
    def __init__(self, frame, event, arg):
        
        local_copy = {}
        for key,value in frame.f_locals.items():
            try:
                local_copy[key] = deepcopy(value)
            except:
                local_copy[key] = NotImplemented
                
        self._locals   = local_copy
        self._event    = event
        self._arg      = arg
        self._caller   = frame.f_code.co_name
        self._filename = frame.f_code.co_filename
        self._line     = frame.f_lineno
    
    @property
    def local(self):
        return self._locals
    
    @property
    def event(self):
        return self._event
    @property
    def arg(self):
        return self._arg
    @property
    def caller(self):
        return self._caller
    @property
    def filename(self):
        return self._filename
    @property
    def line(self):
        return self._line

    def as_dict(self):
        props = 'local event arg caller filename line'.split()
        return dict((prop,getattr(self,prop)) for prop in props)


class TrapException(Exception):
    pass


class MetaTrap(MetaOverwatch):
    def __getitem__(cls, trap_ix):
        return cls._cached_traps[trap_ix]

class Trap(Overwatch):
    __metaclass__ = MetaTrap

    __slots__ = ('traps', 'disarmed', 'tripped',
                 '_prev_frames', 'max_buffered_frames',
                 '_frame_cache_pattern', 'verbose')

    _cached_traps = {}

    _previous_callback = None    
    _default_break_point = BreakpointFunction
    
    _default_frame_cache_pattern = re.compile('<.*>', re.I)
    
    def __init__(self, max_frames = 10, break_point=None, frame_pattern='', verbose=False):
        self._cached_traps[id(self)] = self
        
        self.verbose = verbose

        if break_point is None:
            self.break_point = self._default_break_point
        else:    
            self.break_point = break_point

        if frame_pattern:
            self.frame_cache_pattern = re.compile(frame_pattern)
        else:
            self.frame_cache_pattern = self._default_frame_cache_pattern

        self.max_buffered_frames = max_frames

        self.clear()
        
        # remove the leading underscore and map it to the event
        self._callbacks = dict((event[1:],getattr(self,event))
                               for event in self._configured_events)


    def clear(self):
        self.disarmed = False
        self.tripped = False
        self.traps = {}
        self._prev_frames = deque()

    @classmethod
    def purge_cache(cls):
        for trap in cls._cached_traps.values():
            trap.end()
        cls._cached_traps = {}
        if self.verbose:
            print 'XXX History contexts have been purged!'
        
    # CONTEXT MANAGER
    
    def start(self):
        self._callback_function(self.dispatch)
        if self.verbose:
            print 'V   Trap ready with: %r' % self._callback_current()
            print '|       Use the id %d to access Trap._cached_traps' % id(self)
        else:
            print 'Trap %d started' % id(self)

    def end(self):
        self._callback_function(None)
        if self.verbose:
            print 'A   Trap disarmed (%r)' % self._callback_current()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()
    
    # DISPATCH

    def check_frame(self, context):
        signature = '<%(event)s> %(caller)s on %(line)s of %(filename)s' % context.as_dict()
        return frame_cache_pattern.match()

    
    def dispatch(self, frame, event, arg):
        if self.disarmed:
            if self.verbose:
                print '.    Disarmed - stopping...'
            self._callback_function(None)
            return None

        # Capture history
        context = Context(frame, event, arg)
        if self.frame_cache_pattern.match(context.filename):
            self._push_frame(context)
            
        # Captute the call, if anything (and ignore it)
        self._cb_retval = self._callbacks.get(event,lambda f,a: None)(context)

        # check again in case it's been tripped mid-flight
        if self.tripped:
            if self.verbose:
                print '*    Disarmed - stopping...'
            self._callback_function(None)
            self.break_point()
            return None

        if self.disarmed:
            if self.verbose:
                print '.    Disarmed - stopping...'
            self._callback_function(None)
            return None
        

        # continue the stream
        return self.dispatch
    
   
    # TRACE CALLBACKS
    
    def _exception(self, context):
        exception, value, traceback = context.arg
        if self.verbose:
            print 'FAIL Exception  %s   %s in %s' % (str(exception), context.caller, context.filename)

        if isinstance(exception, TrapException):
            self.disarmed = True
            
        raise exception
    
   
    def _return(self, context):
        return_value = context.arg
        if self.frame_cache_pattern.match(context.filename):
            if self.verbose:
                print '|>-- return   %s in %s  with %r' % (context.caller, context.filename, return_value)
        self.check_traps(context)

        
    def _call(self, context):
        if self.frame_cache_pattern.match(context.filename):
            if self.verbose:
                print '|>-- call   %s in %s' % (context.caller, context.filename)
        self.check_traps(context)

    
    def _line(self, context):
        # if self.verbose:
        #     print '| -- line    %d @ %s in %s' % (frame.f_lineno, frame.f_code.co_name, frame.f_code.co_filename)
        self.check_traps(context)

        
    # TRAP SPRINGS
        
    def check_traps(self, context):
        if self.traps:
            if self.trip_triggers(context):
                if self.verbose:
                    print '+--! Tripping! Pausing execution for debugger...'
                self.disarmed = True
                self.tripped = True
                
    def trip_triggers(self, context):
        for function,expectation in self.traps.items():
            kwargs = set(function.__code__.co_varnames)
            if kwargs <= (set(context.local)|set(['context'])):

                arg_scope = dict((v,context.local[v] if v is not 'context' else context) for v in kwargs)
    
                try:
                    if expectation == function(**arg_scope):
                        return True
                except:
                    pass # fail by default
                
        return False
    
    # SETUP
    
    def add_trigger(self, function, expected_result=True):
        if self.verbose:
            print '+    adding trap: %r against %r' % (function, expected_result)
        self.traps[function] = expected_result
    
    
    # CONTEXT
    def _push_frame(self, context):
        self.history.append(context)
        if len(self.history) > self.max_buffered_frames:
            _ = self.history.popleft()

    @property
    def history(self):
        return self._prev_frames

    def summarize(self):        
        for ix, context in enumerate(reversed(self.history)):
            print '[%3d]>  %-7s   ----------------------------------------------------------------' % (ix, context.event,)
            print '    |   Line %-5d' % (context.line,)
            print '    |     of %s in "%s"' % (context.caller, context.filename,)
            if context.event == 'return':
                print '    |     returning %r' % (context.arg,)
            elif context.arg:
                print '    |     with %r' % (context.arg,)
            for key,value in context.local.items():
                print '    |   %-20s : %r' % (key,value,)

    def __call__(self):
        self.summarize()