"""
	ExtraGlobal - Hold computed objects in memory from anywhere in the JVM.

	This is a manual form of memoization.

	The ExtraGlobal class can not be instantiated - it is forced to be a singleton
	  interface by the metaclass that defines it. All methods to interact with the
	  cache is via MetaGlobalCache's configuration. 

	Note that this has the side effect of not only being a singleton, 
	  but it also effectively can't be subclassed! Don't try to: this is
	  not something that should have special contexts or clever instances.
	  Treat it as a dumb key-value store, where the key can be as complicated
	  as a two element tuple. (Anything more sophisticated lies madness.) 

	NOTE: This is *specifically* not thread safe!
		  Use this to hold immutable objects that could be shared between threads.
		  Or use it (carefully!) to continue partial calculations.
"""

from shared.tools.thread import async
from shared.tools.timing import EveryFixedDelay

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
	"""Hold the relevant details for an object in the cache.
	Assumes that there is a monitoring process that will clear the item
	  at its leisure after at least lifespan seconds past the last_used time.
	"""
	__slots__ = ('_obj', 
		         'label', 'scope', 'lifespan', 
		         '_last_used', 
		         '_callback')

	def __init__(self, obj, label, scope, lifespan, callback=None):
		"""Set up the cache object. A callback may be used to generate a new value."""
		self._obj = obj
		self.label = label
		self.scope = scope
		self.lifespan = lifespan

		self._last_used = time()
		self._callback = callback

	@property
	def obj(self):
		"""Set as a property to prevent getting easily written to."""
		if self.expired:
			return None
		else:
			self._last_used = time()
			return self._obj

	@property
	def last_used(self):
		"""Set as a property to prevent getting easily written to."""
		return self._last_used

	@property 
	def expired(self):
		"""Returns true when the entry is past when it should be cleaned up.
		If a garbage collector catches the referenced object, mark it dead
		"""
		return (time() - self.last_used > self.lifespan) or (self._obj is None)

	def refresh(self):
		"""Run the callback, if any was provided.
		If the callback function does not return a value, assume the function
		  updated the cache on its own (or not - perhaps it's a cleanup...)
		Otherwise save the value and reset the clock. 
		"""
		if self._callback:
			ret_val = self._callback()
			if ret_val is not None:
				self._obj = ret_val
				self._last_used = time()
	
	@property
	def key(self):
		"""Act like a dict."""
		return self.gen_key(self.label, self.scope)

	@staticmethod
	def gen_key(label, scope):
		"""Reference this method to generate the key schema for the cache."""
		return (scope, label)


	def __repr__(self):
		if self.scope is not None:
			return '<CacheEntry "%s" of "%s">' % (self.label, self.scope)
		else:
			return '<CacheEntry "%s" (global)>' % (self.label,)



