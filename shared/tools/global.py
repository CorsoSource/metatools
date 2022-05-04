"""
	ExtraGlobal - Hold computed objects in memory from anywhere in the JVM.

	This is a manual form of memoization.

	When used, ExtraGlobal will generate two threads:
	 - A cache thread that holds references even if the source threads or functions
		 go out of scope
	 - A monitoring thread that culls the cache periodically, checking what items
		 need to be removed from expiration, or replaced/refreshed from a callback

	The ExtraGlobal class can not be instantiated - it is forced to be a singleton
	  interface by the metaclass that defines it. All methods to interact with the
	  cache is via MetaExtraGlobal's configuration.

	Note that this has the side effect of not only being a singleton,
	  but it also effectively can't be subclassed! Don't try to: this is
	  not something that should have special contexts or clever instances.
	  Treat it as a dumb key-value store, where the key can be as complicated
	  as a two element tuple. (Anything more sophisticated lies madness.)

	To summarize:
			   ExtraGlobal - the cache interface
		   MetaExtraGlobal - the interface definition for the cache
	  ExtraMetaExtraGlobal - the enforcer that MetaExtraGlobal defines the cache
							 only ever once at a time in the JVM

	NOTE: This is *specifically* not thread smart!
		  It's thread safe, but the practice of using global state is _not_!

		  Use this to hold immutable objects that could be shared between threads.
		  Or use it (carefully!) to continue partial calculations.
"""

from shared.tools.thread import async, findThreads, getFromThreadScope
from shared.tools.timing import EveryFixedDelay
from shared.tools.meta import MetaSingleton

from time import time, sleep
from functools import wraps
from java.lang import Thread


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'

