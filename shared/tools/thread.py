"""
	Helper functions to make dealing with threads a bit less painful.
"""


from __future__ import with_statement
from functools import wraps, partial
from time import sleep
import re


from java.lang import Thread, ThreadGroup
from jarray import array, zeros
from org.python.core import ThreadState

from shared.tools.meta import getReflectedField


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


__all__ = ['async', 'findThread', 'getThreadObject']


def async(startDelaySeconds=None, name=None):
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

	if name or isinstance(startDelaySeconds, (int, long, float)):
		if name and startDelaySeconds is None:
			startDelaySeconds = 0.0
		# Convert to check param... Clamps to millisecond multiples
		delaySeconds = int(startDelaySeconds*1000.0)/1000.0
		
		# Since we passed in a value, we'll need to return an actual decorator function
		def asyncDecoWrapper(function):
			
			@wraps(function)
			def asyncWrapper(*args, **kwargs):
		
				# Create the closure to carry the scope into another thread
				def full_closure(function, delaySeconds, args=args, kwargs=kwargs):
					#print 'delaying %0.3f' % delaySeconds
					sleep(delaySeconds)
					try:
						_ = function(*args,**kwargs)
					except KeyboardInterrupt:
						pass
					
				# Wrap the function and delay values to prevent early GC of function and delay
				closure = partial(full_closure, function, delaySeconds)
				
				# Async calls should return the thread handle. 
				# They will _not_ return whatever the function returned. That gets dumped to _.
				thread_handle = system.util.invokeAsynchronous(closure)
				if name:
					thread_handle.setName(name)
				return thread_handle
			return asyncWrapper
		return asyncDecoWrapper
	
	else:		
		# Decorator didn't have a param, so this is actually a function
		function = startDelaySeconds
		
		try:
			@wraps(function)
			def asyncWrapper(*args, **kwargs):
				# Create the closure to carry the scope into another thread
				def full_closure(function, args=args, kwargs=kwargs):
					try:
						_ = function(*args,**kwargs)
					except KeyboardInterrupt:
						pass

				# Wrap the function and delay values to prevent early GC of function and delay
				closure = partial(full_closure, function)
				
				# Async calls should return the thread handle. 
				# They will _not_ return whatever the function returned. That gets dumped to _.
				return system.util.invokeAsynchronous(closure)
			return asyncWrapper

		# If the @async decorator was called with empty parenthesis, then the Python engine
		# will assume the results are _themselves_ a decorator. This leads to an AttributeError.
		# Simply call it correctly here.
		except AttributeError:
			assert startDelaySeconds is None and name is None, 'The @async decorator was likely called wrong.\nSimply do not use () with no params.'
			return async(0)


def findThread(thread_name_pattern='.*', search_group=None, recursive=False, sandbagging_percent=110):
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
		# Earlier builds of Jython do not have the internals exposed. At least, not the same way.
		# The following introspects the thread tiven and returns what it finds.
		thread_locals = getReflectedField(target_thread, 'threadLocals')

		table = getReflectedField(thread_locals, 'table', 'java.lang.ThreadLocal$ThreadLocalMap')

		for entry in table:
			if entry is None:
				continue
			
			value = getReflectedField(entry, 'value')
			
			if isinstance(value, ThreadState):
				thread_state = value
				frame = thread_state.frame
				break
		else:
			raise AttributeError("Python ThreadState object not found for given thread!")
		
	# The ThreadState object contains the current Python frame under execution.
	# Frames have all the needed context to execute, including the variable references in scope.
	return frame.f_locals[object_name]
