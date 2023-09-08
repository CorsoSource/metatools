"""
	Better logging

	Allow each thread to have its own logger, but to always use the same calling convention.
	
	It's almost pure syntactic sugar, but it's nice to not need to remember a logger's name 
	and instead just know `self.logger` will be the correct thing.

"""
from shared.data.context.threading.base import ThreadContexts
from shared.data.context.threading.naming import NamedThreadContexts

from java.lang import Thread


DEFAULT_LOGGING_LEVEL = 'trace'


class ThreadSpecificLogging(ThreadContexts):
	"""
	Allow the context shared between threads to resolve itself, if needed.
	"""
	__module__ = shared.tools.meta.get_module_path(1)
	
	_LOGGER_PREFIX_PADDING = None
	_LOGGER_PREFIX_PADDING_MIN = 7

	_INITIAL_LOGGING_LEVEL = DEFAULT_LOGGING_LEVEL

	_LOGGER_CLASS = shared.tools.logging.Logger
	
	
	def __init__(self, *args, **kwargs):
		self._thread_loggers = {
			Thread.currentThread(): self._generate_logger('Context'),
			None: self._generate_logger('  >_<  '), # default/missing/orphaned
		}
		super(ThreadSpecificLogging, self).__init__(*args, **kwargs)
	
	def _add_thread(self, role, thread=None, is_context_init=False, logger_name=None):
		if thread is None: thread = Thread.currentThread()
		self._thread_loggers[thread] = self._generate_logger(logger_name or role, logging_level=self._INITIAL_LOGGING_LEVEL)
		super(ThreadSpecificLogging, self)._add_thread(role, thread, is_context_init)

	def _generate_logger(self, role, logger_name=None, *logger_args, **logger_kwargs):
		if logger_name is None: # default to driver's class name for logger
			logger_name = type(self).__name__
		if role is None:
			role = self._CONTEXT_THREAD_ROLE
		if self._LOGGER_PREFIX_PADDING:
			prefix = '[%%-%ds] ' % max([self._LOGGER_PREFIX_PADDING, self._LOGGER_PREFIX_PADDING_MIN])
		else:
			prefix = '[%s] '
		prefix %= role
		logger_kwargs['prefix'] = prefix
		return self._LOGGER_CLASS(logger_name, *logger_args, **logger_kwargs)
	
	@property
	def logger(self):
		# as threads drop out of scope, one can imainge the GC cleaning up the original scopes that these started in.
		# imports then, may not be there. Most of the context here is self-sufficient, but it's possible for
		# imports that are pulled in via `globals` not to be available in scope
		# (this is why all async threads should treat themselves as new scopes if they're not guaranteed to rejoin the forked thread)
		#
		# (... and yes, this was a symptom found during testing...)
		#
		# NOTE: this is the ONLY place the Context engine will perform a manual import. In all other circumstances the holding threads
		#       will be keeping objects and scopes in memory, but child threads are only weakly referenced by the holding context.
		# The idea is anything may break, but logging needs to be relied on, even as the world GC's
		try:
			thread = Thread.currentThread()
		except NameError:
			from java.lang import Thread
			thread = Thread.currentThread()
		return self._thread_loggers.get(thread, self._thread_loggers[None])


class NamedThreadSpecificLogging(ThreadSpecificLogging, NamedThreadContexts):
	__module__ = shared.tools.meta.get_module_path(1)
	
	def __init__(self, *args, **kwargs):
		super(NamedThreadSpecificLogging, self).__init__(*args, **kwargs)
		for logger in self._thread_loggers.values():
			logger.suffix = ' [%s]' % (self.identifier,)
	
	def _generate_logger(self, *args, **kwargs):
		logger = super(NamedThreadSpecificLogging, self)._generate_logger(*args, **kwargs)
		try:
			logger.suffix = ' [%s]' % (self.identifier,)
		except AttributeError:
			logger.suffix = ' [????]' # ID not yet set!
		return logger