"""
	Mark a context's method as launchable
	
	Because the polling loop pattern is so common, this makes it
	trivial to have a polling mechanism


"""
from shared.data.context.utility import async, apply_jitter
from shared.data.context.utility import formatted_traceback, JavaException
from shared.data.context.threading.base import ThreadContexts, Thread
from shared.data.context.config import CONTEXT_USES_SLOTS


import functools
from time import sleep



def poll(role):
	"""
	Decorate methods as @poll to have them automatically be run asynchronously
	and added to the context when run.

	The argument role defines how it's added to the context. It is not optional.
	"""
	assert role, "Launched threads must be assigned a role."
	
	# adjective
	def pollable_role_method(role_method):
		"""
		The actual decorator. This takes the role and allows for the method's bookkeeping after launching.
		"""
		# directive
		@functools.wraps(role_method)
		def poll_role_method(self, *args, **kwargs):
			"""
			Fires off the context's method in its own thread while also ensuring that
			signals can be processed, at least occasionally.
			"""
			self.logger.trace('[launching role method] launching %(role_method)r')
			assert isinstance(self, EventLoop), """The @launchable decorator assumes the method's class subclasses/implements the ContextLoopControlMixin"""
			
			# verb
			@async(
				name=self._thread_name_format(pending=True) % self._thread_name_parts(role), 
				startDelaySeconds=self._ROLE_EVENT_LOOP_STARTUP_DELAY,
			)
			def polling_role_method(context=self, role_method=role_method, *args, **kwargs):
				context.logger.trace('[launched role] starting loop %(role_method)s')
				# decoractor indirection effectively leaves role_method unbound, so let's set that
				@functools.wraps(role_method)
				def role_method_partial(*args, **kwargs):
					role_method(context, *args, **kwargs)
#               role_method_partial = functools.partial(role_method, context)
#               functools.update_wrapper(role_method_partial, role_method)
				try:
					context.logger.trace('entering loop %(context)r with %(role_method_partial)r (%(role_method)r)')
					context._method_polling_loop(role_method_partial, *args, **kwargs)
					context.logger.trace('loop finished')
				except (Exception, JavaException) as error:
					exc_type, exc_val, exc_tb = sys.exc_info()
					context.logger.error(formatted_traceback(exc_val, exc_tb))
				finally:
					context.logger.debug('[launched role] Event polling loop ended for %(role_method)s. Removing thread from context.')
					context._remove_thread(interrupt_thread=False) # no need to interrupt: it's returning now
					context.logger.trace('[launched role] Removed %r from context tracking' % (Thread.currentThread(),))
					return
					
			thread = polling_role_method(*args, **kwargs)
			self._add_thread(role, thread)
			self.logger.trace('[launching role method] Done! %(role_method)r is now live.')

		return poll_role_method
	return pollable_role_method



