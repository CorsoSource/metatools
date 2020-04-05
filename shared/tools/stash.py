"""
	StashCache - Hold computed objects in memory.

	NOTE: This is *specifically* not thread safe!
		  Use this to hold immutable objects that could be shared between threads.
		  Or use it (carefully!) to continue partial calculations. 
"""

from shared.tools.thread import async
from time import time, sleep
from weakref import WeakKeyDictionary

from java.lang import Thread


class MetaStashCache(type):
	"""Force the StashCache to be a singleton object.
	This enforces that any (effectively all) global state is accessible.

	This also ensures there is a cleanup scrip to scrub out the cache, as needed.

	Externally, all references are (key:scope), interally they are (scope, key)
	Objects are all saved with their last checked time
	"""

	def _update(cls, scope, key, obj, lifespan):
		cls._cache[(scope, key)] = (obj, lifespan, time())
		cls.spawn_cache_monitor()


	def stash(cls, obj, key=None, scope=None, lifespan=None):
		assert key is not None, "Objects stashed need to have a key associated with them."

		if key is None:
			key = hash(obj)
		elif not isinstance(key, (str,unicode,int,long)):
			key = hash(key)

		if lifespan is None:
			lifespan = cls.TIMEOUT

		cls._update(scope, key, obj, lifespan)

		return key


	def access(cls, key, scope=None):
		try:
			obj, lifespan, _ = cls._cache[(scope,key)]
		except KeyError:
			scope = None
			obj, lifespan, _ = cls._cache[(scope,key)]
				
		cls._update(scope, key, obj, lifespan)

		return obj


	def trash(cls, key=None, scope=None):
		del cls._cache[(scope,key)]


	def _resolve(cls, reference):
		if isinstance(reference, slice):
			if reference.stop and not isinstance(reference.stop, (str, unicode, int, long)):
				scope = reference.stop.__class__.__name__
			else:
				scope = reference.stop
			key = reference.start
			lifespan = reference.step or cls.TIMEOUT
		elif isinstance(reference, (tuple,list)):
			assert 1 <= len(reference) <= 3, "References must either be slices or iterables between 1 and 3 elements"

			key = reference[0]
			
			if len(reference) >= 2:
				scope = reference[1]
			else:
				scope = None

			if len(reference) == 3:
				lifespan = reference[2]
			else:
				lifespan = cls.TIMEOUT
		else:
			key = reference
			scope = None
			lifespan = cls.TIMEOUT

		return key, scope, lifespan


	def __getitem__(cls, reference):
		key, scope, _ = cls._resolve(reference)
		return cls.access(key, scope)


	def __setitem__(cls, reference, obj):
		key, scope, lifespan = cls._resolve(reference)
		return cls.stash(obj, key, scope, lifespan)


	def __delitem__(cls, reference):
		key, scope, _ = cls._resolve(reference)
		cls.trash(key, scope)


	def clear_cache(cls):
		cls._cache = {}
		cls._cleanup_monitor = None


	def spawn_cache_monitor(cls):

		if cls._cleanup_monitor:
			if cls._cleanup_monitor.getState() != Thread.State.TERMINATED:
				return
			else:
				cls._cleanup_monitor = None

		@async(0.001)
		def monitor(cls=cls):

			while True:
				# die if disconnected reference or unneeded
				if not (cls._cleanup_monitor and cls._cache):
					return
				# die if another monitor has somehow been spun up instead
				if cls._cleanup_monitor != Thread.currentThread():
					return

				now = time()
				for scope, key in cls._cache:
					_, lifespan, last = cls._cache[(scope,key)]

					if now - last > lifespan:
						cls.trash(key, scope)

				sleep(cls.CHECK_PERIOD)

		cls._cleanup_monitor = monitor()


class StashCache(object):
	__metaclass__ = MetaStashCache

	TIMEOUT = 60 # seconds
	CHECK_PERIOD = 10 # seconds

	_cleanup_monitor = None

	_cache = {}

	def __new__(cls):
		raise NotImplementedError("%s does not support instantiation." % cls.__name__) 
	
	def __init__(cls):
		raise NotImplementedError("%s does not support instantiation." % cls.__name__) 

	def __setattr__(cls, key, value):
		raise AttributeError("%s attributes are not mutable. Use methods to manipulate them." % cls.__name__) 
