

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
		"""



	def strip_angle_brackets(internal_name):
		if internal_name.startswith('<') and internal_name.endswith('>'):
			return internal_name[1:-1]
		else:
			return internal_name


	def _code_event(component, event_name):
		event_name = strip_angle_brackets(event_name)

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


	def _code_module(filename):
		filename = strip_angle_brackets(filename)

		if filename.startswith('module:'):
			filename = filename.partition(':')[2]
			
		try:
			return sys.modules[filename].code
		except:
			return None