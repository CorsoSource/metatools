from weakref import WeakValueDictionary
from time import sleep

from shared.tools.thread import getThreadState, Thread

from shared.tools.debug.command import PdbCommands
from shared.tools.debug.hijack import SysHijack
from shared.tools.debug.frame import iter_frames
from shared.tools.debug.breakpoint import Breakpoint

from shared.tools.debug.snapshot import Snapshot

from datetime import datetime, timedelta

from shared.tools.pretty import p,pdir


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
				 

				 '_top_frame',

				 '_FAILSAFE_TIMEOUT', '_debug', # DeprecationWarning
				)

	CONTEXT_BUFFER_LIMIT = 1000
	
	INTERDICTION_FAILSAFE = False # True
	INTERDICTION_FAILSAFE_TIMEOUT = 30000 # milliseconds (seconds if failsafe disabled)
	
	_active_tracers = WeakValueDictionary()
	
	# _event_labels = set(['call', 'line', 'return', 'exception', 
	# 					 'c_call', 'c_return', 'c_exception',
	# 					 ])	
	
	SKIP_NAMESPACES = set([
		'weakref', 'datetime',
		
		])
	
	@staticmethod
	def _nop(frame=None, event=None, arg=None):
		if Tracer.skip_frame(frame):
			return None
		#system.util.getLogger('FAIL').info('%r %r %r' % (p(frame, directPrint=False), event, arg))
		#sleep(0.1)
		return Tracer._nop
	
	@classmethod
	def skip_frame(cls, frame):
		return frame.f_globals.get('__name__') in cls.SKIP_NAMESPACES
	
	
	def __init__(self, thread=None, *args, **kwargs):
		
		super(Tracer, self).__init__(*args, **kwargs)

		self.tracer_thread = Thread.currentThread()
		self.thread = thread
		
		print "Tracing from %r onto %r" % (self.tracer_thread, self.thread)
		
		self.sys = SysHijack(thread)

		self.interdicting = False		

		self._top_frame = None

		self._debug = {}
		
		#start the machinery so we can inject directly
		#self.sys.settrace(Tracer.dispatch)
		self.sys.settrace(Tracer._nop)
		
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
		while frame:
			frame.f_trace = self.dispatch
			# track the furthest up the stack goes
			self._top_frame = frame
			frame = frame.f_back
		#self.sys.settrace(self.dispatch)

	def _stack_uninstall(self):
		"""Turn off trace and remove the trace dispatcher from every level 
		in the stack.
		"""
		if len(self._active_tracers) == 1:
			self.sys.settrace(None)
		frame = self.sys._getframe()
		while frame:
			if frame.f_trace:
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

	@property
	def context_traceback(self):
		return [repr(context) for i, context in enumerate(self.context_buffer) 
				if (len(self.context_buffer) - 20) < i < len(self.context_buffer)]
			

	# Interception detection

	def interdict_context(self, frame, event, arg):
		"""Determine if execution should be stopped."""
		# Poorman's decorator
		self.interdicting = self._interdict_context(frame, event, arg)
		return self.interdicting


	def _interdict_context(self, frame, event, arg):
		"""Do the actual interdiction checks against the context."""		
		if self.interdicting:
			return True # if already interdicting, continue

		if self.active_traps:
			return True

		if Breakpoint.relevant_breakpoints(frame, self):
			return True

		return False 


	# Dispatch
	
	def dispatch(self, frame, event, arg):
		sleep(0.05) # DEBUG
	
		try:
			# Dispatch and continue as normal
			dispatch_retval = super(Tracer, self).dispatch(frame, event, arg)
		
			# Check if execution should be interdicted for debugging
			if self.interdict_context(frame, event, arg):
				self.command_loop()
				
		except Exception, err:
			system.util.getLogger('FAILTRACE').error('Dispatch Error: %r' % err)
		
		if frame.f_trace is None:
			frame.f_trace = self.dispatch
		
		if self.monitoring and not Tracer.skip_frame(frame):
			#self.sys.settrace(Tracer._nop)
			self.sys.settrace(self.dispatch)
		else:
			self.shutdown()
			
		return self.dispatch
		

	# Interaction

	def command_loop(self):
		"""Run commands until interdiction is disabled."""

		if not self.interdicting:
			return
	
		if Thread.currentThread() is self.tracer_thread:
			raise RuntimeError("Await called from the wrong context! %r instead of %r" % (
							self.tracer_thread, self.thread,) )
		
		if self.INTERDICTION_FAILSAFE:
			self._FAILSAFE_TIMEOUT = datetime.now() + timedelta(microseconds=self.INTERDICTION_FAILSAFE_TIMEOUT * 1000)
		
		while self.interdicting:
			if not self._pending_commands:
				sleep(self._UPDATE_CHECK_DELAY)
				if self.INTERDICTION_FAILSAFE and self._FAILSAFE_TIMEOUT < datetime.now():
					self.interdicting = False
					system.util.getLogger('TRACER').warn('Interaction pause timed out!')
		
			while self._pending_commands and self.interdicting:
				#system.util.getLogger('Debug Command').info('Command: %s' % self.command)
				self.command(self._pending_commands.pop())



	# Command overrides

	def _command_step(self, command='step'):
		"""Step into the next function in the current line (or to the next line, if done)."""
		super(Tracer, self)._command_step(command)
		self.interdicting = False
	_command_s = _command_step

	def _command_next(self, command='next'):
		"""Continue to the next line (or return statement). 
		Note step 'steps into a line' (possibly making the call stack deeper)
		  while next goes to the 'next line in this frame'. 
		"""
		super(Tracer, self)._command_next(command)
		self.interdicting = False
	_command_n = _command_next

	def _command_until(self, command='until', target_line=0):
		"""Continue until a higher line number is reached, or optionally target_line."""
		super(Tracer, self)._command_until(command)
		self.interdicting = False
	_command_u = _command_until

	def _command_return(self, command='return'):
		"""Continue until the current frame returns."""
		super(Tracer, self)._command_return(command)
		self.interdicting = False
	RETURN = _command_r = _command_return

	def _command_continue(self, command='continue'):
		"""Resume execution until a breakpoint is reached. Clears all traps."""
		super(Tracer, self)._command_continue(command)
		self.interdicting = False
	_command_c = _command_cont = _command_continue



def set_trace():
	raise NotImplementedError("TODO: ADD FEATURE")


def record():
	raise NotImplementedError("TODO: ADD FEATURE")
