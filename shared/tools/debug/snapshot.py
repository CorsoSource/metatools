"""
	Snapshots keep track of the tracer as it executes.

	Use the snapshot's context_buffer to look back on the history of the trace.
	Note that it may not be a perfect image! Execution frames update while the
	  stack frame executes, and any objects that fails the deepcopy (or if it's
	  not actively deepcopying for speed) may mutate as execution progresses.
	  Moreover, Java objects are not subject to deepcopy, meaning that their
	  references are merely passed along and saved. And so be forewarned.
"""

from copy import deepcopy

from shared.tools.debug.frame import iter_frames


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


class Snapshot(object):

	__slots__ = ('_event', '_arg', '_frame', '_code',
				 '_filename', '_line', '_caller', '_depth',
				 '_locals_key', '_locals_dup', '_locals_ref', '_locals_err',
				 '_cloned',
				 '__weakref__',)

	_repr_markers = {'line': '|',  'call': '+',   'return': '/',   'exception': 'X',
								 'c_call': '+', 'c_return': '/', 'c_exception': 'X',
					 'init': '#'}

	def __init__(self, frame, event, arg, clone=True):


		self._event    = event
		self._arg      = arg
		self._frame    = frame

		self._code     = frame.f_code
		self._filename = frame.f_code.co_filename
		self._line     = frame.f_lineno
		self._caller   = frame.f_code.co_name
		self._depth    = len(list(iter_frames(frame)))

		local_key = set()
		local_dup = {}
		local_ref = {}
		local_err = {}

		if clone:
			# attempt to make a deepcopy of each item,
			# note that Java and complex objects will fail deepcopy
			#   and instead will be saved by reference only
			for key,value in frame.f_locals.items():
				try:
					local_dup[key] = deepcopy(value)
				except Exception, err:
					local_ref[key] = value
					local_err[key] = err
		self._cloned = clone

		self._locals_key = local_key
		self._locals_dup = local_dup
		self._locals_ref = local_ref
		self._locals_err = local_err


	@property
	def event(self):
		return self._event
	@property
	def arg(self):
		return self._arg
	@property
	def frame(self):
		return self._frame
	@property
	def filename(self):
		return self._filename
	@property
	def line(self):
		return self._line
	@property
	def caller(self):
		return self._caller
	@property
	def depth(self):
		return self._depth
	@property
	def code(self):
		return self._code

	@property
	def cloned(self):
		return self._cloned
	@property
	def locals(self):
		return dict(self._locals_ref.items() + self._locals_dup.items())
	@property
	def locals_uncloned(self):
		return self._locals_err.keys()

	@property
	def globals(self):
		raise NotImplementedError("Frame globals are not snapshot during execution.")
	@property
	def globals_uncloned(self):
		raise NotImplementedError("Frame globals are not snapshot during execution.")

	def back_context(self, arg=None, clone=False):
		if self._frame.f_back:
			return Snapshot(self._frame.f_back, 'backtrace', arg, clone)
		else:
			return None

	def __getitem__(self, key):
		"""Get var from frame. Note that this has various guarantees depending on setup.

		If the frame locals were cloned, then it will first try to return the deepcopy
		  version (to avoid mutation as frame evolves), then it'll fall back to a reference.
		If references were not cloned, the frame is directly referenced. Note that f_locals
		  will mutate as the frame executes, so this is the least reliable way to see
		  what is currently happening.
		"""
		if self._cloned:
			val = self._locals_dup.get(key)
			if val is None:
				return self._locals_ref.get(key)
			else:
				return val
		else:
			return self._frame.f_locals[key]


	def as_dict(self):
		props = 'event arg frame filename line caller local'.split()
		return dict((prop,getattr(self,prop)) for prop in props)


	def __repr__(self):
		tree_marker = [' ']*4
		tree_marker[len(tree_marker) % (self.depth)] = self._repr_markers.get(self.event, '*')
		return '<Snapshot [%s%2d:%6s] %4d of %s at %s>' % (''.join(tree_marker),
			self.depth, self.event.capitalize()[:6], self.line, self.filename, self.caller)
