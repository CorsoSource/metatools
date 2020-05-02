


class Commands(object):

	__slots__ = ('_command', 
				 '_pending_commands', 
				 '_map_o_commands',)

	_UPDATE_CHECK_DELAY = 0.01


	def __init__(self, *args, **kwargs):

		super(Commands, self).__init__(*args, **kwargs)

		self._map_o_commands = dict(
			(attribute[9:], getattr(self, attribute))
			for attribute in dir(self)
			if attribute.startswith('_command_'))
		
		self.command = ''
		self._pending_commands = []


	# Interaction
	
	def await_comand(self):
	
		while not self._pending_commands:
			sleep(self._UPDATE_CHECK_DELAY)
		
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
				 )

	def __init__(self, *args, **kwargs):
		super(PdbCommands, self).__init__(*args, **kwargs)
		self._alias_commands = {}


	def command(self, command):
		"""Interpret commands like PDB: '!' means execute, 
		otherwise it's a command word followed by optional arguments.
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