#__all__ = ['ExtraGlobal']
__all__ = [
	'eg_stash',
	'eg_access',
	'eg_trash',
	'eg_extend',
	'eg_get',
	'eg_setdefault',
	'eg_keys',
	'eg_iterkeys',
	'eg_update',
	]

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


	def extend(self, additional_time=0.0):
		"""Extend the effective lifespan of the cache entry by additional_time seconds."""
		self._last_time += additional_time


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

	NOTE: Once imported, the cache will launch a thread to keep itself in scope!
	  This is to make sure that there is only ever one instance of this and derivative
	  classes anywhere on the JVM.

	  Unlike the other threads, this GLOBAL_REFERENCE thread does NOT die when the cache empties.

	  Keeping GLOBAL_REFERENCE alive prevents the class from getting regenerated as an optimization.
	  If GLOBAL_REFERENCE is set to NONE, though, it will clear itself on its next scan.

	For a little bit of clarity, the metaclasses are being used a bit like this:
	  ExtraMetaExtraGlobal - ensure JVM-level singleton definition
	  MetaExtraGlobal      - ensure interface to dict is strictly method-based
	  ExtraGlobal          - ensure instantiation is impossible and define a class for the methods
	"""
	HOLDING_THREAD_NAME = 'ExtraGlobal-Cache'
	_HOLDING_THREAD = None

	GLOBAL_REFERENCE = None

	# Period to check if the holding thread has been replaced or should be shut down.
	META_RELEVANCE_CHECK_PERIOD = 1 # second

	def __new__(cls, clsname, bases, attrs):
		if cls.GLOBAL_REFERENCE:
			# Ensure there's a holding thread to keep cache references alive (from the GC)
			if not cls.GLOBAL_REFERENCE._HOLDING_THREAD:
				cls.spawn_holding_thread(cls, cls.GLOBAL_REFERENCE)
			return cls.GLOBAL_REFERENCE

		cache_threads = findThreads(cls.HOLDING_THREAD_NAME)

		assert len(cache_threads) <= 1, "The ExtraGlobal-Cache thread has been spun up more than once! Only one should be alive: %r" % cache_threads

		# If no holding threads are found and GLOBAL_REFERENCE is not initialized, generate MetaExtraGlobal
		if not cache_threads:
			cls.GLOBAL_REFERENCE = super(ExtraMetaExtraGlobal, cls).__new__(cls, clsname, bases, attrs)
			cls.spawn_holding_thread(cls, cls.GLOBAL_REFERENCE)
		else:
			system.util.getLogger('ExtraGlobal').debug('Already initialized in %r as %r' % (cache_threads[0], cls.GLOBAL_REFERENCE))
			cls.GLOBAL_REFERENCE = getFromThreadScope(cache_threads[0], 'MetaExtraGlobal')

		return cls.GLOBAL_REFERENCE

	@staticmethod
	def spawn_holding_thread(meg_cls, MEG_Reference):
		"""Spin up (if needed) a thread to hold the cache.
		Checks if it should clear itself META_RELEVANCE_CHECK_PERIOD

		The holding thread will run in perpetuity, but will die if:
		 - the class' _HOLDING_THREAD is cleared
		 - the class' _HOLDING_THREAD no longer references the monitoring script
		 - the GLOBAL_REFERENCE has changed to another cache instance. Somehow.
		"""
		if meg_cls._HOLDING_THREAD:
			if meg_cls._HOLDING_THREAD.getState() != Thread.State.TERMINATED:
				return
			else:
				meg_cls._HOLDING_THREAD = None

		system.util.getLogger('ExtraGlobal').debug('Spinning up holding thread')

		# Spin up the thread after a very short delay to allow final assignments to establish
		@async(0.05, meg_cls.HOLDING_THREAD_NAME)
		def holding_closure(MetaExtraGlobal=MEG_Reference):
			"""Spin up a thread to ensure that MetaExtraGlobal is always in scope,
			and only ever in scope exactly one time. If it goes out of scope
			"""
			from time import sleep
			from java.lang import Thread

			# Initialize to be self-consistent and self-referential
			if MetaExtraGlobal.GLOBAL_REFERENCE is None:
				MetaExtraGlobal.GLOBAL_REFERENCE = MetaExtraGlobal

			thisThread = Thread.currentThread()

			# This GLOBAL_REFERENCE thread will run forever until orphaned or killed directly.
			while True:
				# Wait for META_RELEVANCE_CHECK_PERIOD, but check occasionally if the monitor
				# should be replaced. (Once scan starts, thread won't die until it's done.)
				sleep(MetaExtraGlobal.META_RELEVANCE_CHECK_PERIOD)

				# die if disconnected reference or unneeded
				if MetaExtraGlobal.GLOBAL_REFERENCE is None:
					system.util.getLogger('ExtraGlobal').debug('Closing holding thread: GLOBAL_REFERENCE detected as None')
					return
				# check if the holding thread's been orphaned
				if MetaExtraGlobal._HOLDING_THREAD is not thisThread:
					# if there's somehow _another_ thread...
					if MetaExtraGlobal._HOLDING_THREAD is None:
						if MetaExtraGlobal and MetaExtraGlobal._cache:
							MetaExtraGlobal._cache = {}
					else:
						# check to see if we need to merge keys
						if MetaExtraGlobal and MetaExtraGlobal._cache:
							# try to merge in any missing keys, then clear out
							The_New_Meta = getFromThreadScope(MetaExtraGlobal._HOLDING_THREAD, 'MetaExtraGlobal')
							for key,value in MetaExtraGlobal._cache.items():
								if not key in The_New_Meta:
									The_New_Meta[key] = value
							MetaExtraGlobal._cache = {}
					system.util.getLogger('ExtraGlobal').debug('Closing holding thread: HOLDING THREAD detected as changed')
					return

				# ... and this is "looking both ways down a one-way street"
				if MetaExtraGlobal.GLOBAL_REFERENCE is not MetaExtraGlobal:
					# check to see if we need to merge keys
					if MetaExtraGlobal and MetaExtraGlobal._cache:
						# try to merge in any missing keys, then clear out
						The_New_Meta = MetaExtraGlobal.GLOBAL_REFERENCE
						for key,value in MetaExtraGlobal._cache.items():
							if not key in The_New_Meta:
								The_New_Meta[key] = value
						MetaExtraGlobal._cache = {}
					system.util.getLogger('ExtraGlobal').debug('Closing holding thread: GLOBAL_REFERENCE detected as changed')
					return

		meg_cls._HOLDING_THREAD = holding_closure()

		meg_cls.GLOBAL_REFERENCE = MEG_Reference


class MetaExtraGlobal(type):
	"""Force the ExtraGlobal to be a singleton object.
	This enforces that any (effectively all) global state is accessible.

	NOTE: The Jython dict is based on a thread safe map class in Java. Thus _cache may be
	  safely _accessed_ by anyone. Mutating entries will also be safe, but it also follows
	  all the caveats of a global variable. This is why this is called *Extra*Global, as
	  opposed to "Just a Bit Global, Like a Python Module Variable or Just Poor Planning."

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

	# Inherited from the metaclass, copied here for reference
	RELEVANCE_CHECK_PERIOD = 1 # second

	CLEANUP_THREAD_NAME = 'ExtraGlobal-Monitor'
	_CLEANUP_MONITOR = None

	_cache = {}

	_scoped_labels = {}

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
		cls._scoped_labels.clear()
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
		cls._scope_track(cache_entry.label, cache_entry.scope)

		system.util.getLogger('ExtraGlobal').trace('Stashed %r from %r' % (cache_entry.key, Thread.currentThread()))

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
		cls._scope_untrack(label, scope)
		del cls._cache[CacheEntry.gen_key(label, scope)]
		system.util.getLogger('ExtraGlobal').trace('Trashed (scope:%r, label:%r) from %r' % (scope, label, Thread.currentThread()))
		cls.spawn_cache_monitor()


	# Cache entry helpers

	def extend(cls, label, scope=None, additional_time=0.0):
		"""Extend the cache timeout by additional_time seconds."""
		cache_entry = cls._cache[CacheEntry.gen_key(label, scope)]
		cache_entry.extend(additional_time)


	# Scope tracking for easier filtering

	def _scope_track(cls, label, scope):
		"""Add the reference label to the scope, creating the scope if needed."""
		try:
			cls._scoped_labels[scope].add(label)
		except KeyError:
			cls._scoped_labels[scope] = set([label])

	def _scope_untrack(cls, label, scope):
		"""Ensure a label is not in a scope, also purge the scope if it is empty."""
		if not scope in cls._scoped_labels:
			return
		elif len(cls._scoped_labels[scope]) <= 1:
			del cls._scoped_labels[scope]
		elif label in cls._scoped_labels[scope]:
			cls._scoped_labels[scope].remove(label)


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


	def verify_holding_thread(cls):
		"""Make sure there's something to keep the references alive in case the source(s) go away."""
		meta_cls = cls.__metaclass__
		extra_meta_cls = meta_cls.__metaclass__
		# Is the holding thread missing?
		if extra_meta_cls._HOLDING_THREAD is None:
			extra_meta_cls.spawn_holding_thread(meta_cls, meta_cls)
		# Is the holding thread dead?
		elif extra_meta_cls._HOLDING_THREAD.getState() == Thread.State.TERMINATED:
			extra_meta_cls._HOLDING_THREAD = None
			extra_meta_cls.spawn_holding_thread(meta_cls, meta_cls)


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
		cls.verify_holding_thread()

		if cls._CLEANUP_MONITOR:
			if cls._CLEANUP_MONITOR.getState() != Thread.State.TERMINATED:
				return
			else:
				cls._CLEANUP_MONITOR = None

		# Spin up the thread after a very short delay to allow final assignments to establish
		@async(0.05, cls.CLEANUP_THREAD_NAME)
		def monitor(cls=cls):

			# Initialize to be self-consistent and self-referential
			thisThread = Thread.currentThread()

			while True:
				# Wait for CHECK_PERIOD, but check occasionally if the monitor
				# should be replaced. (Once scan starts, thread won't die until it's done.)
				for iterNum,lastStepTime in EveryFixedDelay(cls.CHECK_PERIOD, cls.RELEVANCE_CHECK_PERIOD):
					# die if disconnected reference or unneeded
					if cls._CLEANUP_MONITOR is None:
						system.util.getLogger('ExtraGlobal').debug('Closing monitor thread %r: CLEANUP MONITOR detected as None' % thisThread)
						return
					# die if another monitor has somehow been spun up instead
					elif cls._CLEANUP_MONITOR != thisThread:
						system.util.getLogger('ExtraGlobal').debug('Closing monitor thread %r: CLEANUP MONITOR detected as Changed' % thisThread)
						return
					# die gracefully if not needed
					elif not cls._cache:
						cls._CLEANUP_MONITOR = None
						system.util.getLogger('ExtraGlobal').debug('Closing monitor thread %r: Cache is empty. Gracefully closing cache.' % thisThread)
						return

				# Scan the cache, removing entries as needed.
				for key in frozenset(cls._cache):
					try:
						entry = cls._cache[key]
					except KeyError:
						continue # the key has been deleted mid-scan

					# Check if the entry is expired
					# (remember, the entry will refresh itself if it can, referencing the new entry if needed)
					try:
						if entry.expired:
							cls.trash(entry.label, entry.scope)
					except:
						del cls._cache[key]
						cls._scope_untrack(entry.label, entry.scope)

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


	def keys(cls, scope=None):
		"""Currently available keys in the cache. (Like a dict, but sorted)"""
		if scope:
			try:
				return sorted(cls._scoped_labels[scope])
			except KeyError:
				return []
		else:
			return sorted(cls._cache.keys())

	def iterkeys(cls, scope=None):
		"""Currently available keys in the cache. (Like a dict)"""
		return iter(cls.keys(scope))

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


