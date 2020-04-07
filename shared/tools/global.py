"""
	ExtraGlobal - Hold computed objects in memory from anywhere in the JVM.

	This is a manual form of memoization.

	NOTE: This is *specifically* not thread safe!
		  Use this to hold immutable objects that could be shared between threads.
		  Or use it (carefully!) to continue partial calculations.
"""

from shared.tools.thread import async
from time import time, sleep
from weakref import WeakKeyDictionary
from functools import wraps
from java.lang import Thread


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'

__all__ = ['ExtraGlobal']

class CacheEntry(object):

	__slots__ = ('_obj', 
		         'label', 'scope', 'lifespan', 
		         '_last_used', 
		         '_callback')

	def __init__(self, obj, label, scope, lifespan, callback=None):
		self._obj = obj
		self.label = label
		self.scope = scope
		self.lifespan = lifespan

		self._last_used = time()
		self._callback = callback

	@property
	def obj(self):
		self._last_used = time()
		return self._obj

	@property
	def last_used(self):
		return self._last_used

	@property 
	def expired(self):
		return time() - self.last_used > self.lifespan

	def refresh(self):
		if self._callback:
			ret_val = self._callback()
			if ret_val is not None:
				self._obj = ret_val
				self._last_used = time()
	
	@property
	def key(self):
		return self.gen_key(self.label, self.scope)

	@staticmethod
	def gen_key(label, scope):
		return (scope, label)

	def __repr__(self):
		if self.scope is not None:
			return '<CacheEntry "%s" of "%s">' % (self.label, self.scope)
		else:
			return '<CacheEntry "%s" (global)>' % (self.label,)


class MetaGlobalCache(type):
	"""Force the GlobalCache to be a singleton object.
	This enforces that any (effectively all) global state is accessible.

	This also ensures there is a cleanup scrip to scrub out the cache, as needed.

	Externally, all references are (label:scope), interally they are (scope, label)
	Objects are all saved with their last checked time
	"""

	DEFAULT_LIFESPAN = 60 # seconds
	CHECK_PERIOD = 10 # seconds

	_cleanup_monitor = None

	_cache = {}


	def clear_cache(cls):
		cls._cache = {}
		cls._cleanup_monitor = None


	def stash(cls, obj, label=None, scope=None, lifespan=None, callback=None):
		assert label is not None, "Objects stashed need to have a label associated with them."

		if lifespan is None:
			lifespan = cls.DEFAULT_LIFESPAN

		cache_entry = CacheEntry(obj, label, scope, lifespan, callback)
		cls._cache[cache_entry.key] = cache_entry
		
		cls.spawn_cache_monitor()
		return cache_entry.key


	def access(cls, label, scope=None):
		try:
			cache_entry = cls._cache[CacheEntry.gen_key(label, scope)]
		except KeyError:
			scope = None
			cache_entry = cls._cache[CacheEntry.gen_key(label, scope)]
				
		cls.spawn_cache_monitor()
		return cache_entry.obj


	def trash(cls, label=None, scope=None):
		del cls._cache[CacheEntry.gen_key(label, scope)]
		cls.spawn_cache_monitor()


	@classmethod
	def resolve(cls, reference):
		if isinstance(reference, slice):
			if reference.stop and not isinstance(reference.stop, (str, unicode, int, long)):
				scope = reference.stop.__class__.__name__
			else:
				scope = reference.stop
			label = reference.start
			lifespan = reference.step or cls.DEFAULT_LIFESPAN
		elif isinstance(reference, (tuple,list)):
			assert 1 <= len(reference) <= 3, "References must either be slices or iterables between 1 and 3 elements"

			label = reference[0]
			
			if len(reference) >= 2:
				scope = reference[1]
			else:
				scope = None

			if len(reference) == 3:
				lifespan = reference[2]
			else:
				lifespan = cls.DEFAULT_LIFESPAN
		else:
			label = reference
			scope = None
			lifespan = cls.DEFAULT_LIFESPAN

		return label, scope, lifespan


	def __getitem__(cls, reference):
		label, scope, _ = cls.resolve(reference)
		return cls.access(label, scope)


	def __setitem__(cls, reference, obj):
		label, scope, lifespan = cls.resolve(reference)
		return cls.stash(obj, label, scope, lifespan)


	def __delitem__(cls, reference):
		label, scope, _ = cls.resolve(reference)
		cls.trash(label, scope)


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
				for key in cls._cache:
					entry = cls._cache[key]

					if entry.expired:
						entry.refresh()
						if entry.expired:
							cls.trash(entry.label, entry.scope)

				sleep(cls.CHECK_PERIOD)

		cls._cleanup_monitor = monitor()


	def keys(cls):
		return iter(sorted(cls._cache.keys()))

	def values(cls):
		raise NotImplementedError("Cache should not be iterated across values.")

	def __iter__(cls):
		return cls.keys()

	def __repr__(cls):
		return '<%s with %d items>' % (cls.__name__, len(cls._cache))


class GlobalCache(object):
	__metaclass__ = MetaGlobalCache

	def __new__(cls):
		raise NotImplementedError("%s does not support instantiation." % cls.__name__) 
	
	def __init__(cls):
		raise NotImplementedError("%s does not support instantiation." % cls.__name__) 

	def __setattr__(cls, key, value):
		raise AttributeError("%s attributes are not mutable. Use methods to manipulate them." % cls.__name__) 

# I like this name more
ExtraGlobal = GlobalCache


#>>> GlobalCache._cache
#\{}
#>>> GlobalCache['asdf'] = 234
#>>> GlobalCache._cache
#{(None, 'asdf'): <__main__.CacheEntry object at 0x4>}
#>>> GlobalCache._cleanup_monitor
#Thread[Thread-16,5,main]
#>>> GlobalCache._cache
#{}
#>>> GlobalCache['asdf'] = 234
#>>> GlobalCache._cache
#{(None, 'asdf'): <__main__.CacheEntry object at 0x5>}
#>>> del GlobalCache['asdf']
#>>> GlobalCache._cache
#{}
#>>> GlobalCache['asdf'] = 234
#>>> GlobalCache._cache
#{(None, 'asdf'): <__main__.CacheEntry object at 0x6>}
#>>> GlobalCache.trash('asdf')
#>>> GlobalCache._cache
#{}
#>>> GlobalCache['asdf':'playground':5] = 234
#>>> GlobalCache._cache
#{('playground', 'asdf'): <__main__.CacheEntry object at 0x7>}
#>>> GlobalCache._cache
#{('playground', 'asdf'): <__main__.CacheEntry object at 0x7>}
#>>> GlobalCache._cache
#{('playground', 'asdf'): <__main__.CacheEntry object at 0x7>}
#>>> GlobalCache._cache
#{}
