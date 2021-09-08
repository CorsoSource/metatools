"""
	Helper functions to make dealing with threads a bit less painful.
"""

from functools import wraps, partial
from time import sleep
from datetime import datetime, timedelta
import re
from heapq import heappush, heappop
import sys

from java.lang import Thread, ThreadGroup, NullPointerException
from java.nio.channels import ClosedByInterruptException
from jarray import array, zeros
from org.python.core import ThreadState

from shared.tools.meta import getReflectedField, MetaSingleton
from shared.tools.timing import EveryFixedDelay

from shared.tools.logging import Logger
from java.lang import Exception as JavaException


__copyright__ = """Copyright (C) 2021 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


__all__ = ['async', 'findThreads', 'getThreadObject']


def total_seconds(some_timedelta):
	return some_timedelta.seconds + some_timedelta.microseconds


class MetaAsyncWatchdog(type):

	SCRAM_THREAD_NAME = 'Async-SCRAM-Monitor'
	SCRAM_CHECK_RATE = 0.1 # seconds
	_SCRAM_MONITOR = None

	_thread_expirations = {}

	def watch(cls, thread_handle, max_allowed_runtime=None, kill_switch=None):
		
		if max_allowed_runtime is None:
			expected_dead_by = None
		else:
			expected_dead_by = datetime.now() + timedelta(seconds=max_allowed_runtime)
		
		if kill_switch is None:
			kill_switch = lambda : False
		
		cls._thread_expirations[thread_handle] = (expected_dead_by, kill_switch)

		cls.spawn_watchdog_monitor()


	def spawn_watchdog_monitor(cls):

		if cls._SCRAM_MONITOR:
			if cls._SCRAM_MONITOR.getState() != Thread.State.TERMINATED:
				return
			else:
				cls._SCRAM_MONITOR = None

		@async(0.001, name=cls.SCRAM_THREAD_NAME)
		def monitor(cls=cls):

			# Once the threads are all gone, exit and die gracefully
			while cls._thread_expirations:
				
				for thread_handle in frozenset(cls._thread_expirations):
					
					try:
						next_expiration, kill_switch = cls._thread_expirations[thread_handle]
					except KeyError:
						continue # already culled, possibly because it finished so fast
					
					thread_state = thread_handle.getState()
					
					# If the thread is already done, then remove it
					if thread_state == Thread.State.TERMINATED:
						try:
							del cls._thread_expirations[thread_handle]
						except KeyError: # already dead or removed? Ok!
							pass
													
					# if the thread isn't dead but should be, kill it
					elif next_expiration and next_expiration < datetime.now():
						thread_handle.interrupt()
						try:
							del cls._thread_expirations[thread_handle]
						except KeyError: # already dead or removed? Ok!
							pass

					else:
						# Check if the kill_switch is set (and wrap in a try/except in case it's malformed)
						try:
							assert kill_switch() is True
							thread_handle.interrupt()
							try:
								del cls._thread_expirations[thread_handle]
							except KeyError: # already dead or removed? Ok!
								pass
						except:
							# otherwise wait a little bit and see if that changes
							# push back onto the dictionary and check again on next loop
							pass
				
				# pause the loop long enough for states to change...			
				sleep(cls.SCRAM_CHECK_RATE)

			cls._SCRAM_MONITOR = None

		cls._SCRAM_MONITOR = monitor()	



class AsyncWatchdog(MetaSingleton):
	__metaclass__ = MetaAsyncWatchdog



def async(startDelaySeconds=None, name=None, maxAllowedRuntime=None, killSwitch=None, ensureOnlyOne=False):
	"""Decorate a function with this to make it run in another thread asynchronously!
	If defined with a value, it will wait that many seconds before firing.
	If a name is provided the thread will be named. Handy for the gateway thread status page.
	
	Note that threads have their own scope, and any output is redirected to their own
	  sys.stderr writer. It turns out this is simply always the JVM's console, though.

	>>> # For a function to immediately run in another thread, simply decorated it:
	>>> from shared.tools.logging import BaseLogger
	>>> @async
	... def foo(x,y=5):
	...     print x,y
	...     BaseLogger().log('x=%(x)r y=%(y)r') # complex delaying calc & shows new stdout
	>>> tFoo = foo(12)
	>>> tFoo.getState()
	RUNNABLE
	>>> tFoo.getState()
	TERMINATED
	>>> 
	>>> # For a 1.5 second delay before executing, you can provide an argument:
	>>> from time import sleep
	>>> @async(1.5)
	... def bar(a,b,c=5):
	...     print a,b,c
	>>> tBar = bar(1,2)
	>>> sleep(0.2); tBar.getState()
	TIMED_WAITING
	>>> sleep(1.5); tBar.getState()
	TERMINATED
	"""
	# Check if the first argument is a function. If it's just decorating, do the trivial case
	if getattr(startDelaySeconds, '__call__', None):		
		# Decorator didn't have a param, so this is actually a function
		function = startDelaySeconds
		
		try:
			@wraps(function)
			def asyncWrapper(*args, **kwargs):
				# Create the closure to carry the scope into another thread
				def async_closure(function, args=args, kwargs=kwargs):
					try:
						_ = function(*args,**kwargs)
					except (KeyboardInterrupt, IOError, ClosedByInterruptException):
						pass
					except (Exception, JavaException), error:
						Logger(prefix='(Async)', target_context=error).error(repr(error))
						return

				# Wrap the function and delay values to prevent early GC of function and delay
				closure = partial(async_closure, function)
				
				# Async calls should return the thread handle. 
				# They will _not_ return whatever the function returned. That gets dumped to _.
				return system.util.invokeAsynchronous(closure)
			return asyncWrapper

		# If the @async decorator was called with empty parenthesis, then the Python engine
		# will assume the results are _themselves_ a decorator. This leads to an AttributeError.
		# Simply call it correctly here.
		except AttributeError:
			assert all(arg is None for arg in (startDelaySeconds, name, maxAllowedRuntime)), 'The @async decorator was likely called wrong.\nSimply do not use () with no params.'
			return async(0)

	# ... otherwise apply the configuration provided
	else:
		if isinstance(startDelaySeconds, (str, unicode)):
			name = startDelaySeconds
			startDelaySeconds = None
			
		if startDelaySeconds is None:
			startDelaySeconds = 0.0

		# Convert to check param... Clamps to millisecond multiples
		delaySeconds = int(startDelaySeconds*1000.0)/1000.0
			
		# Since we passed in a value, we'll need to return an actual decorator function
		def asyncDecoWrapper(function):
			
			@wraps(function)
			def asyncWrapper(*args, **kwargs):
		
				# Create the closure to carry the scope into another thread
				def async_closure(function, delaySeconds, args=args, kwargs=kwargs):
					#print 'delaying %0.3f' % delaySeconds
					sleep(delaySeconds)
					try:
						_ = function(*args,**kwargs)
					except (KeyboardInterrupt, IOError, ClosedByInterruptException):
						pass
					except (Exception, JavaException), error:
						Logger(prefix='(Async)', target_context=error).error(repr(error))
					
				# Wrap the function and delay values to prevent early GC of function and delay
				closure = partial(async_closure, function, delaySeconds)
				
				# Async calls should return the thread handle. 
				# They will _not_ return whatever the function returned. That gets dumped to _.
				if name and ensureOnlyOne and findThreads(name):
					return # do nothing

				thread_handle = system.util.invokeAsynchronous(closure)
				if name:
					thread_handle.setName(name)
				
				if maxAllowedRuntime or killSwitch:
					AsyncWatchdog.watch(thread_handle, maxAllowedRuntime, killSwitch)
				
				return thread_handle
			return asyncWrapper
		return asyncDecoWrapper


def findThreads(thread_name_pattern='.*', search_group=None, recursive=False, sandbagging_percent=110):
	"""Find a thread in reachable scope that matches the pattern provided.

	Pattern is a regular expression, so an explicit name will work.

	Returns a list of threads. Names are _not_ guaranteed to be unique!
	  Thus, even a direct name reference can't be used directly. Only the `getId()` value
	  is unique.

	By default, it only looks in the local thread group.
	If recursive is selected, it will also look at any lower thread_groups.
	If both are default, it scans all threads available.
	"""
	
	# Guess scope and search all groups if need. 
	# Otherwise start with a hint
	if search_group is None:
		search_group = Thread.currentThread().getThreadGroup()
		
		if recursive:
			while search_group.parent is not None:
				search_group = search_group.parent

	# Get all the threads in the group
	# Docs note that this may change moment to moment,
	#   so use it as a guide and check
	estimated_num_threads = search_group.activeCount()
	
	# As a sanity check, ask for more and then be sure we didn't exceed it
	overshot_estimate = int(estimated_num_threads * (sandbagging_percent/100.0))
	
	search_group_threads = zeros(overshot_estimate, Thread)
	
	search_group.enumerate(search_group_threads, recursive)

	matching_threads = []
	match_pattern = re.compile(thread_name_pattern)
	for thread in search_group_threads:
		if not thread:
			continue
		if match_pattern.match(thread.getName()):
			matching_threads.append(thread)
	
	return matching_threads

	
def dangerouslyKillThreads(thread_name_pattern, bypass_interlock='No!'):
	"""Mercilessly kill threads matching the given pattern.
	
	Must set bypass_interlock to "Yes, seriously." (sans quotes, with punctuation).
	  We don't want anyone accidentally fubaring a running system, right?
	"""
	if not bypass_interlock == 'Yes, seriously.':
		return
		
	for thread in findThreads(thread_name_pattern):
		thread.interrupt()
		

def getThreadState(target_thread):
	# Earlier builds of Jython do not have the internals exposed. At least, not the same way.
	# The following introspects the thread tiven and returns what it finds.
	try:
		thread_locals = getReflectedField(target_thread, 'threadLocals')
	
		table = getReflectedField(thread_locals, 'table', 'java.lang.ThreadLocal$ThreadLocalMap')
	
		for entry in table:
			if entry is None:
				continue
			
			value = getReflectedField(entry, 'value')
			
			if isinstance(value, ThreadState):
				return value
		else:
			raise AttributeError("Python ThreadState object not found for given thread!")
	
	# If the thread's dead, attempts to reflect garbage throw NPEs
	except NullPointerException:
		return None

def getFromThreadScope(target_thread, object_name):
	"""Abuse optimizations in Jython or reflection in Java to get objects in other frames.

	For the ThreadStateMapping method, see Jython commit 8f00d52031
	  and http://bugs.jython.org/issue2321
	For the Java reflection introspection, see  
	  https://web.archive.org/web/20150505022210/http://weblogs.java.net/blog/jjviana/archive/2010/06/09/dealing-glassfish-301-memory-leak-or-threadlocal-thread-pool-bad-ide
	  https://web.archive.org/web/20150422074412/http://blog.igorminar.com/2009/03/identifying-threadlocal-memory-leaks-in.html
	"""

	try:
		# Jython 2.7 has a singleton-style dictionary that keeps track of the thread states.
		# Given a thread ID, it will return the ThreadState object
		from org.python.core import ThreadStateMapping
		frame = ThreadStateMapping._current_frames()[target_thread.getId()]

	except (ImportError, AttributeError):
		thread_state = getThreadState(target_thread)
		frame = thread_state.frame

	# The ThreadState object 	contains the current Python frame under execution.
	# Frames have all the needed context to execute, including the variable references in scope.
	return frame.f_locals[object_name]


def getThreadInfo(thread):
	"""Get the thread info object from the Java ThreadMXBean. Thing."""
	from java.lang.management import ManagementFactory
	TMXB = ManagementFactory.getThreadMXBean()
	return TMXB.getThreadInfo(thread.id)