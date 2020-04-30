from shared.tools.thread import async, dangerouslyKillThreads

from time import sleep

RUNNING_THREAD_NAME = 'debug_test'

dangerouslyKillThreads(RUNNING_THREAD_NAME, bypass_interlock='Yes, seriously.')

@async(name='debug_test')
def monitored():
	close_loop = False
	
	time_delay = 0.1
	find_me = 0
	
	while True:
		find_me += 1
		sleep(time_delay)
		
		if close_loop:
			break
	
	print 'Finished'

running_thread = monitored()



from StringIO import StringIO

shared.tools.pretty.install()

from shared.data.expression import Expression, convert_to_postfix
from shared.tools.thread import findThreads, getThreadState, Thread
from collections import deque
from datetime import datetime, timedelta

from weakref import WeakValueDictionary


class Context(object):
	
	__slots__ = ('_locals', '_event', '_arg', '_frame',
				 '_locals_unsafe', '_snapshot')
	
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
		self.displayhook = shared.tools.pretty.displayhook
	
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

	_BACKUP_ATTRIBUTES = ('stdin', 'stdout', 'stderr','displayhook')
	
	# _FAILSAFE_TIMEOUT = 20
	
	def __init__(self, thread, stdio=None):
		self._target_thread = thread
		self._thread_state = getThreadState(self._target_thread)
		
		self._io_stream = stdio
		self._originals = {self._target_thread:{}}
		
		self._init_time = datetime.now()
		
		self._install()
		
		# @async(self._FAILSAFE_TIMEOUT)
		# def failsafe_uninstall(self=self):
		# 	self._restore()
		# failsafe_uninstall()
		
		
	def _install(self):
		for key in self._BACKUP_ATTRIBUTES:
			self._originals[self._target_thread][key] = getattr(self._thread_state.systemState, key)
			
			setattr(self._thread_state.systemState, key, 
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

	def settrace(self, tracefunc=None):
		print 'Setting trace function...'
		if tracefunc is None:
			self._thread_state.systemState.settrace(None)
		else:
			self._thread_state.systemState.settrace(tracefunc)

	def setprofile(self, profilefunc=None):
		if profilefunc is None:
			self._thread_state.systemState.setprofile(None)
		else:
			self._thread_state.systemState.setprofile(profilefunc)

	# def displayhook(self, obj):



class Tracer(object):
	"""A variant of the Python Debugger (Pdb)
	
	This is designed to overcome and take advantage of the different
	  constraints that running Pdb in a multi-threaded environment
	  creates.
	  
	For more information and the cool implementation that we're tweaking here,
	  see also rpdb at https://github.com/tamentis/rpdb
	"""
	__slots__ = ('thread', 'thread_state', 'active',
				 'io_interface', 'sys',
				 'context_buffer', '_dispatch_mapping',
				 'command', 'monitoring', 'intercepting',
				 '_shutdown', '_monitoring_thread',
			#####	 'monitoring', 'tracing',
				)

	CONTEXT_BUFFER_LIMIT = 1000
	
	_TRACE_MONITOR_SLEEP = 0.05
	_TRACE_MONITOR_INIT_USECOND_TIMEOUT = 100000
	
	_active_tracers = WeakValueDictionary()
	
	_event_labels = set(['call', 'line', 'return', 'exception', 
						 'c_call', 'c_return', 'c_exception',
						 ])	
	
	def _nop(self, _1=None,_2=None):
		pass
		 
	def __new__(cls, thread=None):
		"""Tracer needs to have its own async holding thread
		so it doesn't block the main thread when it spins up and waits for input.
		"""
		if not thread or thread is Thread.currentThread():
			raise RuntimeError("Tracer should not be spawned from its own thread! (Risks zombie deadlocking on input!)")
			#thread = Thread.currentThread()
		if thread in cls._active_tracers:
			raise RuntimeError('Only one Tracer is allowed to attach to a thread at a time! Dupe attempt found on "%s"@%s' % (thread.getName(), thread.getId()))
		
		# I assume timeouts are better than sleep waits.
		# When the tracer exits, the weak reference will drop the thread.
		@async(name='Tracing: %s' % thread.getName())
		def tracing_monitor(cls=cls, thread=thread):
			
			tracer = super(Tracer, cls).__new__(cls)
			
			my_thread = Thread.currentThread()
			cls._active_tracers[thread] = tracer
			
			tracer._monitoring_thread = my_thread
			
			tracer.__init__(thread)
			
			# keep this holding thread alive until the tracer dies
			#   once it is removed from the weak value dict the thread
			#   will pass on as well
			while cls._active_tracers.get(my_thread):
				sleep(cls._TRACE_MONITOR_SLEEP)
		
		tracer_thread = tracing_monitor()
#		
#		# Wait for the thread to initialize the debugger object, 
#		#   but don't wait _too_ long...
#		timeout = datetime.now() + timedelta(microseconds=cls._TRACE_MONITOR_INIT_USECOND_TIMEOUT)
#		while not cls._active_tracers.get(tracer_thread) and datetime.now() < timeout:
#			sleep(0.005)
#			
#		if not cls._active_tracers.get(tracer_thread):
#			raise RuntimeError("Tracer spawn init timed out!")
#		
#		# If we have the object, set the monitoring thread reference.
#		#   It should never be used outside of an emergency SCRAM.
#		self = cls._active_tracers.get(tracer_thread)
#		self._monitoring_thread = tracer_thread
#		return self
		
			
	def __init__(self, thread=None):
		
		self._shutdown = False
		self.monitoring = False
		self.intercepting = False
		self.command = ''
		
		self._dispatch_mapping = dict(
			(event, getattr(self, 'dispatch_%s' % event))
			for event in self._event_labels)
		
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

	def intercept(self):
		self.intercepting = True
		_ = self.__enter__()

	def shutdown(self):
		self.intercepting = False
		self.monitoring = False
		self._shutdown = True

	# History controls

	def _add_context(self, context):
		self.context_buffer.append(context)
		while len(self.context_buffer) > self.CONTEXT_BUFFER_LIMIT:
			_ = self.context_buffer.popleft()


	# Interaction
	
	def _await_input(self):
		self.command = self.sys.stdin.readline()


	# Dispatch

	def dispatch(self, frame, event, arg):
		if self.monitoring:
			# Check if execution should be intercepted for debugging
			if self.intercept_context(frame, event, arg):
				self._dispatch_mapping.get(event, self._nop)(frame, arg)

				self._await_input()
			return self.dispatch
		else:
			return # none

	def intercept_context(self, frame, event, arg):
		"""Determine if execution should be stopped."""
		# Poorman's decorator
		self.intercepting = self._intercept_context(frame, event, arg)
		return self.intercepting

	def _intercept_context(self, frame, event, arg):
		"""Do the actual interception checks against the context."""
		context = Context(frame, event, arg)
		self._add_context(context)
		
		if self.intercepting:
			return True # if already intercepting, continue

#		if frame in self.stop_frames:
#			return True

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
		try:
			return (self.left(*(getattr(context, field, context[field]) 
								for field 
								in self.left._fields) ) 
					== 
					self.right(*(getattr(context, field, context[field]) 
								 for field 
					 			 in self.right._fields) ) )
		except:
			return False






















def set_trace():
	raise NotImplementedError("TODO: ADD FEATURE")


def record():
	raise NotImplementedError("TODO: ADD FEATURE")




tracer = Tracer(running_thread)





