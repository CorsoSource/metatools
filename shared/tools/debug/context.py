from copy import deepcopy


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