class EventLoop(ThreadContexts):
	"""
	Extend the thread context management to make it easier to launch methods as their own threads.
	"""
	_EVENT_LOOP_DELAY = 0.25 # seconds
	_ROLE_EVENT_LOOP_STARTUP_DELAY = 2*_EVENT_LOOP_DELAY
	_CONTEXT_EVENT_LOOP_STARTUP_DELAY = 4*_EVENT_LOOP_DELAY

	_THREAD_DEATH_LOOP_WAIT = 1.1 * _EVENT_LOOP_DELAY


	def hoist_context(self):
		"""
		Uplift the context into its own control loop.
		
		Unlike role-based methods, this one is a little specialized and manages a 
		slightly different setup in comparison to methods decorated by @poll
		Primarily it's merely that it throws the context into it's context manager form.
		"""
		assert not self._context_threads, "Will not hoist context into its own thread: context already assigned another"

		@async(
			name=self._thread_name_format(pending=True) % self._thread_name_parts('context'), 
			startDelaySeconds = self._CONTEXT_EVENT_LOOP_STARTUP_DELAY,
		)
		def launched_context(context=self):
			context.logger.trace('[Hoist (async)] - launching %r in %r' % (context, Thread.currentThread(),))
			# launch the context and begin it's polling loop
			with context:
				context.logger.trace("[Hoist (async)] entered context management for %(context)r")
				context._method_polling_loop(context.poll_context)
			context.logger.trace('[Hoist (async)] context management complete and unwound')
			
		thread = launched_context()
		# context will already take ownership of the thread, but this will make sure it's there
		# even before it's fully spun up
		self._add_thread(None, thread, is_context_init=True)
		self.logger.debug('Added context thread: %r' % (thread,))
		return thread

	start_loop = hoist_context


	@property
	def _event_loop_delay(self):
		# by default, simply wait a moment - this will get replaced in subclasses with smarter variants
		return self._EVENT_LOOP_DELAY


	def poll_context(self):
		"""
		Subclasses NEED TO implement poll_context.
		
		This method processes any messages or events or whatever needed to keep
		the context running. 
		
		Any exceptions caught must be re-thrown if handled.
		
		Also note that it takes no arguments: context should be initialized and
		self-sufficient by the time it runs!
		"""
		raise NotImplementedError('Context should do SOMETHING. Override as a `pass` if it should be a NOP.')


	def poll_context_setup(self):
		"""
		Subclasses don't need to use this. The `init_context` method is meant to do this work.
		
		But IFF the context needs to do something right before entering `poll_context`
		and also after `init_context`, then, well, here it is. Have at it and enjoy.
		
		It's here to also act as a breadcrumb to show how the `_method_polling_loop`
		construct works.
		"""
		pass


	# post-facto dispatch/routing/overriding for loop behavior
	def _method_polling_loop_pre_iter(self, role_method, *args, **kwargs):
		"""Give subclasses the ability to do work before an iteration in the polling loop"""
		pass

	def _method_polling_loop_post_iter(self, role_method, *args, **kwargs):
		"""Give subclasses the ability to do work after an iteration in the polling loop"""
		pass


	def _method_polling_loop(self, role_method, *args, **kwargs):
		"""
		Pass in a method that gets thrown into a polling loop.
		
		Follows the convention of __init__ somewhat: args passed in are also passed to
		the _setup function
		
		"""
		setup_method = getattr(self, role_method.__name__ + '_setup', None)
		
		if setup_method is not None:
			setup_method(*args, **kwargs)
			sleep(self._event_loop_delay)
		
		try:
			# enter polling loop
			self.logger.trace('Entering polling loop')
			
			while True:
				# check if anything should be done/checked before iterating
				self._method_polling_loop_pre_iter(role_method, *args, **kwargs)
				
				# iterate!
				role_method(*args, **kwargs)
				
				# check if anything should be done after iterating
				self._method_polling_loop_post_iter(role_method, *args, **kwargs)
				
				# wait a moment before iterating
				sleep(self._event_loop_delay)
		
		except StopIteration:
			# silently and gracefully stop
			self.logger.debug('Stop requested.')
			return
		
		except KeyboardInterrupt:
			# noisily stop
			raise KeyboardInterrupt('Interrupt signal caught for %r' % role_method)
		
		except (Exception,JavaException) as error:
			exc_type, exc_val, exc_tb = sys.exc_info()
			self.logger.error(formatted_traceback(exc_val, exc_tb))
			raise error



class RoleSpecificEventLoop(EventLoop):
	__module__ = shared.tools.meta.get_module_path(1)

	if CONTEXT_USES_SLOTS:
		__slots__ = (
			'_role_event_loop_delays',
		)

	# Jitter can make sure that event loops don't cause a thundering herd effect
	_EVENT_LOOP_JITTER = 0.1

	def __init__(self, *args, **kwargs):
		self._role_event_loop_delays = {}
		super(RoleSpecificEventLoop, self).__init__(*args, **kwargs)

	@property
	def _event_loop_delay(self):
		delay = self._role_event_loop_delays.get(self.role, self._EVENT_LOOP_DELAY)
		if self._EVENT_LOOP_JITTER:
			delay = apply_jitter(delay, self._EVENT_LOOP_JITTER)
		return delay

	def _set_role_event_loop_delay(self, role, delay=None):
		if delay is None:
			delay = self._EVENT_LOOP_DELAY
		if isinstance(delay, timedelta):
			delay = delay.total_seconds()
		self._role_event_loop_delays[role] = delay