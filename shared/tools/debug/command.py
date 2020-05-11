
from shared.tools.debug.frame import iter_frames
from shared.tools.debug.codecache import CodeCache, trace_entry_line
from shared.tools.debug.breakpoint import Breakpoint
from shared.tools.debug.event import EventDispatch
from shared.tools.debug.snapshot import Snapshot

from shared.tools.debug.trap import TransientTrap, Step, Next, Until, Return

from ast import literal_eval
from time import sleep
from collections import deque 




class Commands(EventDispatch):

	__slots__ = ('_cursor_index', '_cursor_stack',
				 '_pending_commands', 
				 '_map_o_commands',
				 '_current_context', 'recording', 'context_buffer',
				 )

	_UPDATE_CHECK_DELAY = 0.01


	def __init__(self, record=False, *args, **kwargs):

		super(Commands, self).__init__(*args, **kwargs)

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


	# Dispatch
	def dispatch(self, frame, event, arg):
		self._cursor_stack = tuple(iter_frames(frame))
		self._current_context = Snapshot(frame, event, arg, clone=self.recording)
		self._add_context(self.current_context)

		return super(Commands, self).dispatch(frame, event, arg)


	# Convenience properties

	@property 
	def cursor_frame(self):
		if self._cursor_index < len(self._cursor_stack):
			return self._cursor_stack[self._cursor_index]
		else:
			return None
	@property 
	def cursor_locals(self):
		return self.cursor_frame.f_locals
	@property
	def cursor_globals(self):
		return self.cursor_frame.f_globals
	@property
	def current_context(self):
		return self._current_context


	# Reference controls

	def _add_context(self, context):
		if self.recording:
			self.context_buffer.append(context)
		while len(self.context_buffer) > self.CONTEXT_BUFFER_LIMIT:
			_ = self.context_buffer.popleft()


	# Interaction
	
	def _await_pause(self):
		while not self._pending_commands:
			sleep(self._UPDATE_CHECK_DELAY)
		

	def await_comand(self):
	
		self._await_pause()
		
		while self._pending_commands:
			#system.util.getLogger('Debug Command').info('Command: %s' % self.command)
			self.command(self._pending_commands.pop())	

	def command(self, command):
		"""Run the method associated with a command"""
		self._map_o_commands.get(command, self._command_default)(command)

	def _command_default(self, command, *args):
		pass



class PdbCommands(Commands):
	"""Run a command or execute a statement.
	
	Commands designed to be compatible with PDB docs
	https://docs.python.org/2.7/library/pdb.html?highlight=pdb#debugger-commands
	"""

	__slots__ = ('_alias_commands', 
				 'traps', 'active_traps', 
				 )

	def __init__(self, *args, **kwargs):
		super(PdbCommands, self).__init__(*args, **kwargs)
		self._alias_commands = {}
		self.traps = set()
		self.active_traps = set()


	def dispatch(self, frame, event, arg):
		ret_val = super(PdbCommands, self).dispatch(frame, event, arg)
		self.check_traps()
		# do something with the traps, then return
		return ret_val

	def check_traps(self):
		"""Check any traps, and mark them active if the context triggers it.

		Any transient traps are removed when placed on the active set.
		"""		
		self.active_traps = set()
		for trap in frozenset(self.traps):
			if trap.check(self.current_context):
				
				system.util.getLogger('FAILTRACE').info('TRIP: %r on %r' % (trap, self.current_context,))
				
				if isinstance(trap, TransientTrap):
					self.active_traps.add(trap)
					self.traps.remove(trap)
				else:
					self.active_traps.add(trap)
					
		if not self.active_traps:
			system.util.getLogger('FAILTRACE').info('No active traps on %r' % (self.current_context,))
		


	def command(self, command):
		"""Interpret commands like PDB: '!' means execute, 
		otherwise it's a command word followed by optional arguments.
		"""
		if not command:
			return

		if command.lstrip()[0] == '!':
			self._command_statement(command)
		else:
			args = []
			for arg in command.split():
				try:
					args.append(literal_eval(arg))
				except ValueError:
					args.append(arg)
			self._map_o_commands.get(args[0], self._command_default)(command, *args[1:])


	# Meta commands

	def _command_help(self):
		"""Print available commands. If given a command print the command data."""
		raise NotImplementedError
	_command_h = _command_help


	def _command_where(self):
		"""Print a stack trace, with the most recent frame at the bottom, pointing to cursor frame."""
		stack = [trace_entry_line(frame, indent= ('-> ' if index == self._cursor_index else '   ') )
				 for index, frame
				 in iter_frames(self.current_frame)]

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


	# Breakpoint controls

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

	# Execution control

	def _command_step(self, command='step'):
		"""Step into the next function in the current line (or to the next line, if done)."""
		self.traps.add(Step())
	_command_s = _command_step

	def _command_next(self, command='next'):
		"""Continue to the next line (or return statement). 
		Note step 'steps into a line' (possibly making the call stack deeper)
		  while next goes to the 'next line in this frame'. 
		"""
		self.traps.add(Next(self.current_context))
	_command_n = _command_next

	def _command_until(self, command='until', target_line=0):
		"""Continue until a higher line number is reached, or optionally target_line."""
		self.traps.add(Until(self.current_context))
	_command_u = _command_until

	def _command_return(self, command='return'):
		"""Continue until the current frame returns."""
		self.traps.add(Return(self.current_context))
	_command_r = _command_return

	def _command_continue(self, command='continue'):
		"""Resume execution until a breakpoint is reached. Clears all traps."""
		self.traps = set()
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


	# Info commands

	def _command_list(self, command='list', first=0, last=0):
		"""List the source code for the current file, +/- 5 lines.
		Given just first, show code +/- 5 lines around first.
		Given first and last show code between the two given line numbers.
		If last is less than first it goes last lines past the first. 
		"""
		code = CodeCache.get_lines(self.current_frame)

		if not last:
			start = first - 5
			end = first + 5
		else:
			if last < first:
				start = first
				end = first + last
			else:
				start = first
				end = last
		
		# sanity check
		if start < 0:
			start = 0
		if end >= len(code):
			end = len(code) - 1

		return code[start:end]


	_command_l = _command_list

	def _command_args(self, command='args'):
		"""Show the argument list to this function."""
		raise NotImplementedError
	_command_a = _command_args

	def _command_p(self, command='p', expression=''):
		"""Print the expression."""
		if expression == '':
			return
		raise NotImplementedError

	def _command_pp(self, command='pp', expression=''):
		"""Print the expression via pretty printing. This is actually how p works, too."""
		if expression == '':
			return
		raise NotImplementedError

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
