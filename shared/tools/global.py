"""
	ExtraGlobal - Hold computed objects in memory from anywhere in the JVM.

	This is a manual form of memoization.

	The ExtraGlobal class can not be instantiated - it is forced to be a singleton
	  interface by the metaclass that defines it. All methods to interact with the
	  cache is via MetaExtraGlobal's configuration. 

	Note that this has the side effect of not only being a singleton, 
	  but it also effectively can't be subclassed! Don't try to: this is
	  not something that should have special contexts or clever instances.
	  Treat it as a dumb key-value store, where the key can be as complicated
	  as a two element tuple. (Anything more sophisticated lies madness.) 

	NOTE: This is *specifically* not thread safe!
		  Use this to hold immutable objects that could be shared between threads.
		  Or use it (carefully!) to continue partial calculations.
"""

from shared.tools.thread import async, findThreads, getFromThreadScope
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
		         '_last_time', 'callback')

	def __init__(self, obj, label, scope, lifespan, callback=None):
		"""Set up the cache object. A callback may be given to generate a new value on expiration.
		
		Lifespan determines when death should occur.
		 - If a callback is given, wait for the lifespan then refresh
		 - Otherwise lifespan is the timeout for the cache entry cooling off
		"""
		self._obj = obj
		self.label = label
		self.scope = scope
		self.lifespan = lifespan

		self._last_time = time()
		self.callback = callback
		
	def update(self, obj=None):
		"""Change the cache entry to what's in obj. Resets the last_time for expiration/refresh.
		If nothing is provided, triggers the entry to update itself, if possible.
		"""
		if obj is None:
			if self.callback:
				self.refresh()
		else:
			self._obj = obj
			self._last_time = time()

	@property
	def obj(self):
		"""Set as a property to prevent getting easily written to."""
		if self.expired:
			return None
		else:
			if self.callback is None:
				self._last_time = time()
			return self._obj

	@property
	def last_time(self):
		"""Set as a property to prevent getting easily written to."""
		return self._last_time
		
	@property
	def time_remaining(self):
		return max(0, self.lifespan - (time() - self._last_time))

	@property 
	def expired(self):
		"""Returns true when the entry is past when it should be cleaned up.
		If a garbage collector catches the referenced object, mark it dead
		"""
		# Don't cache null pointers...
		if self._obj is None:
			return True
		
		# If time expired...
		if (time() - self._last_time > self.lifespan):
			# ... check if it can be refreshed
			if self.callback:
				
				self.refresh()
				
				# Either the refresh worked, or it didn't. 
				# If the refresh callback replaced the entry, then it'll return None
				#   and the new entry will be fine and this one will just get GC'd by JVM,
				#   and we want to signal to the monitor the new one is ok.
				# If the refresh wrote back directly, then this entry will still work.
				# Either way, ExtraGlobal has the correct entry to check
				#   so for simplicity this is tightly coupled here.
				gc_entry = ExtraGlobal._cache[self.key]

				# if this CacheEntry *has* been replaced,
				#   then copy the object to be consistent until the GC catches self
				if self is not gc_entry:
					self._obj = gc_entry._obj
					
				return gc_entry.expired
			
			# otherwise there's nothing to fix it, so mark this entry for destruction		
			else:
				return True
		
		# Otherwise no death condition was detected.
		return False


	def refresh(self):
		"""Run the callback, if any was provided.
		If the callback function does not return a value, assume the function
		  updated the cache on its own (or not - perhaps it's a cleanup...)
		Otherwise save the value and reset the clock. 
		"""
		if self.callback:
			# in case of failure, mark to cull and move on
			try:
				ret_val = self.callback()
			except:
				self._obj = None
				return
				
			if ret_val is not None:
				self._obj = ret_val
				self._last_time = time()
	
	@property
	def key(self):
		"""Act like a dict."""
		return self.gen_key(self.label, self.scope)

	@staticmethod
	def gen_key(label, scope):
		"""Reference this method to generate the key schema for the cache."""
		return (scope, label)

	
	def __eq__(self, other):
		"""Don't reset timer when merely checked (like in testing)"""
		return self._obj == other
		
	def __ne__(self, other):
		"""Don't reset timer when merely checked (like in testing)"""
		return self._obj != other

	def __repr__(self):
		if self.scope is not None:
			return '<CacheEntry [% 9.3fs] "%s" of "%s">'  % (time() - self._last_time, self.label, self.scope,)
		else:
			return '<CacheEntry [% 9.3fs] "%s" (global)>' % (time() - self._last_time, self.label,)


