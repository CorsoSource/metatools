from weakref import WeakValueDictionary
from time import sleep

from shared.tools.thread import getThreadState, Thread
from shared.tools.global import ExtraGlobal
from shared.tools.data import randomId

from shared.tools.debug.hijack import SysHijack
from shared.tools.debug.frame import iter_frames
from shared.tools.debug.breakpoint import Breakpoint

from shared.tools.debug.codecache import CodeCache, trace_entry_line
from shared.tools.debug.snapshot import Snapshot

from shared.tools.debug.trap import TransientTrap, Step, Next, Until, Return

from ast import literal_eval
from time import sleep
from collections import deque 
from datetime import datetime, timedelta

from shared.tools.pretty import p,pdir


class Tracer(object):
	"""A variant of the Python Debugger (Pdb)
	
	This is designed to overcome and take advantage of the different
	  constraints that running Pdb in a multi-threaded environment
	  creates.

	Breakpoints are created globally, enabled PER TRACER, and break by default.
	Traps are created for a tracer, enabled by default, and break only on success.

	Breakpoints are evaluated _before_ the line is executed.
	  For example, if a breakpoint is set for the line 'x += 1' and 
	  has a condition 'x == 20', then trace.cursor_frame (lowest frame) will show
	  x is 20, _not_ 21.

	NOTE: If this is activated inline with the code (same thread), it will NOT
	      wait indefinitely. You MUST turn off the Tracer instance's INTERDICTION_FAILSAFE
	      or it will time out quickly!
	  
	For more information and the cool implementation that we're tweaking here,
	  see also rpdb at https://github.com/tamentis/rpdb
	"""
	__slots__ = (
				 # Event attributes
				 '_map_for_dispatch', 
				 'monitoring',

				 # Command attributes

				 '_cursor_index', '_cursor_stack',
				 '_pending_commands', 
				 '_map_o_commands',
				 '_current_context', 'recording', 'context_buffer',
				 
				 '_alias_commands', 
				 'traps', 'active_traps', 
				 
				 # Tracer attributes
				 'thread', 'sys', 'tracer_thread',
				 'interdicting',
				 '_top_frame',

				 'step_speed',
				 '_FAILSAFE_TIMEOUT', '_debug', # DeprecationWarning
				 'logger', 'id',
				 
				 '__weakref__', # Allows the weakref mechanics to work on this slotted class.
				)

	CONTEXT_BUFFER_LIMIT = 1000
	_UPDATE_CHECK_DELAY = 0.01
	INTERDICTION_FAILSAFE = False # True
	INTERDICTION_FAILSAFE_TIMEOUT = 30000 # milliseconds (seconds if failsafe disabled)

	# Set to true to have any active traces using this class to purge themselves (on next call)
	SCRAM_SIGNAL = False
	
	_active_tracers = WeakValueDictionary()
	
	# _event_labels = set(['call', 'line', 'return', 'exception', 
	# 					 'c_call', 'c_return', 'c_exception',
	# 					 ])	
	
	SKIP_NAMESPACES = set([
		'weakref', 'datetime', 		
		])
	
	SKIP_FILES = set([
		'<module:shared.tools.debug.breakpoint>',
		'<module:shared.tools.debug.codecache>',
		'<module:shared.tools.debug.frame>',
		'<module:shared.tools.debug.hijack>',
		'<module:shared.tools.debug.proxy>',
		'<module:shared.tools.debug.snapshot>',
		'<module:shared.tools.debug.tracer>',
		'<module:shared.tools.debug.trap>',
		])

	def __init__(self, thread=None, *args, **kwargs):
	
		self.id = randomId()
		self.logger = system.util.getLogger('Tracer %s' % self.id)

		# Event init
		
		self.monitoring = False

		self._map_for_dispatch = dict(
			(attribute[10:], getattr(self, attribute))
			for attribute in dir(self)
			if attribute.startswith('_dispatch_'))

		# Command init

		self._map_o_commands = dict(
			(attribute[9:], getattr(self, attribute))
			for attribute in dir(self)
			if attribute.startswith('_command_'))
		
		self._pending_commands = []

		self._cursor_index = 0
		self._cursor_stack = tuple()

		self.recording = record
		self.context_buffer = deque()
		self._current_context = None

		self._alias_commands = {}
		self.traps = set()
		self.active_traps = set()

		# Tracer init

		self.tracer_thread = Thread.currentThread()
		self.thread = thread or self.tracer_thread
		
		self.logger.info("Tracing [%s] from %r onto %r" % (self.id, self.tracer_thread, self.thread))
		
		self.sys = SysHijack(self.thread)

		self.interdicting = False		

		self._top_frame = None

		self._debug = {}
		
		#start the machinery so we can inject directly
		#self.sys.settrace(Tracer.dispatch)
		self.sys.settrace(Tracer._nop)
		
		self._active_tracers[thread] = self
		ExtraGlobal.stash(self, self.id, scope='Tracer', callback=lambda self=self: self)
		
		self._FAILSAFE_TIMEOUT = datetime.now()

		self.step_speed = 0


	@classmethod
	def _scram(cls, base_frame):
		# Clear out any active traces running
		for frame in iter_frames(base_frame):
			if frame.f_trace:
				del frame.f_trace
		
		# Attempt to ask all the active tracers to gracefully unwind
		for tracer in cls._active_tracers.values():
			try:
				tracer.shutdown()
			except:
				pass

	@classmethod
	def _nop(cls, frame=None, event=None, arg=None):
		if cls.SCRAM_SIGNAL:
			cls._scram(frame)
			return None
			
		if cls.skip_frame(frame):
			return None
		
		#self.logger.info('NOP(): %r %r %r' % (p(frame, directPrint=False), event, arg))
		#sleep(0.1)
		return cls._nop
	
	@classmethod
	def skip_frame(cls, frame):
		return any((
			frame.f_globals.get('__name__') in cls.SKIP_NAMESPACES,
			frame.f_code.co_filename in cls.SKIP_FILES,
			))

	#--------------------------------------------------------------------------
	# Context control - start and stop active tracing
	#--------------------------------------------------------------------------


	def __enter__(self):
		self.monitor()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.shutdown()


	#--------------------------------------------------------------------------
	# Un/Install to the call stack
	#--------------------------------------------------------------------------

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
		
		# Trace is already initialized by this point, and setting
		#  the frame's trace ensures dispatch will trigger on the
		#  next line. That dispatch will call sys.settrace as well,
		#  but strictly from within the target thread.
		#self.sys.settrace(self.dispatch)


	def _stack_uninstall(self):
		"""Turn off trace and remove the trace dispatcher from every level 
		in the stack.
		"""
		self.sys.settrace(None)
		
		frame = self.sys._getframe()
		while frame:
			if frame.f_trace:
				del frame.f_trace
			frame = frame.f_back


	#--------------------------------------------------------------------------
	# Run state status controls
	#--------------------------------------------------------------------------

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


	#==========================================================================
	# Convenience properties
	#==========================================================================
	
	@property
	def debug(self):
		return self._debug

	@property 
	def cursor_frame(self):
		# Override to fail safe to local context (if we're not actively monitoring...)
		if self._cursor_index < len(self._cursor_stack):
			return self._cursor_stack[self._cursor_index]
		else:
			return self.sys._getframe()
	@property 
	def cursor_locals(self):
		return self.cursor_frame.f_locals
	@property
	def cursor_globals(self):
		return self.cursor_frame.f_globals

	@property
	def current_context(self):
		return self._current_context

	@property
	def context_traceback(self):
		return [repr(context) for i, context in enumerate(self.context_buffer) 
				if (len(self.context_buffer) - 20) < i < len(self.context_buffer)]

	@property
	def stdin_log(self):
		return self.sys._io_proxy.stdin.history
	@property
	def stdout_log(self):
		return self.sys._io_proxy.stdout.history
	@property
	def stderr_log(self):
		return self.sys._io_proxy.stderr.history

	
	#==========================================================================
	# Interdiction Triggers
	#==========================================================================

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


	def check_traps(self):
		"""Check any traps, and mark them active if the context triggers it.

		Any transient traps are removed when placed on the active set.
		"""		
		self.active_traps = set()
		for trap in frozenset(self.traps):
			if trap.check(self.current_context):
				
				#self.logger.info('TRIP: %r on %r' % (trap, self.current_context,))
				
				if isinstance(trap, TransientTrap):
					self.active_traps.add(trap)
					self.traps.remove(trap)
				else:
					self.active_traps.add(trap)
					
		#if not self.active_traps:
		#	self.logger.info('No active traps on %r' % (self.current_context,))


	#==========================================================================
	# Trace Events
	#==========================================================================


	#--------------------------------------------------------------------------
	# Dispatch
	#--------------------------------------------------------------------------
	
	def dispatch(self, frame, event, arg):
		if self.SCRAM_SIGNAL:
			self._scram(frame)
			return None

		if not self.monitoring:
			return None

		if self.skip_frame(frame):
			return None

		if self.step_speed:
			sleep(self.step_speed) # DEBUG
		
		self._cursor_stack = tuple(iter_frames(frame))
		self._current_context = Snapshot(frame, event, arg, clone=self.recording)
		
		if self.recording:
			self.context_buffer.append(self._current_context)
		while len(self.context_buffer) > self.CONTEXT_BUFFER_LIMIT:
			_ = self.context_buffer.popleft()


		self.logger.info('%r' % self._current_context)

		# From user code to overrides, this is the section that can go wrong.
		# Blast shield this with a try/except
		try:
			# Dispatch and continue as normal
			# Note that we don't really do anything with this...
			#   The rest of the function determines how we reply to sys' trace
			dispatch_retval = self._map_for_dispatch.get(event, self._nop)(frame, arg)
			
			self.check_traps()

			# Check if execution should be interdicted for debugging
			if self.interdict_context(frame, event, arg):
				self.command_loop()
				
		except Exception, err:
			self.logger.error('Dispatch Error: %r' % err)
		

		# Ensure trace continues in this context
		if frame.f_trace is None:
			frame.f_trace = self.dispatch
		
		# Ideally we'd use sys.gettrace but that ain't a thing in Jython 2.5
		if self.monitoring and not Tracer.skip_frame(frame):
			self.sys.settrace(self.dispatch)
		else:
			self.shutdown()
		
		# TRAMPOLINE GOOOOO
		return self.dispatch
		

	#--------------------------------------------------------------------------
	# Event Dispatch
	#--------------------------------------------------------------------------

	def _dispatch_call(self, frame, _=None):
		self.on_call(frame)

	def _dispatch_line(self, frame, _=None):
		self.on_line(frame)

	def _dispatch_return(self, frame, return_value):
		self.on_return(frame, return_value)

	def _dispatch_exception(self, frame, (exception, value, traceback)):
		self.on_exception(frame, (exception, value, traceback))


	# Jython shouldn't ever call these, so they're here for completeness/compliance
	def _dispatch_c_call(self, frame, _=None):
		pass
	def _dispatch_c_return(self, frame, return_value):
		pass
	def _dispatch_c_exception(self, frame, (exception, value, traceback)):
		pass


	#--------------------------------------------------------------------------
	# User overridable hooks
	#--------------------------------------------------------------------------
	
	def on_call(self, frame):
		pass
	def on_line(self, frame):
		pass
	def on_return(self, frame, return_value):
		pass
	def on_exception(self, frame, (exception, value, traceback)):
		pass


	#==========================================================================
	# Interaction
	#==========================================================================


	def command(self, command):
		"""Interpret commands like PDB: '!' means execute, 
		otherwise it's a command word followed by optional arguments.
		"""
		if not command:
			return

		if command.lstrip()[0] == '!':
			return self._command_statement(command)
		else:
			args = []
			for arg in command.split():
				try:
					args.append(literal_eval(arg))
				except ValueError:
					args.append(arg)
			return self._map_o_commands.get(args[0], self._command_default)(command, *args[1:])


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

				# Failsafe off ramp
				if self.INTERDICTION_FAILSAFE and self._FAILSAFE_TIMEOUT < datetime.now():
					self.interdicting = False
					self.logger.warn('Interaction pause timed out!')
		
			while self._pending_commands and self.interdicting:
				#self.logger.info('Command: %s' % self.command)
				self.command(self._pending_commands.pop())

	
	def _await_pause(self):
		while not self._pending_commands:
			sleep(self._UPDATE_CHECK_DELAY)


	def _compile(self, expression, mode='eval'):
		return self.sys.builtins['compile'](expression, '<tracer:expression>', mode)
	
	def cursor_eval(self, expression):
		code = self._compile(expression)
		return self.sys.builtins['eval'](code, self.cursor_frame.f_globals, self.cursor_frame.f_locals)
		

	#==========================================================================
	# PDB Commands
	#==========================================================================


	#--------------------------------------------------------------------------
	# Meta commands
	#--------------------------------------------------------------------------


	def _command_help(self):
		"""Print available commands. If given a command print the command data."""
		raise NotImplementedError
	_command_h = _command_help


	def _command_where(self):
		"""Print a stack trace, with the most recent frame at the bottom, pointing to cursor frame."""
		stack = [trace_entry_line(frame, indent= ('-> ' if index == self._cursor_index else '   ') )
				 for index, frame
				 in iter_frames(self.cursor_frame)]

		return '\n'.join(reversed(stack))

	_command_w = _command_where 


	def _command_down(self):
		"""Move the cursor to a more recent frame (down the stack)"""
		if self._cursor_index:
			self._cursor_index -= 1
	_command_d = _command_down


	def _command_up(self):
		"""Move the cursor to an older frame (up the stack)"""
		if self._cursor_index < (len(self._cursor_stack) - 1):
			self._cursor_index += 1
	_command_u = _command_up


	#--------------------------------------------------------------------------
	# Breakpoint controls
	#--------------------------------------------------------------------------


	def _command_clear(self, command='clear', *breakpoints):
		"""Clear breakpoint(s).

		Breakpoints can be by ID, location, or instance.

		If none are provided, clear all after confirmation. (Pulled off _pending_commands)
		"""
		breakpoints = Breakpoint.resolve_breakpoints(breakpoints)

		if not breakpoints:
			print "Please confirm clearing all breakpoints (yes/no)"
			self._await_pause()
			command = self._pending_commands.pop()
			if command.lower() in ('y','yes',):
				breakpoints = Breakpoint._instances.values()
			else:
				print "Breakpoints were not cleared."
				return

		for breakpoint in breakpoints:
			breakpoint._remove()

	_command_cl = _command_clear


	def _command_enable(self, command='enable', *breakpoints):
		"""Enable the breakpoints"""
		breakpoints = Breakpoint.resolve_breakpoints(breakpoints)

		for breakpoint in breakpoints:
			breakpoint.enable(self)


	def _command_disable(self, command='disable', *breakpoints):
		"""Disable the breakpoints"""
		breakpoints = Breakpoint.resolve_breakpoints(breakpoints)

		for breakpoint in breakpoints:
			breakpoint.disable(self)


	def _command_ignore(self, command='ignore', breakpoint=None, num_passes=0):
		"""Run past breakpoint num_passes times. 
		Once count goes to zero the breakpoint activates."""
		if breakpoint is None:
			return
		breakpoint.ignore(self, num_passes)


	def _command_break(self, command='break', stop_location='', stop_condition=lambda:True):
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


	def _command_tbreak(self, command='tbreak', stop_location='', stop_condition=lambda:True):
		"""Create a temporary breakpoint at the given location. Same usage otherwise as break."""
		raise NotImplementedError


	def _command_condition(self, command='condition', breakpoint=None, condition=None):
		"""Stop on breakpoint if condition is True"""
		if condition is None:
			raise RuntimeError("Condition is required for conditional breakpoints.")
		raise NotImplementedError


	def _command_commands(self, command='commands', breakpoint=None):
		"""Run commands when breakpoint is reached. 
		Commands entered will be assigned to this breakpoint until 'end' is seen.

		To clear a breakpoint's commands, enter this mode and enter 'end' immediately.

		Any command that resumes execution will prematurely end command list execution.
		  (This is continue, step, next, return, jump, quit)

		Entering 'silent' will run the breakpoint commands but not stop.
		"""
		if breakpoint is None:
			raise RuntimeError("In order for commands to be run on a breakpoint, a breakpoint is needed.")
		raise NotImplementedError


	#--------------------------------------------------------------------------
	# Execution control
	#--------------------------------------------------------------------------


	def _command_step(self, command='step'):
		"""Step into the next function in the current line (or to the next line, if done)."""
		self.traps.add(Step())
		self.interdicting = False
	_command_s = _command_step


	def _command_next(self, command='next'):
		"""Continue to the next line (or return statement). 
		Note step 'steps into a line' (possibly making the call stack deeper)
		  while next goes to the 'next line in this frame'. 
		"""
		self.traps.add(Next(self.current_context))
		self.interdicting = False
	_command_n = _command_next


	def _command_until(self, command='until', target_line=0):
		"""Continue until a higher line number is reached, or optionally target_line."""
		self.traps.add(Until(self.current_context))
		self.interdicting = False
	_command_u = _command_until


	def _command_return(self, command='return'):
		"""Continue until the current frame returns."""
		self.traps.add(Return(self.current_context))
		self.interdicting = False
	_command_r = _command_return


	def _command_continue(self, command='continue'):
		"""Resume execution until a breakpoint is reached. Clears all traps."""
		self.traps = set()
		self.interdicting = False
	_command_c = _command_cont = _command_continue


	def _command_jump(self, command='jump', target_line=0):
		"""Set the next line to be executed. Only possible in the bottom frame.
		
		Use this to re-run code or skip code in the current frame.
		NOTE: You can note jump into the middle of a for loop or out of a finally clause.
		"""
		if target_line == 0:
			raise RuntimeError('Jump lines are in the active frame only, and must be within range')
		raise NotImplementedError
	_command_j = _command_jump


	#--------------------------------------------------------------------------
	# Info commands
	#--------------------------------------------------------------------------


	def _command_list(self, command='list', first=0, last=0):
		"""List the source code for the current file, +/- 5 lines.
		Given just first, show code +/- 5 lines around first.
		Given first and last show code between the two given line numbers.
		If last is less than first it goes last lines past the first. 
		"""
		code_lines = CodeCache.get_lines(self.cursor_frame, radius=0, sys_context=self.sys)

		if not code_lines:
			self.logger.warn('Code is empty in listing: %s %d %d' % (command, first, last))
			
		if last == 0:
			if first == 0:
				start = self.cursor_frame.f_lineno - 5
				end   = self.cursor_frame.f_lineno + 5
			else:
				start = first - 5
				end   = first + 5
		else:
			if last < first:
				start = first
				end   = first + last
			else:
				start = first
				end   = last
		
		# sanity check
		if start < 0:
			start = 0
		if end >= len(code_lines):
			end = len(code_lines) - 1

		return code_lines[start:end]
	_command_l = _command_list


	def _command_args(self, command='args'):
		"""Show the argument list to this function."""
		frame = self.cursor_frame
		frame_code = frame.f_code
		argnames = frame_code.co_varnames[:frame_code.co_argcount]
		return dict((name, frame.f_locals[name]) for name in argnames)
	_command_a = _command_args


	def _command_p(self, command='p', expression=''):
		"""Print the expression."""
		if expression == '':
			return
		return p(self.cursor_eval(expression), directPrint=False)


	def _command_pp(self, command='pp', expression=''):
		"""Print the expression via pretty printing. This is actually how p works, too."""
		if expression == '':
			return
		return p(self.cursor_eval(expression), directPrint=False)


	def _command_pdir(self, command='pdir', expression='', skip_private=True):
		"""Print the expression via pretty printing. This is actually how p works, too."""
		if expression == '':
			return
		return pdir(self.cursor_eval(expression), skipPrivate=skip_private, directPrint=False)
		
		
	def _command_alias(self, command='alias', name='', command_string=''):
		"""Create an alias called name that executes command. 
		If no command, then show what alias is. If no name, then show all aliases.

		NOTE: The command should not be in quotes.

		Parameters can be indicated by %1, %2, and so on, while %* is replaced by all parameters.
		"""
		raise NotImplementedError


	def _command_unalias(self, command='unalias', name=''):
		"""Delete the specified alias."""
		if not name:
			raise RuntimeError("Unalias must have a name to, well, un-alias.")
		raise NotImplementedError


	def _command_statement(self, raw_command, *tokens):
		"""Execute the (one-line) statement. 
		Start the statement with '!' if it starts with a command.

		To set a global variable, prefix the assignment command with `global`
		  (IPDB) global list_options; list_options['-1']
		"""
		# remove '!' or 'statement' from start first!
		raw_command = raw_command.strip()
		if raw_command.startswith('!'):
			raw_command = raw_command[1:].strip()
		elif raw_command.startswith('statement'):
			raw_command = raw_command[10:].strip()
			
		if isinstance(raw_command, (str, unicode)):
			raw_command += '\n'
		
		code = self._compile(raw_command, mode='exec')
		
		frame = self.cursor_frame
		exec code in frame.f_globals, frame.f_locals	

		# DO NOT RUN THIS - Frames can't be generated from within the Python
		#   engine, it seems, and this just... locks everything up.
		# frame = self.cursor_frame
		# thread_state = self.sys._thread_state
		# code.call(thread_state, frame)
	_command_default = _command_bang = _command_statement


	def _command_run(self, command, *args):
		"""Restart the debugged program. This is not and will not be implemented."""
		raise NotImplementedError("IPDB will not implement the 'run' command.")
	

	def _command_quit(self, command):
		"""Quit the debugger. Unlike in PDB, this will _not_ kill the program thread."""
		self.shutdown()
		self.sys._restore()
	_command_shutdown = _command_die = _command_q = _command_quit



def set_trace():
	raise NotImplementedError("TODO: ADD FEATURE")


def record():
	raise NotImplementedError("TODO: ADD FEATURE")
