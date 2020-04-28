

from StringIO import StringIO

from shared.tools.pretty import p,pdir
from shared.data.expression import Expression




class Context(object):
	
	__slots__ = ('_locals', '_event', '_arg', 
				 '_local_unsafe', '_snapshot')
	
	def __init__(self, frame, event, arg, snapshot=True):
		
		self._snapshot = snapshot

		local_copy = {}
		local_unsafe = frame.f_locals.copy()

		if snapshot:
			for key,value in frame.f_locals.items():
				try:
					local_copy[key] = deepcopy(value)
				except:
					local_copy[key] = NotImplemented # p or pdir?
					local_copy['*' + key + '*'] = value
				
		self._locals   = local_copy
		self._event    = event
		self._arg      = arg
		self._frame    = frame
		self._locals_unsafe = local_unsafe

	@property
	def deep(self):
		return self._deep
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
	def unsafe(self):
		return self._locals_unsafe
	
	@property
	def caller(self):
		return self._frame.f_code.co_name
	@property
	def filename(self):
		return self._frame.f_code.co_filename
	@property
	def line(self):
		return self._frame.f_lineno

	def __getitem__(self, key):
		if self._deep:
			return self._locals[key]
		else:
			return self._locals_unsafe[key]


	def as_dict(self):
		props = 'event arg caller filename line'.split()
		rep_dict = dict((prop,getattr(self,prop)) for prop in props)

		# locals
		rep_dict['local'] = self.unsafe_locals

		return rep_dict



class StreamHistory():
	"""I/O stream mixin to add history"""
	_MAX_HISTORY = 1000

	def __init__(self):
		self.history = deque(['#! Starting log...'])

	def log(self, string):
		self.history.append(string)
		while len(self.history) > self._MAX_HISTORY:
			_ = self.history.popleft()


class PatientInputStream(StringIO, StreamHistory):
	
	_SLEEP_RATE = 0.05 # seconds
	
	def __init__(self, *args, **kwargs):
		StringIO.__init__(self, *args, **kwargs)
		StreamHistory.__init__(self)
	
	def read(self, n=-1):
		while True:
			chunk = StringIO.read(n)
			if chunk:
				self.history.append('# %s' % chunk)
				return chunk
			else:
				sleep(self._SLEEP_RATE)


	def readline(self, length=None):
		while True:
			line = StringIO.readline(self, length)
			if line:
				self.history.append('>>> %s' % '... '.join(line.splitlines()))
				return line
			else:
				sleep(self._SLEEP_RATE)			
		
	def inject(self, string):
		current_pos = self.tell()
		self.write(string)
		self.pos = current_pos


class OutputStream(StringIO, StreamHistory):
	
	def __init__(self, *args, **kwargs):
		StringIO.__init__(self, *args, **kwargs)
		StreamHistory.__init__(self)
		
	def write(self, string):
		if string != '\n':
			self.history.append(string)
		StringIO.write(self, string)

	def writelines(self, iterable):
		self.history.append(iterable)
		StringIO.writelines(self, iterable)


class ProxyIO(object):
	"""Control the I/O"""

	_SLEEP_RATE = 0.05 # seconds
	
	def __init__(self):
		self.log = lambda s: system.util.getLogger('proxy-io').info(str(s))
		
		self.stdin = PatientInputStream()
		self.stdout = OutputStream()
		self.stderr = OutputStream()
	
	@property
	def last_input(self):
		return self.stdin.history[-1]

	@property
	def last_output(self):
		return self.stdout.history[-1]

	@property
	def last_error(self):
		return self.stderr.history[-1]



