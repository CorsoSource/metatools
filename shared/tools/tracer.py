from shared.tools.thread import async, dangerouslyKillThreads

from time import sleep

RUNNING_THREAD_NAME = 'debug_test'

dangerouslyKillThreads(RUNNING_THREAD_NAME, bypass_interlock='Yes, seriously.')

@async(name='debug_test')
def monitored():
	close_loop = False
	
	time_delay = 0.5
	find_me = 0
	
	def bar(x):
		x += 1
		y = x + 2
		return x
		
	while True:
		find_me = bar(find_me)
		
		sleep(time_delay)
		
		if close_loop:
			break
	
	print 'Finished'

running_thread = monitored()


from copy import deepcopy
# from shared.tools.global import ExtraGlobal

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
				except Exception, err:
					local_copy[key] = NotImplemented # p or pdir?
					local_copy['*' + key + '*'] = value
					local_copy['*' + key + '* err'] = err
				
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



class ProxyStream(object):
	"""I/O stream mixin to add history"""

	__slots__ = ('history', '_parent_proxyio')
	_MAX_HISTORY = 1000

	def __init__(self, parent_proxyio=None):
		self.history = deque(['#! Starting log...'])
		self._parent_proxyio = parent_proxyio

	def log(self, string):
		self.history.append(string)
		while len(self.history) > self._MAX_HISTORY:
			_ = self.history.popleft()

	@property
	def parent(self):
		return self._parent


class PatientInputStream(StringIO, ProxyStream):
	
	_SLEEP_RATE = 0.05 # seconds
	
	def __init__(self, buffer='', parent_proxyio=None):
		StringIO.__init__(self, buffer)
		ProxyStream.__init__(self, parent_proxyio)
	
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


class OutputStream(StringIO, ProxyStream):
	
	def __init__(self, buffer='', parent_proxyio=None):
		StringIO.__init__(self, buffer)
		ProxyStream.__init__(self, parent_proxyio)
		
	def write(self, string):
		if string != '\n':
			self.history.append(string)
		StringIO.write(self, string)

	def writelines(self, iterable):
		self.history.append(iterable)
		StringIO.writelines(self, iterable)


class ProxyIO(object):
	"""Control the I/O"""
	
	__slots__ = ('stdin', 'stdout', 'stderr', 'displayhook', '_logger_name', '_coupled_sys')
	
	def __init__(self, coupled_sys=None):
		self._logger_name = 'proxy-io'
		
		self._coupled_sys = coupled_sys
		
		self.stdin = PatientInputStream(parent_proxyio=self)
		self.stdout = OutputStream(parent_proxyio=self)
		self.stderr = OutputStream(parent_proxyio=self)
		self.displayhook = shared.tools.pretty.displayhook
	
	def log(self, s):
		system.util.getLogger(self._logger_name).info(str(s))
	
	@property
	def coupled_sys(self):
		return self._coupled_sys
		
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

	__slots__ = ('_thread_state', '_target_thread', '_io_proxy',
	             '_original_stdin', '_original_stdout', '_original_stderr', '_original_displayhook',
	             )
	
	# _FAILSAFE_TIMEOUT = 20
	
	def __init__(self, thread):
		
		self._target_thread = thread
		#self._thread_state = getThreadState(self._target_thread)
		
		self._io_proxy = ProxyIO(coupled_sys=self)
		
		self._init_time = datetime.now()
		
		self._original_stdin       = self._thread_sys.stdin
		self._original_stdout      = self._thread_sys.stdout
		self._original_stderr      = self._thread_sys.stderr
		self._original_displayhook = self._thread_sys.displayhook
				
		self._install()
		
		# @async(self._FAILSAFE_TIMEOUT)
		# def failsafe_uninstall(self=self):
		# 	self._restore()
		# failsafe_uninstall()
		
	def _install(self):
		"""Redirect all I/O to proxy's endpoints"""
		self._thread_sys.stdin       = self._io_proxy.stdin
		self._thread_sys.stdout      = self._io_proxy.stdout
		self._thread_sys.stderr      = self._io_proxy.stderr
		self._thread_sys.displayhook = self._io_proxy.displayhook
			
	def _restore(self):
		"""Restore all I/O to original's endpoints"""
		self._thread_sys.stdin       = self._original_stdin
		self._thread_sys.stdout      = self._original_stdout
		self._thread_sys.stderr      = self._original_stderr
		self._thread_sys.displayhook = self._original_displayhook
		
	@property
	def _thread_state(self):
		return getThreadState(self._target_thread)
	
	@property
	def _thread_sys(self):
		return self._thread_state.systemState
	

	def __getattr__(self, attribute):
		"""Get from this class first, otherwise use the wrapped item."""
		try:
			return super(SysHijack, self).__getattr__(attribute)
		except AttributeError:
			return getattr(self._thread_sys).__getattr__(attribute)
	
	
	def __setattr__(self, attribute, value):
		"""Set to this class first, otherwise use the wrapped item."""
		try:
			super(SysHijack, self).__setattr__(attribute, value)
		except AttributeError:
			setattr(self._thread_sys, attribute, value)

	@property
	def stdin(self):
		if Thread.currentThread() is self._target_thread:
			return self._io_proxy.stdin
		else:
			return self._original_stdin

	@property
	def stdout(self):
		if Thread.currentThread() is self._target_thread:
			return self._io_proxy.stdout
		else:
			return self._original_stdout
			
	@property
	def stderr(self):
		if Thread.currentThread() is self._target_thread:
			return self._io_proxy.stderr
		else:
			return self._original_stderr
			
	@property
	def displayhook(self):
		if Thread.currentThread() is self._target_thread:
			return self._io_proxy.displayhook
		else:
			return self._original_displayhook
			
			

	def _getframe(self, depth=0):
		#print >>self.stdout, '[~] getting frame %d' % depth
		frame = self._thread_state.frame
		while depth > 0 and frame:
			depth -= 1
			frame = frame.f_back
		return frame

	def settrace(self, tracefunc=None):
		self._thread_sys.settrace(tracefunc)
		# print 'Setting trace function...'
