from weakref import WeakValueDictionary
from collections import defaultdict

from shared.tools.debug.frame import normalize_filename


class Breakpoint(object):
	"""Note that breakpoints are explicit, while a trap is much more commonly
	  evaluated. Traps are rooting about for a situation while the debugger
	  effectively brings the situation to the breakpoint to be verified.
	"""
	__slots__ = ('_id', '_filename', '_line_number', '_function_name',
				 'temporary', 'condition', 'hits', 
				 'enabled', 'ignored',
				 'note',
				 '__weakref__',
				 )

	_id_counter = 0

	_instances = {}
	_break_locations = {(None, None): set()}


	def __init__(self, filename=None, location=None, 
				 temporary=False, condition=None, note=''):

		self._filename = normalize_filename(filename)
		try:
			line_number = int(location)
			self._line_number = line_number
			self._function_name = ''
		except ValueError:
			self._line_number = None
			self._function_name = location

		# A purely contextless breakpoint should not be abided for long.
		# (since it'll stop. on. every. single. line.)
		if not temporary and not any((filename, location, condition)):
			temporary = True
			if not note:
				note = 'Contextless breaking ONCE at NEXT opportunity'

		self.note = note

		self.temporary = temporary # this is a bit jank if more than one debugger scans it
		self.condition = condition

		self.hits = 0

		# use Tracer/PDB instance as key for number of hits
		self.enabled = defaultdict(bool) # no one is interested by default
		self.ignored = defaultdict(int)

		self._add()


	# Properties that should not change once set
	@property
	def filename(self):
		return self._filename
	
	@property
	def line_number(self):
		return self._line_number

	@property
	def function_name(self):
		return self._function_name
	
	
	@property
	def id(self):
		return self._id


	@classmethod
	def next_id(cls):
		cls._id_counter += 1
		return cls._id_counter

	@property
	def location(self):
		return (self.filename, self.function_name or self.line_number)


	@classmethod
	def resolve_breakpoints(cls, breakpoint_ids):
		# coerce to iterable, if needed
		if not isinstance(breakpoint_ids, (list, tuple, set)):
			breakpoint_ids = [breakpoint_ids] 

		breakpoints = []
		for breakpoint in breakpoint_ids:
			if isinstance(breakpoint, Breakpoint):
				breakpoints.append(breakpoint)
			elif isinstance(breakpoint, (long, int)):
				breakpoints.append(cls._instances[breakpoint])
			elif isinstance(breakpoint, (str, unicode)):
				breakpoints.extend(cls._break_locations[breakpoint])
		return breakpoints


	def _add(self):
		"""Add the breakpoint to the class' tracking. If set leave it."""
		try:
			if self._id:
				return
		except AttributeError:
			if self.location in self._break_locations:
				self._break_locations[self.location].add(self)
			else:
				self._break_locations[self.location] = set([self])
			
			self._id = self.next_id()
			self._instances[self.id] = self 

	def _remove(self):
		self.enabled.clear()
		del self._instances[self.id]
		self._break_locations[self.location].remove(self)


	def trip(self, frame):
		"""Determine if the breakpoint should trip given the frame context."""
	
		# Breakpoint set by line
		if not self.function_name:
			# always trip on contextless breakpoints
			if not any((self.line_number, self.filename)):
				return True
			else:
				return self.line_number == frame.f_lineno

		# Fail if the function name's wrong
		if self.function_name != frame.f_code.co_name:
			return False

		# Correct frame and correct function
		# Check if this is the first line of the function (call)
		try:
			return frame.f_lineno == self._function_first_line(frame)
		except KeyError:
			return False # in case of lookup in previous scope error, such as for a lambda?


	def _function_first_line(self, frame_scope):
		"""Grab the function's first line number from the frame scope."""
		try:
			function = frame_scope.f_back.f_locals[self.function_name]
		except KeyError:
			function = frame_scope.f_back.f_globals[self.function_name]
		return function.func_code.co_firstlineno


	@staticmethod
	def frame_location_by_line(frame):
		return (normalize_filename(frame.f_code.co_filename), frame.f_lineno)

	@staticmethod
	def frame_location_by_function(frame):
		return (normalize_filename(frame.f_code.co_filename), frame.f_code.co_name)


	def enable(self, interested_party):
		"""Enable the breakpoint for the interested_party"""
		self.enabled[interested_party] = True
		
	def disable(self, interested_party):
		"""Disable the breakpoint for the interested_party (this is the default state)"""
		self.enabled[interested_party] = False

	def ignore(self, interested_party, num_passes=0):
		"""Ignore this breakpoint for num_passes times for the interested_party"""
		self.ignored[interested_party] = num_passes


	@classmethod
	def relevant_breakpoints(cls, frame, interested_party=None):
		relevant = set()

		possible = set( cls._break_locations[(None,None)]
					  | cls._break_locations.get(cls.frame_location_by_line(frame), set())
			          | cls._break_locations.get(cls.frame_location_by_function(frame), set()) )

		# Check candidate locations
		for breakpoint in possible:

			# Check if it's enabled for them (default no)
			if not breakpoint.enabled[interested_party]:
				continue

			# Check if the breakpoints trips for this context (always true for (None,None))
			if not breakpoint.trip(frame):
				continue

			# Count each pass over the breakpoint while it's enabled
			#   Note that this is not filtered - it counts all executions
			breakpoint.hits += 1

			if not breakpoint.condition:

				# If interested_party chose to ignore the breakpoint,
				#   decrement the counter and pass on...
				if breakpoint.ignored[interested_party] > 0:
					breakpoint.ignored[interested_party] -= 1
					continue
				# ... otherwise pass it in
				else:
					relevant.add(breakpoint)
					if breakpoint.temporary:
						breakpoint._remove()
					continue

			else:
				# Attempt to evaluate the condition
				try:
					# Sure, eval is evil... but we're in debug so all bets are off
					# Note that this is like PDB: it expects a string or compiled code here.
					#   A function will need to be either in scope or compiled beforehand!
					result = eval(breakpoint.condition, 
								  frame.f_globals,
								  frame.f_locals)
					if result:
						# If interested_party chose to ignore the breakpoint,
						#   decrement the counter and pass on...
						if breakpoint.ignored[interested_party] > 0:
							breakpoint.ignored[interested_party] -= 1
							continue
						# ... otherwise pass it in
						else:
							relevant.add(breakpoint)
							if breakpoint.temporary:
								breakpoint._remove()
							continue							
				# If the condition fails to eval, then break just to be safe
				#   but don't modify the ignore settings, also to be safe. (PDB compliance)
				except:
					relevant.add(breakpoint)
					continue

		return relevant


	def __str__(self):
		meta = []
		if self.temporary:
			meta.append('temporary')
		if self.condition:
			meta.append('conditional')

		meta = (' %r' % meta) if meta else ''

		func = (' for %s' % self.function_name) if self.function_name else ''

		return '<Breakpoint [%d] %sin %s at %s%s>' % (self.id, func, self.filename, self.line_number, meta)


	def __repr__(self):
		return self.__str__() # for now... should add conditional 


def set_breakpoint(note=''):
	import sys
	frame = sys._getframe(1)
	Breakpoint(frame.f_code.co_filename, frame.f_lineno, note=note)