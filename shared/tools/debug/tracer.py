from weakref import WeakValueDictionary
from collections import deque 
from time import sleep

from shared.tools.thread import getThreadState

try:
	from shared.tools.debug.command import PdbCommands
	from shared.tools.debug.event import EventDispatch
	from shared.tools.debug.snapshot import Snapshot
	from shared.tools.debug.hijack import SysHijack
except ImportError:
	from metatools.debug.command import PdbCommands
	from metatools.debug.event import EventDispatch
	from metatools.debug.snapshot import Snapshot
	from metatools.debug.hijack import SysHijack


class TracerEvents(EventDispatch):
	pass


class Tracer(TracerEvents, PdbCommands):
	"""A variant of the Python Debugger (Pdb)
	
	This is designed to overcome and take advantage of the different
	  constraints that running Pdb in a multi-threaded environment
	  creates.
	  
	For more information and the cool implementation that we're tweaking here,
	  see also rpdb at https://github.com/tamentis/rpdb
	"""
	__slots__ = ('thread', 'sys',
				 'intercepting',
				 'context_buffer',

				 '_bottom_frame',

				 '_debug', '_cursor_frame', # DeprecationWarning
				 
			#####	 'monitoring', 'tracing',
				)

	CONTEXT_BUFFER_LIMIT = 1000
		
	_active_tracers = WeakValueDictionary()
	
	# _event_labels = set(['call', 'line', 'return', 'exception', 
	# 					 'c_call', 'c_return', 'c_exception',
	# 					 ])	
	
	@staticmethod
	def _nop(_0=None, _1=None,_2=None):
		pass		
			
	def __init__(self, thread=None, *args, **kwargs):
		
		super(Tracer, self).__init__(*args, **kwargs)

		self.thread = thread
		self.sys = SysHijack(thread)

		self.intercepting = False
		self.context_buffer = deque()

		self._bottom_frame = None

		self._debug = {}
		self._cursor_frame = None
		
		#start the machinery so we can inject directly
		self.sys.settrace(self._nop)
		
		self._active_tracers[thread] = self


	# Context control - start and stop active tracing

	def __enter__(self):
		self.monitor()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.shutdown()


	# Install and Uninstall self from the call stack

	def _stack_install(self):
		"""Install the trace dispatcher to every level of the stack 
		and then set the trace machinery in motion.
		"""
		frame = self.sys._getframe()
		while frame:
			frame.f_trace = self.dispatch
			# track the furthest down the stack goes
			self._bottom_frame = frame
			frame = frame.f_back
		self.sys.settrace(self.dispatch)

	def _stack_uninstall(self):
		"""Turn off trace and remove the trace dispatcher from every level 
		in the stack.
		"""
		self.sys.settrace(None)
		frame = self.sys._getframe()
		while frame and frame is not self._bottom_frame:
			del frame.f_trace
			frame = frame.f_back

	# Run state status controls

	def monitor(self):
		"""Begin trace, watching each frame event."""
		self.monitoring = True
		self._stack_install()
	
		self._debug['entry'] = self.sys._getframe()		

	def intercept(self):
		"""Begin trace, intercepting each frame event and waiting for commands."""
		self.intercepting = True
		self.monitor()
		
		
	def shutdown(self):
		"""Stop the trace and tear down the setup."""
		self.intercepting = False
		self.monitoring = False
		self._stack_uninstall()


	# Convenience properties
		
	@property
	def current_frame(self):
		return self.sys._getframe()
	@property
	def current_locals(self):
		return self.current_frame.f_locals
	@property
	def current_globals(self):
		return self.current_frame.f_globals

	# History controls

	def _add_context(self, context):
		self.context_buffer.append(context)
		while len(self.context_buffer) > self.CONTEXT_BUFFER_LIMIT:
			_ = self.context_buffer.popleft()
		

	# Interception detection

	def intercept_context(self, frame, event, arg):
		"""Determine if execution should be stopped."""
		# Poorman's decorator
		self.intercepting = self._intercept_context(frame, event, arg)
		return self.intercepting

	def _intercept_context(self, frame, event, arg):
		"""Do the actual interception checks against the context."""
		context = Snapshot(frame, event, arg)
		self._add_context(context)
		
		if self.intercepting:
			return True # if already intercepting, continue

		# if frame in self.stop_frames:
		# 	return True

		return False 


	# Dispatch

	def dispatch(self, frame, event, arg):
		if self.monitoring:
			# Check if execution should be intercepted for debugging
			if self.intercept_context(frame, event, arg):
				self._map_for_dispatch.get(event, self._nop)(frame, arg)

				self.await_comand()
				
			return self.dispatch
		else:
			return # none


	# Interaction

	def await_comand(self):
	
		while not self._pending_commands and self.intercepting:
			sleep(self._UPDATE_CHECK_DELAY)
		
		while self._pending_commands and self.intercepting:
			#system.util.getLogger('Debug Command').info('Command: %s' % self.command)
			self.command(self._pending_commands.pop())








def set_trace():
	raise NotImplementedError("TODO: ADD FEATURE")


def record():
	raise NotImplementedError("TODO: ADD FEATURE")



