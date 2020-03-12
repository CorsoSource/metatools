from .overwatch import Overwatch


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


class TrapException(Exception):
    pass

class Trap(Overwatch):
    
    __slots__ = ('traps', 'prev_frames', 'disarmed', 'tripped',)
    _previous_callback = None
    
    max_buffered_frames = 20
    
    break_point = Tracer()
    
    frame_file_pattern = re.compile(r'(<.*>|[\/]sequencer[\/])', re.I)
    
    def __init__(self, *args, **kwargs):
        self.clear()
        
        # remove the leading underscore and map it to the event
        self._callbacks = dict((event[1:],getattr(self,event))
                               for event in self._configured_events)
        

    def clear(self):
        self.disarmed = False
        self.tripped = False
        self.traps = {}
        self.prev_frames = deque()
        
    
    # CONTEXT MANAGER
    
    def __enter__(self):
        self._callback_function(self.dispatch)
        print 'V   Trap ready with: %r' % self._callback_current()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._callback_function(None)
        print 'A   Trap disarmed (%r)' % self._callback_current()

    
    # DISPATCH
    
    def dispatch(self, frame, event, arg):
        if self.disarmed:
            print '.    Disarmed - stopping...'
            self._callback_function(None)
            return None

        # Capture history
        context = Context(frame, event, arg)
        if self.frame_file_pattern.match(context.filename):
            self._push_frame(context)
            
        # Captute the call, if anything (and ignore it)
        self._cb_retval = self._callbacks.get(event,lambda f,a: None)(context)

        # check again in case it's been tripped mid-flight
        if self.tripped:
            print '*    Disarmed - stopping...'
            self._callback_function(None)
            self.break_point()
            return None

        if self.disarmed:
            print '.    Disarmed - stopping...'
            self._callback_function(None)
            return None
        

        # continue the stream
        return self.dispatch
    
   
    # TRACE CALLBACKS
    
    def _exception(self, context):
        exception, value, traceback = context.arg
        print 'FAIL Exception  %s   %s in %s' % (str(exception), context.caller, context.filename)

        if isinstance(exception, TrapException):
            self.disarmed = True
            
        raise exception
    
   
    def _return(self, context):
        return_value = context.arg
        if self.frame_file_pattern.match(context.filename):
            print '|>-- return   %s in %s  with %r' % (context.caller, context.filename, return_value)
        self.check_traps(context)

        
    def _call(self, context):
        if self.frame_file_pattern.match(context.filename):
            print '|>-- call   %s in %s' % (context.caller, context.filename)
        self.check_traps(context)

    
    def _line(self, context):
        #print '| -- line    %d @ %s in %s' % (frame.f_lineno, frame.f_code.co_name, frame.f_code.co_filename)
        self.check_traps(context)

        
    # TRAP SPRINGS
        
    def check_traps(self, context):
        if self.traps:
            if self.trip_triggers(context):
                
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
    
    def add_trigger(self, function, expected_result):
        print '+    adding trap: %r against %r' % (function, expected_result)
        self.traps[function] = expected_result
    
    
    # CONTEXT
    def _push_frame(self, context):
        self.prev_frames.append(context)
        if len(self.prev_frames) > self.max_buffered_frames:
            _ = self.prev_frames.popleft()

    def summarize(self):        
        for ix, context in enumerate(reversed(self.prev_frames)):
            print '[%3d]>  %-7s   -----------------------------------------' % (ix, context.event,)
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