class SysHijack(object):
	"""Capture a thread's system state and redirect it's standard I/O."""

	__slots__ = ('_thread_state', '_io_proxy', '_originals',
	             '_target_thread',)

	_BACKUP_ATTRIBUTES = ('stdin', 'stdout', 'stderr',)
	
	# _FAILSAFE_TIMEOUT = 20
	
	def __init__(self, thread, stdio=None):
		self._target_thread = thread
		self._thread_state = getThreadState(self._target_thread)
		
		self._io_stream = stdio
		self._originals = {self._target_thread:{}}
		
		self._init_time = time()
		
		self._install()
		
		# @async(self._FAILSAFE_TIMEOUT)
		# def failsafe_uninstall(self=self):
		# 	self._restore()
		# failsafe_uninstall()
		
		
	def _install(self):
		for key in self._BACKUP_ATTRIBUTES:
			self._originals[self._target_thread][key] = getattr(self._thread_state.systemState, key)
			
			setattr(self._thread_state.systemState, 
				    key, 
				    getattr(self._io_stream,key) if self._io_stream else StringIO())
	
	def _restore(self):
		self._originals['last_session'] = {}
		for key in self._BACKUP_ATTRIBUTES:
			self._originals['last_session'][key] = getattr(self._thread_state.systemState, key)
			setattr(self._thread_state.systemState, key, self._originals[self._target_thread][key])
			
	
	def __getattr__(self, attribute):
		"""Get from this class first, otherwise use the wrapped item."""
		try:
			return super(SysHijack, self).__getattr__(attribute)
		except AttributeError:
			return getattr(self._thread_state.systemState, attribute)

	def __setattr__(self, attribute, value):
		"""Set to this class first, otherwise use the wrapped item."""
		try:
			return super(SysHijack, self).__setattr__(attribute, value)
		except AttributeError:
			return setattr(self._thread_state.systemState, attribute, value)


	def _getframe(self, depth=0):
		print >>self.stdout, '[~] getting frame %d' % depth
		frame = self._thread_state.frame
		while depth > 0 and frame:
			depth -= 1
			frame = frame.f_back
		return frame

	def settrace(self, tracefunc):
		print 'Setting trace function...'
		if tracefunc is None:
			self._thread_state.systemState.settrace(None)
		else:
			self._thread_state.systemState.settrace(tracefunc)

	def setprofile(self, profilefunc):
		if profilefunc is None:
			self._thread_state.systemState.setprofile(None)
		else:
			self._thread_state.systemState.setprofile(profilefunc)

	# def displayhook(self, obj):



class MetaDebugger(type):

	def __new__(cls, clsname, bases, attrs):

		# Generate dispatch lookup for events
		for base in bases:
			event_labels = getattr(base,'_event_labels', None)
			if event_labels:
				break
		else:
			raise AttributeError('Base class(es) missing _event_labels! This is needed to resolve what is needed.')

		event_map = dict((event, getattr(cls, 'dispatch_%s' % event))
						 for event in event_labels)

		setattr(cls, '_dispatch_mapping', event_map)




class Tracer(object):
	"""A variant of the Python Debugger (Pdb)
	
	This is designed to overcome and take advantage of the different
	  constraints that running Pdb in a multi-threaded environment
	  creates.
	  
	For more information and the cool implementation that we're tweaking here,
	  see also rpdb at https://github.com/tamentis/rpdb
	"""

	def _nop(self, _1=None,_2=None):
		pass
	
	__slots__ = ('thread', 'thread_state',
				 'io_interface', 'sys',
				 'frame_history',
			#####	 'monitoring', 'tracing',
				)

	self.context_buffer_limit = 1000

	_event_labels = set(['call', 'line', 'return', 'exception', 
						 'c_call', 'c_return', 'c_exception',
						 ])

	def __init__(self, thread=None):
		
		if not thread:
			raise RuntimeError("Prototype should not be run on main thread!")
			thread = Thread.currentThread()
		
		self.thread = thread
		self.thread_state = getThreadState(thread)
		self.io_interface = ProxyIO()
		
		self.context_buffer = deque()

		self.sys = SysHijack(thread, stdio=self.io_interface)


	# Context control - start and stop active tracing
	def __enter__(self):
		self.monitoring = True
		self.sys.settrace(self.dispatch)
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.monitoring = False
		self.sys.settrace(None)


	# History controls

	def add_context(self, context):
		self.context_buffer.append(context)
		if len(self.context_buffer) > self.context_buffer_limit:
			_ = self.context_buffer_limit.popleft()


	# Dispatch

	def dispatch(self, frame, event, arg):
		if self.monitoring:
			# Check if execution should be intercepted for debugging
			if self.intercept_context(frame, event, arg):

				self._dispatch_mapping.get(event, self._nop)(frame, arg)

			return self.dispatch
		else:
			return # none


	def intercept_context(self, frame, event, arg):
		"""Determine if execution should be stopped."""
		if self.intercepting:
			return True # if already intercepting, continue

		if frame in self.stop_frames:
			return True

		return False 


	def dispatch_call(self, frame, _=None):
		pass
	def dispatch_line(self, frame, _=None):
		pass
	def dispatch_return(self, frame, return_value):
		pass
	def dispatch_exception(self, frame, (exception, value, traceback)):
		pass

	# Jython shouldn't ever call these, so they're here for completeness/compliance
	def dispatch_c_call(self, frame, _=None):
		pass
	def dispatch_c_return(self, frame, return_value):
		pass
	def dispatch_c_exception(self, frame, (exception, value, traceback)):
		pass









class Trap(object):
	
	__slots__ = ('left', 'right')
	
	def __init__(self, left_expression, right_expression):
		self.left = Expression(left_expression)
		self.right = Expression(right_expression)
		
		
	def check(self, context):
		return (self.left(*(getattr(context, field, context[field]) 
							for field 
							in self.left._fields) ) 
				== 
				self.right(*(getattr(context, field, context[field]) 
							 for field 
				 			 in self.right._fields) ) )







def set_trace():
	raise NotImplementedError("TODO: ADD FEATURE")