class ExtraMetaExtraGlobal(type):
	"""Force the MetaExtraGlobal definition to be a JVM-level global singleton object.

	The goal here is to reach across all Python threads and make sure that there can
	  be only one cache.

	For a little bit of clarity, the metaclasses are being used a bit like this:
	  ExtraMetaExtraGlobal - ensure JVM-level singleton definition
	  MetaExtraGlobal      - ensure interface to dict is strictly method-based
	  ExtraGlobal          - ensure instantiation is impossible and define a class for the methods
	"""
	HOLDING_THREAD_NAME = 'ExtraGlobal-Cache'
	
	GLOBAL_REFERENCE = None

	def __new__(cls, clsname, bases, attrs):
		if cls.GLOBAL_REFERENCE:
			return cls.GLOBAL_REFERENCE

		cache_threads = findThreads(cls.HOLDING_THREAD_NAME)

		assert len(cache_threads) <= 1, "The ExtraGlobal-Cache thread has been spun up more than once! Only one should be alive: %r" % cache_threads

		if not cache_threads:
			system.util.getLogger('ExtraGlobal').debug('Spinning up holding thread')

			MetaExtraGlobal = super(ExtraMetaExtraGlobal, cls).__new__(cls, clsname, bases, attrs)
	
			@async(name=cls.HOLDING_THREAD_NAME)
			def holding_closure(MetaExtraGlobal=MetaExtraGlobal):
				from time import sleep
				
				while True:
					sleep(0.01)
		
			cache_thread = holding_closure()
			
			cls.GLOBAL_REFERENCE = getFromThreadScope(cache_thread, 'MetaExtraGlobal')
	
		else:
			system.util.getLogger('ExtraGlobal').debug('Already initialized: %r' % cls.GLOBAL_REFERENCE)

			cls.GLOBAL_REFERENCE = getFromThreadScope(cache_threads[0], 'MetaExtraGlobal')
	
		return cls.GLOBAL_REFERENCE
#	
#	@classmethod
#	def purge_holding_thread(cls):
#		for thread in findThreads(cls.HOLDING_THREAD_NAME):
#			thread.interrupt()	
#			

