"""
	Helper functions to make dealing with threads a bit less painful.
"""

from functools import wraps, partial
from time import sleep
from datetime import datetime, timedelta
import re
from heapq import heappush, heappop
import sys
from uuid import uuid1 # sequential when seeded
from random import random

from java.lang import Thread, ThreadGroup, NullPointerException
from java.nio.channels import ClosedByInterruptException
from jarray import array, zeros
from org.python.core import ThreadState

from shared.tools.meta import getReflectedField, MetaSingleton, PythonFunctionArguments
from shared.tools.timing import EveryFixedDelay

from shared.tools.logging import Logger
from java.lang import Exception as JavaException, Thread


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
					
					if delaySeconds:
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


SEMAPHORE_WAIT_JITTER_MILLISECONDS = 1.000
SEMAPHORE_WAIT_MILLISECONDS = 2.500

assert SEMAPHORE_WAIT_JITTER_MILLISECONDS < SEMAPHORE_WAIT_MILLISECONDS, 'Jitter should be less than amount that can be taken from...'

# no more than this many calls may be backstuffed in a queue
SEMAPHORE_MAX_QUEUE = 20

class SemaphoreError(RuntimeError): """Errors thrown specifically in the service of the semaphore decorator"""


def semaphore(*arguments, **options):
	"""Block execution until any previously running functions 
	with the same values for the given arguments finish.
	
	Place the semaphore decorator as close to the function as possible,
	under other decorators (since they'll goober up the argument checks)
	
	To block other threads from using a function while in use by another thread
	(even if the other thread only uses it periodically), 
	use `None` for arguments and clue with `<thread>`:
		@semaphore(None, '<thread>')
	
	Special argument flags:
	 - <function>: always included (almost by definition)
	 - <thread>: block by thread (async first come, first serve)
	 - None: don't use arguments to block, just the function (and thread, if flagged)
	
	Options:
	 max_queue: maximum number of blocks per key
	
	Usage:
		@async
		@semaphore('z', 'y')
		# @semaphore
		def bar(x, y, z=5):
			sleep(0.5 + random())
			print x,y,z
			
		for i in range(5):
			bar(i, 99)
	
	This blocks all bar threads with (z=5, y=99) until each finish.
	
	NOTE: This does NOT guarantee they finish in order, 
	      only that they are done one at a time!
	      
	For full JVM-level blocking (in case of sharded Python contexts),
	use ExtraGlobal as the dictionary, as commented out in the code.
	"""
	SEMAPHORE_SPECIAL_ARGUMENTS = set(['<thread>', '<function>'])
	
	# special case: no arguments, just decorator
	# in this case the function blocks if any arguments have the same value
	if (len(arguments) == 1 and not isinstance(arguments[0], str) and getattr(arguments[0], '__call__', None)):
		return semaphore()(arguments[0])	
		
	thread_block = '<thread>' in arguments
	
	if thread_block:
		arguments = tuple(arg for arg in arguments if not arg == '<thread>')
		
	if 'max_queue' in options:
		max_queue = options['max_queue']
	else:
		max_queue = SEMAPHORE_MAX_QUEUE
	
		
	def tuned_decorator(function, arguments=arguments):
		"""Main function bits cribbed from shared.tools.meta.getFunctionCallSigs"""
		assert function is not None
		
		pfa = PythonFunctionArguments(function)
		
		# if no arguments are given, the block on any function with the same inputs
		if len(arguments) == 0:
			arguments = pfa.args
		elif arguments == (None,):
			arguments = tuple()
			
		assert all(arg in pfa.args or (arg in SEMAPHORE_SPECIAL_ARGUMENTS) 
				   for arg in arguments), (
				   "Arguments given to semaphore (%r) must be in decorated function (%r) or be special (%r)" % (
				   arguments, function, SEMAPHORE_SPECIAL_ARGUMENTS,) )		

		# make sure the function can always reference itself,
		# that way even if there's no arguments given, it can
		# still block
		arguments += ('<function>',)
				
		arg_lookup     = dict((arg, ix) for ix,arg in enumerate(pfa.args))
		default_lookup = pfa.defaults
		
		arg_lookup['<function>'] = -1 # out of bounds to force default 
		default_lookup['<function>'] = function
		
		# closure variable
		call_queue_lookup = {}
		thread_id_lookup = {}
				
		@wraps(function)
		def decorated(*args, **kwargs):
		
			my_thread = Thread.currentThread()
			my_thread_id = my_thread.getId()
							
			# keep track of this thread's id in case we try to come back later
			# so that we don't block ourselves (or grab it if it's already been generated)
			# NOTE: we're using Thread.getId() here so that we can be sure we're getting a consistent hash
			#       this wasn't working, and so this annoying indirection was needed since Thread.currentThread()
			#       wasn't returning the actual object 
			call_id = thread_id_lookup.setdefault(my_thread_id, uuid1(node=None, clock_seq = hash(function)))
	
			block_key = tuple(
					kwargs[key]           if key in kwargs else (
					args[arg_lookup[key]] if 0 <= arg_lookup[key] < len(args) else 
					default_lookup.get(key, None)
					)
					for key in arguments
				)

			block_key = tuple((tuple(entry) if isinstance(entry, list) else (
							   frozenset(entry) if isinstance(entry, set) else (
							   frozenset(entry.items()) if isinstance(entry, dict) else (
							   entry
							   ))))
							  for entry in block_key)

			# Get/create the call queueueue
			# NOTE: yes, the "queue" here is a dict - in Java maps are thread safe
			#       and it is _critical_ that nothing break simply adding/removing entries
			# To get the head of the queue, we use min(...) which seems to be fairly safe
			# It's also reasonably fast, and the semaphore is NOT meant to be used for traffic
			#   control - it's to prevent small-ish numbers of threads from tromping on each other!
			
			try:
				call_queue = call_queue_lookup.setdefault(block_key, {})
				# call_queue = EG.setdefault(block_key, scope=(function, semaphore), default={})
			except TypeError as error:
				if 'unhashable' in error.message:
					raise SemaphoreError('An argument in %r could not be hashed: arguments were %r with an attempted key %r' % (function, arguments, block_key))
				else:
					raise error
			
			if len(call_queue) > max_queue:
				raise SemaphoreError('Semaphore for %r blocking more than %d (max) waiting calls! Blocking key: %r' % (function, max_queue, block_key))
			
			# new call_ids are monotonically increasing, so either we're re-entering or we have
			# just gotten a stale id from the earlier thread_id_lookup.setdefault(...)
			if call_queue and call_id < min(call_queue):
				raise SemaphoreError('Semaphore seems to have a reused thread ID with an invalid identifier')
				# we could clean it up automatically by doing the following:
				thread_id_lookup[my_thread_id] = call_id = uuid1(node=None, clock_seq = hash(function))
				# but this isn't tested yet...
						
			if not call_id in call_queue:
				call_queue[call_id] = my_thread
						
			my_thread.sleep(0, 1000) # wait a microsecond in case there's a starting race...
			
			# IMPORTANT: There are two semantics at play here.
			#  - Remove semaphore block when finished - normal blocking monitor (at end)
			#  - Cull dead threads (whose handles are left after they finish) (up next below)
								
			# wait until our number comes up
			# (min is probably safe here, or at least it won't throw an error for 
			#  the dict changing sizes during the check
			#  See https://gist.github.com/null-directory/273498601dfe55b2130234b8d5cc8cd7 )			
			while not min(call_queue) == call_id:
				# wait, with jitter
				wait = SEMAPHORE_WAIT_MILLISECONDS + (SEMAPHORE_WAIT_JITTER_MILLISECONDS * random())
				wait_ms, wait_ns = divmod(wait, 1.0)
				# (by splitting up, we can get faster loops, if desired...
				#  just be warned that lots of threads can lead to a lot of wheel spinning)
				Thread.sleep(int(wait_ms), int(wait_ns*1000000))
				
				# attempt to clear a dead head off queue, if needed
				# (subsequent iterations will *eventually* drain the queue if many die,
				#  and the larger the queue the faster it drains... -ish.)
				head = min(call_queue)
				try:
					head_thread = call_queue[head]
					if head_thread.getState() == Thread.State.TERMINATED:
						try: # attempt to purge thread ref first
							del thread_id_lookup[head_thread.getId()]
						except KeyError:
							pass						
						try: # release lock
							del call_queue[head]
						except KeyError: 
							pass
				except:
					pass
							
			try:
				results = function(*args, **kwargs)
			except Exception as error:
				raise error
			finally:
				# hold the door open if blocking by thread (wait for cleanup in wait loop)
				if thread_block:
					pass
				# clear the block if we don't need to wait for other work
				else:
					try: # attempt to purge thread ref first
						del thread_id_lookup[my_thread_id]
					except KeyError:
						pass
					try: # release lock
						del call_queue[call_id]
					except KeyError:
						pass # job already done
					pass 

			return results
			
		return decorated

	return tuned_decorator
