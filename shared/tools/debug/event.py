

class EventDispatch(object):

	__slots__ = ('_map_for_dispatch', 
				 'monitoring',
				)

	def __init__(self, thread=None, *args, **kwargs):
		
		super(EventDispatch, self).__init__(*args, **kwargs)

		self.monitoring = False

		self._map_for_dispatch = dict(
			(attribute[10:], getattr(self, attribute))
			for attribute in dir(self)
			if attribute.startswith('_dispatch_'))


	# User overridable functions
	
	def on_call(self, frame):
		pass
	def on_line(self, frame):
		pass
	def on_return(self, frame, return_value):
		pass
	def on_exception(self, frame, (exception, value, traceback)):
		pass

	# Dispatch

	def dispatch(self, frame, event, arg):
		if self.monitoring:
			self._map_for_dispatch.get(event, self._nop)(frame, arg)
			return self.dispatch
		else:
			return # none

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