#		code_to_execute = compile('import sys; sys.settrace(new_trace_function)', '<tracer>', 'single')
#		self._thread_sys.builtins['eval'](
#			code_to_execute, 
#			self._thread_state.frame.f_globals, 
#			{'new_trace_function': tracefunc})
#		if tracefunc is None:
#			self._thread_sys.settrace(None)
#		else:			
#			self._thread_sys.settrace(tracefunc)

	def setprofile(self, profilefunc=None):
		if profilefunc is None:
			self._thread_sys.setprofile(None)
		else:
			self._thread_sys.setprofile(profilefunc)


	def __del__(self):
		self._restore()
	


class Tracer(object):
	"""A variant of the Python Debugger (Pdb)
	
	This is designed to overcome and take advantage of the different
	  constraints that running Pdb in a multi-threaded environment
	  creates.
	  
	For more information and the cool implementation that we're tweaking here,
	  see also rpdb at https://github.com/tamentis/rpdb
	"""
	__slots__ = ('thread', 'thread_state', 'active',
				 'sys',
				 'context_buffer', '_dispatch_mapping',
				 'command', 'monitoring', 'intercepting',
				 '_shutdown', '_monitoring_thread',
				 '_debug',
			#####	 'monitoring', 'tracing',
				)

	CONTEXT_BUFFER_LIMIT = 1000
	
	_UPDATE_CHECK_DELAY = 0.01
	
	_active_tracers = WeakValueDictionary()
	
	_event_labels = set(['call', 'line', 'return', 'exception', 
						 'c_call', 'c_return', 'c_exception',
						 ])	
	
	@staticmethod
	def _nop(_0=None, _1=None,_2=None):
		pass		
			
	def __init__(self, thread=None):
		
		self._shutdown = False
		self.monitoring = False
		self.intercepting = False
		self.command = ''
		self._debug = {}
		
		self._dispatch_mapping = dict(
			(event, getattr(self, 'dispatch_%s' % event))
			for event in self._event_labels)
		
		self.thread = thread
		self.thread_state = getThreadState(thread)
		
		self.context_buffer = deque()

		self.sys = SysHijack(thread)
		
		#start the machinery so we can inject directly
		self.sys.settrace(self._nop)
		
		self._active_tracers[thread] = self
		

	# Context control - start and stop active tracing
	def __enter__(self):
		self.monitoring = True
		self.sys._getframe().f_trace = self.dispatch
		#self.sys.settrace(self.dispatch)
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

	@property
	def current_locals(self):
		return self.sys._getframe().f_locals

	@property
	def current_globals(self):
		return self.sys._getframe().f_globals

	# History controls

	def _add_context(self, context):
		self.context_buffer.append(context)
		while len(self.context_buffer) > self.CONTEXT_BUFFER_LIMIT:
			_ = self.context_buffer.popleft()


	# Interaction
	
	def _await_input(self):
	
		while not self.command:
			sleep(self._UPDATE_CHECK_DELAY)
			
		system.util.getLogger('Tracer').info('Command: %s' % self.command)
		self.command = ''


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