class MetaExtraGlobal(type):
	"""Force the ExtraGlobal to be a singleton object.
	This enforces that any (effectively all) global state is accessible.
	
	By default, a scope of None is "global". If a scope is provided and the key fails,
	  the key will be tried with a scope of None as well, as a fallback.

	This also ensures there is a cleanup scrip to scrub out the cache, as needed.

	Externally, all references are (label:scope), interally they are (scope, label)
	Objects are all saved with their last checked time and will be scrubbed when the expire
	  (assuming they do not autorenew themselves.)
	"""
	__metaclass__ = ExtraMetaExtraGlobal

	# Interlock for once-and-only-once setup
	_initialized = False

	# Default period a cache entry should live in the cache before garbage collection
	DEFAULT_LIFESPAN = 60 # seconds

	# Monitor (garbage collecing) thread configuraiton
	# Period to check the cache for expired entries
	CHECK_PERIOD = 10 # seconds
	# Period to check if the monitor has been replaced or should be shut down.
	RELEVANCE_CHECK_PERIOD = 1 # second

	_CLEANUP_MONITOR = None

	_cache = {}
	
	def __new__(cls, clsname, bases, attrs):
		"""Run when ExtraGlobal is created. Set to run once and only once."""
		if not cls._initialized:
			newclass = super(MetaExtraGlobal, cls).__new__(cls, clsname, bases, attrs)
			cls._initialized = newclass
			return newclass
		else:
			return cls._initialized

	def clear(cls):
		"""Hard reset the cache."""
		cls._cache.clear()
		cls._CLEANUP_MONITOR = None


	def __setattr__(cls, key, value):
		"""Further control what can be changed. This will essentially trap the (meta)class into a singleton framework."""
		# allow global constants to change
		if key.upper() == key:
			setattr(type(cls), key, value)
		elif not cls._initialized:
			setattr(cls, key, value)
		else:
			raise AttributeError("Only global (all uppercase) attributes on %s can be changed" % repr(cls))

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
		 - the class' _CLEANUP_MONITOR is cleared
		 - the class' _CLEANUP_MONITOR no longer references the monitoring script
		 - the cache is empty
		
		Once started, the monitor will scan all objects in the cache to determine
		  if they should be culled. If their time is up, an attempt will be made
		  to refresh it. If the refresh brought the object back, then it will be skipped.
		  Otherwise the cache entry will be trashed.
		"""
		if cls._CLEANUP_MONITOR:
			if cls._CLEANUP_MONITOR.getState() != Thread.State.TERMINATED:
				return
			else:
				cls._CLEANUP_MONITOR = None

		@async(0.001, 'ExtraGlobal-Monitor')
		def monitor(cls=cls):

			while True:
				# Wait for CHECK_PERIOD, but check occasionally if the monitor
				# should be replaced. (Once scan starts, thread won't die until it's done.)
				for iterNum,lastStepTime in EveryFixedDelay(cls.CHECK_PERIOD, cls.RELEVANCE_CHECK_PERIOD):
					# die if disconnected reference or unneeded
					if not (cls._CLEANUP_MONITOR and cls._cache):
						return
					# die if another monitor has somehow been spun up instead
					if cls._CLEANUP_MONITOR != Thread.currentThread():
						return

				# Scan the cache, removing entries as needed.
				for key in frozenset(cls._cache):
					try:
						entry = cls._cache[key]
					except KeyError:
						continue # the key has been deleted mid-scan
					
					# Check if the entry is expired
					# (remember, the entry will refresh itself if it can, referencing the new entry if needed)
					if entry.expired:
						cls.trash(entry.label, entry.scope)

		cls._CLEANUP_MONITOR = monitor()

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

	# Additional Dict convenience methods
	
	def get(cls, label, scope=None, default=None):
		"""Return a value without a KeyError if the reference is missing. (Like a dict)"""
		key = CacheEntry.gen_key(label, scope)
		if key in cls._cache:
			return cls.access(label, scope)
		else:
			return default

	def setdefault(cls, label, scope=None, default=None, lifespan=None, callback=None):
		"""Return a value without a KeyError, adding default if key was missing. (Like a dict)"""
		key = CacheEntry.gen_key(label, scope)
		if key in cls._cache:
			return cls.access(label, scope)
		else:
			cls.stash(default, label, scope, lifespan, callback)
			return default


	def keys(cls):
		"""Currently available keys in the cache. (Like a dict, but sorted)"""
		return sorted(cls._cache.keys())

	def iterkeys(cls):
		"""Currently available keys in the cache. (Like a dict)"""
		return iter(cls.keys())

	def __len__(cls):
		return len(cls._cache)

	def values(cls):
		"""All the values in the cache. Note: this shouldn't ever be used."""
		raise NotImplementedError("Cache should not be iterated across values.")

	def items(cls):
		raise NotImplementedError("Cache should not be iterated across values.")
		
	def update(cls, new_values=None, **kwargs):
		"""Updates the cache with new_values, updating existing cache entries.
		
		Acceptable values are:
			new_values may be a dict, where keys are references and values are replacements.
			new_values may be a list of references to force the entries to update themselves.
			  where references will be decoded like dict[...] references.
			keyword arguments are all interpreted as labels and objects, with scope=None.
			
		Note that the cache entries maintain their settings, and new entries get defaults.
		Also note that this does _not_ fail to global scope - references must be explicit
		"""
		if new_values is None:
			pass
		
		elif isinstance(new_values, dict):
			for reference, obj in new_values.items():
				label, scope, lifespan = cls.resolve(reference)
				
				# keyword arguments override given dict, so skip and leave for kwargs handling
				if scope is None and label in kwargs:
					continue
					
				key = CacheEntry.gen_key(label, scope)
				if key in cls._cache:
					cls._cache[key].update(obj)
				else:
					cls.stash(obj, label, scope, lifespan)
			
		# assume an iterable of references
		else:
			for reference in new_values:
				label, scope, _ = cls.resolve(reference)
				
				key = CacheEntry.gen_key(label, scope)
				cls._cache[key].update()
		
		for local, obj in kwargs.items():
			key = CacheEntry.gen_key(label, scope=None)
			if key in cls._cache:
				cls._cache[key].update(obj)
			else:
				cls.stash(obj, local)
		

	def __contains__(cls, reference):
		if reference in cls._cache:
			return True
		label, scope, _ = cls.resolve(reference)

		if CacheEntry.gen_key(label, scope) in cls._cache:
			return True
		
		return False  


	def __iter__(cls):
		"""Maintaining the illusion of a dict..."""
		return cls.keys()

	def __repr__(cls):
		return '<%s with %d items>' % (cls.__name__, len(cls._cache))