class MetaGlobalCache(type):
	"""Force the GlobalCache to be a singleton object.
	This enforces that any (effectively all) global state is accessible.
	
	By default, a scope of None is "global". If a scope is provided and the key fails,
	  the key will be tried with a scope of None as well, as a fallback.

	This also ensures there is a cleanup scrip to scrub out the cache, as needed.

	Externally, all references are (label:scope), interally they are (scope, label)
	Objects are all saved with their last checked time and will be scrubbed when the expire
	  (assuming they do not autorenew themselves.)
	"""

	# Default period a cache entry should live in the cache before garbage collection
	DEFAULT_LIFESPAN = 60 # seconds

	# Monitor (garbage collecing) thread configuraiton
	# Period to check the cache for expired entries
	CHECK_PERIOD = 10 # seconds
	# Period to check if the monitor has been replaced or should be shut down.
	RELEVANCE_CHECK_PERIOD = 1 # second

	_cleanup_monitor = None

	_cache = {}

	def clear_cache(cls):
		"""Hard reset the cache."""
		cls._cache = {}
		cls._cleanup_monitor = None

	
	# Primary access methods

	def stash(cls, obj, label=None, scope=None, lifespan=None, callback=None):
		"""Add an object to the cache.  Label will be how it's retrieved, with an optional scope
		  in case multiple labels are the same in differing contexts.

		Object in cache for the label in that scope will be replaced if it already exists!

		A lifetime can be given if the object should be cleared out of the cache
		  at a time different from the default (DEFAULT_LIFESPAN).

		A callback can be provided that will be called when the object expires or when refresh is called.
		  The callback must take no arguments (either setting the cache value itself or is a closure.) 
		"""
		assert label is not None, "Objects stashed need to have a label associated with them."

		if lifespan is None:
			lifespan = cls.DEFAULT_LIFESPAN

		cache_entry = CacheEntry(obj, label, scope, lifespan, callback)
		cls._cache[cache_entry.key] = cache_entry
		
		cls.spawn_cache_monitor()
		return cache_entry.key


	def access(cls, label, scope=None):
		"""Retrieve an object from the cache, given the label and (optionally) scope.

		Defaults to "global" scope (contextless - just the label as the key)
		"""
		try:
			cache_entry = cls._cache[CacheEntry.gen_key(label, scope)]
		except KeyError:
			scope = None
			cache_entry = cls._cache[CacheEntry.gen_key(label, scope)]
				
		cls.spawn_cache_monitor()
		return cache_entry.obj


	def trash(cls, label=None, scope=None):
		"""Remove an item from the cache directly."""
		del cls._cache[CacheEntry.gen_key(label, scope)]
		cls.spawn_cache_monitor()


	# Convenience (dict-like) methods

	def __getitem__(cls, reference):
		"""Retrieve an item from the cache. 
		Acts like a dictionary lookup, but can reference a scope as well.

		Reference as either [label], [label:scope], or [label, scope] 
		"""
		label, scope, _ = cls.resolve(reference)
		return cls.access(label, scope)


	def __setitem__(cls, reference, obj):
		"""Add an item to the cache.
		Acts like a dictionary reference, but both a scope and a lifespan can be provided.

		Reference as either [label], [label:scope], [label:scope:lifespan], [label::lifespan],
		  or [label, scope], [label, scope, lifespan], [label, , lifespan] 
		"""

		label, scope, lifespan = cls.resolve(reference)
		return cls.stash(obj, label, scope, lifespan)


	def __delitem__(cls, reference):
		"""Remove an item from the cache.
		Acts like a dictionary, but can reference a scope as well.

		Reference as either [label], [label:scope], or [label, scope] 
		"""
		label, scope, _ = cls.resolve(reference)
		cls.trash(label, scope)


	@classmethod
	def resolve(cls, reference):
		"""Given a reference (the contents between the ExtraGlobal[...]), 
		resolve what the user wanted.

		The reference may be one of the following types:
		 - slice:    where the format is [label:scope:lifespan]
		 - iterable: where the format is [label, scope, lifespan]
		 - just a label (default to "global" scope and default lifespan)
		
		Note that the lifetime only matters when using __setitem__.
		"""
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


	def spawn_cache_monitor(cls):
		"""Spin up (if needed) a thread to monitor the cache. Checks all cache entries
		  every CHECK_PERIOD seconds.

		If there's already a thread (that's not dead) then don't bother.
		If the thread that was watching is dead for some reason, replace it.

		The monitoring script will run in perpetuity, but will die if:
		 - the class' _cleanup_monitor is cleared
		 - the class' _cleanup_monitor no longer references the monitoring script
		 - the cache is empty
		
		Once started, the monitor will scan all objects in the cache to determine
		  if they should be culled. If their time is up, an attempt will be made
		  to refresh it. If the refresh brought the object back, then it will be skipped.
		  Otherwise the cache entry will be trashed.
		"""
		if cls._cleanup_monitor:
			if cls._cleanup_monitor.getState() != Thread.State.TERMINATED:
				return
			else:
				cls._cleanup_monitor = None

		@async(0.001)
		def monitor(cls=cls):

			while True:
				# Wait for CHECK_PERIOD, but check occasionally if the monitor
				# should be replaced. (Once scan starts, thread won't die until it's done.)
				for iterNum,lastStepTime in EveryFixedDelay(cls.CHECK_PERIOD, cls.RELEVANCE_CHECK_PERIOD):
					# die if disconnected reference or unneeded
					if not (cls._cleanup_monitor and cls._cache):
						return
					# die if another monitor has somehow been spun up instead
					if cls._cleanup_monitor != Thread.currentThread():
						return

				# Scan the cache, removing entries as needed.
				for key in frozenset(cls._cache):
					try:
						entry = cls._cache[key]
					except KeyError:
						continue # the key has been deleted mid-scan

					if entry.expired:
						# in case of failure, cull move on
						try:
							entry.refresh()
						except:
							pass
						# check if the refresh updated the cache entry
						if entry.expired:
							cls.trash(entry.label, entry.scope)

		cls._cleanup_monitor = monitor()


	def keys(cls):
		"""Currently available keys in the cache. (Like a dict)"""
		return iter(sorted(cls._cache.keys()))

	def values(cls):
		"""All the values in the cache. Note: this shouldn't ever be used."""
		raise NotImplementedError("Cache should not be iterated across values.")

	def __iter__(cls):
		"""Maintaining the illusion of a dict..."""
		return cls.keys()

	def __repr__(cls):
		return '<%s with %d items>' % (cls.__name__, len(cls._cache))


class GlobalCache(object):
	"""This is a singleton implementation of the cache. It exists without instances."""
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
