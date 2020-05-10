from weakref import WeakValueDictionary
from collections import deque 
from time import sleep

from shared.tools.thread import getThreadState, Thread

from shared.tools.debug.command import PdbCommands
from shared.tools.debug.snapshot import Snapshot
from shared.tools.debug.hijack import SysHijack
from shared.tools.debug.frame import iter_frames
from shared.tools.debug.breakpoint import Breakpoint

from datetime import datetime, timedelta


class Tracer(PdbCommands):
	"""A variant of the Python Debugger (Pdb)
	
	This is designed to overcome and take advantage of the different
	  constraints that running Pdb in a multi-threaded environment
	  creates.
	  
	For more information and the cool implementation that we're tweaking here,
	  see also rpdb at https://github.com/tamentis/rpdb
	"""
	__slots__ = ('thread', 'sys', 'tracer_thread',
				 'interdicting',
				 
				 'recording', 'context_buffer',

				 '_top_frame',

				 '_FAILSAFE_TIMEOUT', '_debug', # DeprecationWarning
				)

	CONTEXT_BUFFER_LIMIT = 1000
	
	INTERDICTION_FAILSAFE = True
	INTERDICTION_FAILSAFE_TIMEOUT = 30000 # milliseconds (seconds if failsafe disabled)
	
	_active_tracers = WeakValueDictionary()
	
	# _event_labels = set(['call', 'line', 'return', 'exception', 
	# 					 'c_call', 'c_return', 'c_exception',
	# 					 ])	
	
	@staticmethod
	def _nop(_0=None, _1=None,_2=None):
		pass		
			
	def __init__(self, thread=None, record=False, *args, **kwargs):
		
		super(Tracer, self).__init__(*args, **kwargs)

		self.tracer_thread = Thread.currentThread()
		self.thread = thread
		
		print "Tracing from %r onto %r" % (self.tracer_thread, self.thread)
		
		self.sys = SysHijack(thread)

		self.interdicting = False
		self.context_buffer = deque()
		self.recording = record
 
		self._top_frame = None

		self._debug = {}
		
		#start the machinery so we can inject directly
		self.sys.settrace(self._nop)
		
		self._active_tracers[thread] = self
		self._FAILSAFE_TIMEOUT = datetime.now()


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
		
		self.debug['on_install'] = Snapshot(frame, 'install', 'init', tuple())
		
		while frame:
			frame.f_trace = self.dispatch
			# track the furthest up the stack goes
			self._top_frame = frame
			frame = frame.f_back
		# self.sys.settrace(self.dispatch)

	def _stack_uninstall(self):
		"""Turn off trace and remove the trace dispatcher from every level 
		in the stack.
		"""
		self.sys.settrace(None)
		frame = self.sys._getframe()
		while frame:
			if frame.f_trace is self.dispatch:
				del frame.f_trace
			frame = frame.f_back


	# Run state status controls

	def monitor(self):
		"""Begin trace, watching each frame event."""
		self.monitoring = True
		self._stack_install()
	
		self._debug['entry'] = self.sys._getframe()		

	def interdict(self):
		"""Begin trace, interdicting each frame event and waiting for commands."""
		self.interdicting = True
		self.monitor()		
		
	def shutdown(self):
		"""Stop the trace and tear down the setup."""
		self.interdicting = False
		self.monitoring = False
		try:
			self._stack_uninstall()
			self.sys._restore()
		except:
			raise RuntimeError('Tracer shutdown gracelessly - traced thread is likely already dead and cleanup thus failed.')

	# Convenience properties
	
	@property
	def debug(self):
		return self._debug

	@property 
	def cursor_frame(self):
		# Override to fail safe to local context (if we're not actively monitoring...)
		f = super(Tracer, self).cursor_frame
		return f if f else self.sys._getframe()

	# Reference controls

	def _add_context(self, context):
		if self.recording:
			self.context_buffer.append(context)
		while len(self.context_buffer) > self.CONTEXT_BUFFER_LIMIT:
			_ = self.context_buffer.popleft()
		

	# Interception detection

	def interdict_context(self, frame, event, arg):
		"""Determine if execution should be stopped."""
		# Poorman's decorator
		self.interdicting = self._interdict_context(frame, event, arg)
		return self.interdicting


	def _interdict_context(self, frame, event, arg):
		"""Do the actual interdiction checks against the context."""
		context = Snapshot(frame, event, arg, clone=self.recording)
		self._add_context(context)
		
		if self.interdicting:
			return True # if already interdicting, continue

		if any(self.active_traps(context)):
			return True

		if Breakpoint.relevant_breakpoints(frame, self):
			return True

		return False 


	def active_traps(self, context):
		raise NotImplementedError


	# Dispatch

	def dispatch(self, frame, event, arg):
		# Dispatch and continue as normal
		dispatch_retval = super(Tracer, self).dispatch(frame, event, arg)

		# Check if execution should be interdicted for debugging
		if self.interdict_context(frame, event, arg):
			self.await_comand()
		
		return dispatch_retval

	# Interaction

	def await_comand(self):
	
		if Thread.currentThread() is self.tracer_thread:
			raise RuntimeError("Await called from the wrong context! %r instead of %r" % (
							self.tracer_thread, self.thread,) )
		
		if self.INTERDICTION_FAILSAFE:
			self._FAILSAFE_TIMEOUT = datetime.now() + timedelta(microseconds=self.INTERDICTION_FAILSAFE_TIMEOUT * 1000)
		
		while not self._pending_commands and self.interdicting:
			sleep(self._UPDATE_CHECK_DELAY)
			if self.INTERDICTION_FAILSAFE and self._FAILSAFE_TIMEOUT < datetime.now():
				self.interdicting = False
				system.util.getLogger('TRACER').warn('Interaction pause timeed out!')
		
		while self._pending_commands and self.interdicting:
			#system.util.getLogger('Debug Command').info('Command: %s' % self.command)
			self.command(self._pending_commands.pop())








def set_trace():
	raise NotImplementedError("TODO: ADD FEATURE")


def record():
	raise NotImplementedError("TODO: ADD FEATURE")