class ExtraGlobal(MetaSingleton):
	"""This is a singleton implementation of the cache. It exists without instances."""
	__metaclass__ = ExtraMetaExtraGlobal.GLOBAL_REFERENCE


##==========================================================================
## Global access, in case class access is undesired
##==========================================================================
## Disabled by default
#
#def MEG_FACTORY():
#
#	class CacheAccess(MetaSingleton):
#		"""This is a singleton implementation of the cache. It exists without instances."""
#		__metaclass__ = ExtraMetaExtraGlobal.GLOBAL_REFERENCE
#
#	return CacheAccess
#
#
#def eg_stash(obj, label=None, scope=None, lifespan=None, callback=None):
#	"""Add an object to the cache.  Label will be how it's retrieved, with an optional scope
#	  in case multiple labels are the same in differing contexts.
#
#	Object in cache for the label in that scope will be replaced if it already exists!
#
#	A lifetime can be given if the object should be cleared out of the cache
#	  at a time different from the default (DEFAULT_LIFESPAN).
#
#	A callback can be provided that will be called when the object expires or when refresh is called.
#	  The callback must take no arguments (either setting the cache value itself or is a closure.)
#	"""
#	shared.tools.global.ExtraGlobal.stash(obj, label, scope, lifespan, callback)
#
#def eg_access(label, scope=None):
#	"""Retrieve an object from the cache, given the label and (optionally) scope.
#
#	Defaults to "global" scope (contextless - just the label as the key)
#	"""
#	shared.tools.global.ExtraGlobal.access(obj, label, scope)
#
#def eg_trash(label=None, scope=None):
#	"""Remove an item from the cache directly."""
#	shared.tools.global.ExtraGlobal.trash(label, scope)
#
#def eg_extend(label, scope=None, additional_time=0.0):
#	"""Extend the cache timeout by additional_time seconds."""
#	shared.tools.global.ExtraGlobal.extend(label, scope, additional_time)
#
#def eg_get(label, scope=None, default=None):
#	"""Return a value without a KeyError if the reference is missing. (Like a dict)"""
#	return shared.tools.global.ExtraGlobal.get(label, scope, default)
#
#def eg_setdefault(label, scope=None, default=None, lifespan=None, callback=None):
#	"""Return a value without a KeyError, adding default if key was missing. (Like a dict)"""
#	return shared.tools.global.ExtraGlobal.setdefault(label, scope, default, lifespan, callback)
#
#def eg_keys(scope=None):
#	"""Currently available keys in the cache. (Like a dict, but sorted)"""
#	return shared.tools.global.ExtraGlobal.keys(scope)
#
#def eg_iterkeys(scope=None):
#	"""Currently available keys in the cache. (Like a dict)"""
#	return shared.tools.global.ExtraGlobal.iterkeys(scope)
#
#def eg_update(new_values=None, **kwargs):
#	"""Updates the cache with new_values, updating existing cache entries.
#
#	Acceptable values are:
#		new_values may be a dict, where keys are references and values are replacements.
#		new_values may be a list of references to force the entries to update themselves.
#		  where references will be decoded like dict[...] references.
#		keyword arguments are all interpreted as labels and objects, with scope=None.
#
#	Note that the cache entries maintain their settings, and new entries get defaults.
#	Also note that this does _not_ fail to global scope - references must be explicit
#	"""
#	shared.tools.global.ExtraGlobal.update(new_values, **kwargs)