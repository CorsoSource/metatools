
from functools import wraps


def cached(function):
	@wraps(function)
	def check_cache_first(cls, *args):
		if not args in cls._cache:
			cls._cache[args] = function(cls, *args)
		return cls._cache[args]



class CodeCache(object):
	"""Similar to the linecache module in purpose, but makes sense of the Ignition environment.
	
	It caches the results for faster lookup.

	For example, the `frame.f_code.co_filename` may be `<event:actionPerformed>`.
	  This isn't enough information, so we need to backtrace to get the event object.
	  Though the project may have many of these, the `event` object nearest in the 
	  call stack is certainly the one of interest. It's `event.source` is what fired
	  it, and if we go up the `.parent` tree enough, we'll find the interaction
	  controller that has the adapters that has the source code in them.

	  That's a bit involved, hence the caching.
	"""

	# cache keys are based on what the _code_* functions need.
	_cache = {}


	def _dispatch_location(location, frame):
		"""Resolve and make sense of the location given. 

		It may be "module:shared.tools.debug.codecache" or perhaps 
		  a vague "event:actionPerformed". This function will make sense of this
		  in the Ignition environment, backtracing as needed.

		Note that this caches after resolving objects. This is because name references
		  may be ambiguous or change as the stack mutates.
		"""

		if ':' in location:
			location = strip_angle_brackets(location)
			script_type, _, identifier = location.partition(':')

			if script_type == 'module:':
				return self._code_module(identifier)

			elif script_type == 'event':
				component = self.find_root_object('event', frame).source
				return self._code_event(component, identifier)

			elif script_type == 'tagevent':
				tag_path = self.find_root_object('tagPath', frame)
				return self._code_tag_event()

		else:



	def strip_angle_brackets(internal_name):
		if internal_name.startswith('<') and internal_name.endswith('>'):
			return internal_name[1:-1]
		else:
			return internal_name


	@cached
	def _code_file(cls, filepath):
		with open(filepath, 'r') as f:
			return f.read()


	@cached
	def _code_event(cls, component, event_name):

		ic = None
		ic_comp = component
		while not ic and ic_comp:
			try:
				ic = getattr(ic_comp, 'getInteractionController')()
			except:
				ic_comp = ic_comp.parent

		assert ic_comp, "Interaction controller not found - backtrace failed."
		
		for adapter in ic.getAllAdaptersForTarget(component):
			if adapter.getMethodDescriptor().getName() == event_name:
				return adapter.getJythonCode()
		else:
			return None


	@cached
	def _code_module(cls, filename):
		
		module = sys.modules[filename]

		if isinstance(module)

		filepath = getattr(module, '__file__', None)
		if filepath:
			with open(filepath, 'r') as f:
				return f.read()

		code = getattr(module, 'code', None)
		if code:
			return code
		
		return None


	@cached
	def _code_tag_event(cls, tag, event_name):
		if isinstance(tag, (str, unicode)):
			tag = system.tag.getTag(tag)
		return tag.getEventScripts().get(event_name)


	@staticmethod
	def _iter_frames(frame):
		while frame:
			yield frame
			frame = frame.f_back

	@staticmethod
	def _iter_frame_root(frame):
		stack = list(_iter_frames(frame))
		for frame in reversed(stack):
			yield frame


	@staticmethod
	def find_object(obj_name, frame):
		"""Grab an item from the Python stack by its name, starting with the given frame."""
		# if no shortcut is provided, start at the furthest point
		for frame in _iter_frames(frame):
			if obj_name in frame.f_locals:
				return frame.f_locals[obj_name]
		return None

	@staticmethod
	def find_root_object(obj_name, frame):
		"""Grab an item from the Python stack by its name, starting with the given frame."""
		# if no shortcut is provided, start at the furthest point
		for frame in _iter_frame_root(frame):
			if obj_name in frame.f_locals:
				return frame.f_locals[obj_name]
		return None
