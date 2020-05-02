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
#from shared.tools.global import ExtraGlobal

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
	__slots__ = ('thread', 'thread_state', 'sys',
				 'monitoring', 'intercepting',
				 'context_buffer', 
				 '_map_for_dispatch', '_map_o_commands', 

				 '_pending_commands', '_command', '_alias_commands',

				 '_bottom_frame',

				 '_debug', '_cursor_frame', # DeprecationWarning
				 
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
		
		self.monitoring = False
		self.intercepting = False
		self.context_buffer = deque()

		self._map_for_dispatch = dict(
			(event, getattr(self, 'dispatch_%s' % event))
			for event in self._event_labels)
			
		self._map_o_commands = dict(
			(command, getattr(self, command_method))
			for command_method in dir(self)
			if attribute.startswith('_command_'))
		
		self.command = ''
		self._alias_commands = {}
		self._pending_commands = []

		self._bottom_frame = None

		self._debug = {}
		self._cursor_frame = None


		self.thread = thread
		self.thread_state = getThreadState(thread)
		
		self.sys = SysHijack(thread)
		
		#start the machinery so we can inject directly
		self.sys.settrace(self._nop)
		
		self._active_tracers[thread] = self


	# Context control - start and stop active tracing
	def __enter__(self):
		self.monitor()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.shutdown()

	# Install and Uninstall
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

	# Convenience functions
	@property
	def current_locals(self):
		return self.sys._getframe().f_locals

	@property
	def current_globals(self):
		return self.sys._getframe().f_globals
		
	@property
	def current_frame(self):
		return self.sys._getframe()

	# History controls

	def _add_context(self, context):
		self.context_buffer.append(context)
		while len(self.context_buffer) > self.CONTEXT_BUFFER_LIMIT:
			_ = self.context_buffer.popleft()
		

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

		# if frame in self.stop_frames:
		# 	return True

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


	# Interaction
	
	def await_comand(self):
	
		while not self._pending_commands and self.intercepting:
			sleep(self._UPDATE_CHECK_DELAY)
		
		while self._pending_commands:
			system.util.getLogger('Tracer').info('Command: %s' % self.command)
			self.command(self._pending_commands.pop())	


	def command(self, command):
		"""Run a command or execute a statement.
		
		Commands designed to be compatible with PDB docs
		https://docs.python.org/2.7/library/pdb.html?highlight=pdb#debugger-commands
		"""
		if not command:
			return

		if command.ltrim()[0] == '!':
			self._command_statement(command)
		else:
			args = []
			for arg in command.split():
				try:
					args.append(literal_eval(arg))
				except ValueError:
					args.append(arg)
			self._map_o_commands.get(args[0], self._command_default)(command, *args)


	# Meta commands

	def _command_help(self):
		"""Print available commands. If given a command print the command data."""
		raise NotImplementedError
	_command_h = _command_help

	def _command_where(self):
		"""Print a stack trace, with the most recent frame at the bottom, pointing to cursor frame."""
		raise NotImplementedError
	_command_w = _command_where 

	def _command_down(self):
		"""Move the cursor to a more recent frame (down the stack)"""
	_command_d = _command_down

	def _command_up(self):
		"""Move the cursor to a more recent frame (up the stack)"""
	_command_u = _command_up


	# Breakpoint controls

	def _command_clear(self, command, *breakpoints):
		"""Clear breakpoint(s).

		Breakpoints can be by ID or filename:line number.

		If none are provided, clear all after confirmation. (Pulled off _pending_commands)
		"""
		raise NotImplementedError
	_command_cl = _command_clear

	def _command_enable(self, command, *breakpoints):
		"""Enable the breakpoints"""
		raise NotImplementedError
	def _command_disable(self, command, *breakpoints):
		"""Disable the breakpoints"""
		raise NotImplementedError
	def _command_ignore(self, command, breakpoint, num_passes=0):
		"""Run past breakpoint num_passes times. 
		Once count goes to zero the breakpoint activates."""
		raise NotImplementedError

	def _command_break(self, command, stop_location='', stop_condition=lambda:True):
		"""Create a breakpoint at the given location.
		
		The stop_location can be
		 - a line in the current file
		 - a function in the current file
		 - a filename and line (i.e "shared.tools.debug:45")
		 - a filename and a function (i.e. "shared.tools.meta:getFunctionSigs")

		If a condition is provided, then the breakpoint will be ignored until true.

		If no location or condition is provided, then list all breakpoints:
		 - breakpoint location and ID
		 - number of times hit
		 - remaining ignore count
		 - conditions, if any
		 - is temporary
		"""
		raise NotImplementedError

	def _command_tbreak(self, command, stop_location='', stop_condition=lambda:True):
		"""Create a temporary breakpoint at the given location. Same usage otherwise as break."""
		raise NotImplementedError

	def _command_condition(self, command, breakpoint, condition):
		"""Stop on breakpoint if condition is True"""
		raise NotImplementedError

	def _command_commands(self, command, breakpoint):
		"""Run commands when breakpoint is reached. 
		Commands entered will be assigned to this breakpoint until 'end' is seen.

		To clear a breakpoint's commands, enter this mode and enter 'end' immediately.

		Any command that resumes execution will prematurely end command list execution.
		  (This is continue, step, next, return, jump, quit)

		Entering 'silent' will run the breakpoint commands but not stop.
		"""
		raise NotImplementedError

	# Execution control

	def _command_step(self, command):
		"""Step into the next function in the current line (or to the next line, if done)."""
		raise NotImplementedError
	_command_s = _command_step

	def _command_next(self, command):
		"""Continue to the next line (or return statement). 
		Note step 'steps into a line' (possibly making the call stack deeper)
		  while next goes to the 'next line in this frame'. 
		"""
		raise NotImplementedError
	_command_n = _command_next

	def _command_until(self, command, target_line=0):
		"""Continue until a higher line number is reached, or optionally target_line."""
		raise NotImplementedError
	_command_u = _command_until

	def _command_return(self, command):
		"""Continue until the current frame returns."""
		raise NotImplementedError
	_command_r = _command_return

	def _command_continue(self, command):
		"""Resume execution until a breakpoint is reached."""
		raise NotImplementedError
	_command_c = _command_cont = _command_continue

	def _command_jump(self, command, target_line):
		"""Set the next line to be executed. Only possible in the bottom frame.
		
		Use this to re-run code or skip code in the current frame.
		NOTE: You can note jump into the middle of a for loop or out of a finally clause.
		"""
		raise NotImplementedError
	_command_j = _command_jump


	# Info commands

	def _command_list(self, command, first=0, last=0):
		"""List the source code for the current file, +/- 5 lines.
		Given just first, show code +/- 5 lines around first.
		Given first and last show code between the two given line numbers.
		If last is less than first it goes last lines past the first. 
		"""
		raise NotImplementedError
	_command_l = _command_list

	def _command_args(self, command):
		"""Show the argument list to this function."""
		raise NotImplementedError
	_command_a = _command_args

	def _command_p(self, command, expression):
		"""Print the expression."""
		raise NotImplementedError

	def _command_pp(self, command, expression):
		"""Print the expression via pretty printing. This is actually how p works, too."""
		raise NotImplementedError

	def _command_alias(self, command, name='', command=''):
		"""Create an alias called name that executes comand. 
		If no command, then show what alias is. If no name, then show all aliases.

		NOTE: The command should not be in quotes.

		Parameters can be indicated by %1, %2, and so on, while %* is replaced by all parameters.
		"""
		raise NotImplementedError

	def _command_unalias(self, command, name):
		"""Delete the specified alias."""
		raise NotImplementedError

	def _command_statement(self, raw_command, *tokens):
		"""Execute the (one-line) statement. 
		Start the statement with '!' if it starts with a command.

		To set a global variable, prefix the assignment command with `global`
		  (IPDB) global list_options; list_options['-1']
		"""
		# remove '!' or 'statement' from start first!
		raise NotImplementedError
	_command_default = _command_bang = _command_statement

	def _command_run(self, command, *args):
		"""Restart the debugged program. This is not and will not be implemented."""
		raise NotImplementedError("IPDB will not implement the 'run' command.")
	
	def _command_quit(self, command):
		"""Quit the debugger. Unlike in PDB, this will _not_ kill the program thread."""
		self.shutdown()
		self.sys._restore()
	_command_shutdown = _command_die = _command_q = _command_quit


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





