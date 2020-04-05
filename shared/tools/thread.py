"""
	Helper functions to make dealing with threads a bit less painful.
"""


from __future__ import with_statement
from functools import wraps, partial
from time import sleep


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


def async(startDelaySeconds=None):
	"""Decorate a function with this to make it run in another thread asynchronously!
	If defined with a value, it will wait that many seconds before firing.
	
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

	try:
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
					_ = function(*args,**kwargs)
					
				# Wrap the function and delay values to prevent early GC of function and delay
				closure = partial(full_closure, function, delaySeconds)
				
				# Async calls should return the thread handle. 
				# They will _not_ return whatever the function returned. That gets dumped to _.
				return system.util.invokeAsynchronous(closure)				
			return asyncWrapper
		return asyncDecoWrapper
		
	except TypeError:
		
		# Decorator didn't have a param, so this is actually a function
		function = startDelaySeconds
		
		try:
			@wraps(function)
			def asyncWrapper(*args, **kwargs):
				# Create the closure to carry the scope into another thread
				def full_closure(function, args=args, kwargs=kwargs):
					#print 'running immediately'
					_ = function(*args,**kwargs)
				
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
			assert startDelaySeconds is None, 'The @async decorator was likely called wrong.'
			return async(0)