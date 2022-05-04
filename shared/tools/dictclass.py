class DictPosingAsClass(object):
	"""
	Convert a dictionary to an object that's class-like.

	Enter expected fields in __slots__.

	Set _skip_undefined to True to ignore dict fields that
	  are not in __slots__.

	Entries in _coerce_fields should be keys that are in __slots__
	  and values that are functions (or types).

	>>> dpac = DPAC(**some_dict)
	"""
	__slots__ = tuple()

	# True == exclusive to __slots__
	# False == no error if extra args beyond what's in __slots__, just skipped
	_skip_undefined=False

	_coerce_fields = {}

	@classmethod
	def _nop(cls, x):
		return x
	def _coerce(self, key, value):
		return self._coerce_fields.get(key, self._nop)(value)

	def __init__(self, **kwargs):
		if self._skip_undefined:
			for key,value in kwargs.items():
				try:
					self.__setitem__(key, value)
				except AttributeError:
					pass
		else:
			for key,value in kwargs.items():
				self.__setitem__(key, value)

	def keys(self):
		ks = []
		for key in self.__slots__:
			try:
				_ = getattr(self, key)
				ks.append(key)
			except AttributeError:
				pass
		return ks

	def values(self):
		vs = []
		for key in self.__slots__:
			try:
				vs.append(getattr(self, key))
			except AttributeError:
				pass
		return vs

	def __contains__(self, key):
		try:
			_ = getattr(self, key)
			return True
		except AttributeError:
			return False

	def __setitem__(self, key, val):
		setattr(self, key, self._coerce(key,val))

	def __getitem__(self, key):
		if not key in self.__slots__:
			raise AttributeError('"%s" is not a key in __slots__' % key)
		try:
			return getattr(self, key)
		except AttributeError:
			return None

	def _asdict(self):
		d = {}
		for key in self.__slots__:
			try:
				v = getattr(self, key)
				d[key] = v._asdict() if isinstance(v, DictPosingAsClass) else v
			except AttributeError:
				pass
		return d

	def __repr__(self):
		return repr(self._asdict())


class DPAC_JSON(DictPosingAsClass):
	"""An example of extending it for easier serializing"""
	@classmethod
	def _coerceToString(cls, thing):
		if isinstance(thing, DictPosingAsClass):
			return thing._asdict()
		if isinstance(thing, tuple):
			return list(thing)
		if isinstance(thing, (arrow.Arrow, datetime)):
			return thing.isoformat()
		return repr(thing)

	def __repr__(self):
		return rapidjson.dumps(self._asdict(), indent=2, default=self._coerceToString)