class ExtraGlobal(object):
	"""This is a singleton implementation of the cache. It exists without instances."""
	__metaclass__ = ExtraMetaExtraGlobal.GLOBAL_REFERENCE

	def __new__(cls):
		raise NotImplementedError("%s does not support instantiation." % cls.__name__) 
	
	def __init__(cls):
		raise NotImplementedError("%s does not support instantiation." % cls.__name__) 

	def __setattr__(cls, key, value):
		raise AttributeError("%s attributes are not mutable. Use methods to manipulate them." % cls.__name__) 


#from shared.tools.pretty import p,pdir
#from time import sleep
#
#from shared.tools.global import ExtraGlobal, MetaExtraGlobal
#	
#ExtraGlobal.DEFAULT_LIFESPAN = 5
#ExtraGlobal.CHECK_PERIOD = 0.1
#ExtraGlobal.RELEVANCE_CHECK_PERIOD = 0.05
#
#assert ExtraGlobal._cache == {}
#
#print "\nTesting basic timeout - wait 5s"
#ExtraGlobal['asdf'] = 234
#p(ExtraGlobal._cache)
## {(None, 'asdf'): <__main__.CacheEntry object at 0x4>}
#
#print ExtraGlobal._CLEANUP_MONITOR
##~ Thread[Thread-16,5,main]
#
#sleep(6)
#assert ExtraGlobal._cache == {}
#
#print "\nTesting del"
#ExtraGlobal['asdf'] = 234
#del ExtraGlobal['asdf']
#assert ExtraGlobal._cache == {}
#
#print "\nTesting trash"
#ExtraGlobal['asdf'] = 234
#ExtraGlobal.trash('asdf')
#assert ExtraGlobal._cache == {}
#
#print "\nTesting partial timeout - 3 checks in 3 seconds"
#ExtraGlobal['asdf':'playground':3] = 234
#p(ExtraGlobal._cache)
#assert ExtraGlobal._cache[('playground', 'asdf')] == 234
#sleep(1)
#assert ExtraGlobal._cache[('playground', 'asdf')] == 234
#sleep(2.5)
#assert ExtraGlobal._cache == {}
#
#try:
#	# raises RuntimeError
#	class BARGLE(object):
#		__metaclass__ = MetaExtraGlobal
#	raise AssertionError("Failed to catch singleton definition case.")
#except RuntimeError:
#	pass	