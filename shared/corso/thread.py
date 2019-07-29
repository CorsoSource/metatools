"""
	Helper functions to make dealing with threads a bit less painful.
"""



from __future__ import with_statement
from functools import wraps, partial
from time import sleep

def async(startDelaySeconds=None):
	"""Decorate a function with this to make it run in another thread asynchronously!
	If defined with a value, it will wait that many seconds before firing.

	For a function to immediately run:
	@async
	def foo(x,y=5):
		print x,y

	For a 1.5 second delay before executing:
	@async(1.5)
	def bar(a,b,c=5):
		print a,b,c
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
					print 'delaying %d' % delaySeconds
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
					print 'running immediately'
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