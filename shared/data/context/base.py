"""
	Base interface expected for a Context

"""
from shared.data.context.utility import formatted_traceback, JavaException



class ContextManagementForContexts(object):
	"""
	Let the context have, well, context management functionality.
	
	And yes. The class name is terrible. Shame about how jargon overlaps.
	But it's just a mixin and I wanted to have it organized and separate.    
	"""
	__module__ = shared.tools.meta.get_module_path(1)

	def __init__(self, *args, **kwargs):
		self.initialize_context(*args, **kwargs)

	
	###########################
	# context setup and startup

	def initialize_context(self, *args, **kwargs):
		"""
		Subclasses MUST IMPLEMENT initialize_context, 

		This method sets up the context to be self-sufficient. It runs immediately after __init__.

		Also note that this takes the __init__ arguments. Context is not launching with this,
		merely setting itself up. Please keep launching bits to the launch_context method.
		"""
		raise NotImplementedError

	def launch_context(self):
		"""
		Subclasses MUST IMPLEMENT launch_context by calling super() at the end.
		
		This method launches any extra threads/functions that might be needed.
		Note that this is unlike init_context, which merely sets up the context.
		
		Also note that it takes no arguments: context should be initialized and
		self-sufficient by the time it launches itself!
		"""
		raise NotImplementedError

	
	def finish_context(self):
		"""
		Subclasses MUST IMPLEMENT finish_context, calling super() at the end.

		Subclasses should do any preparatory work in getting the context into a closable state,
		but not actually do any aggressive thread management bits - that's for the context mechanics.

		Ultimately, this method tears down and cleans up any extra threads/functions that were needed.

		Also note that it does not stop the main context thread. The context should be able to
		re-launch after this!
		"""
		raise NotImplementedError

	
	def crash_context(self):
		"""
		Subclasses MUST IMPLEMENT crash_context, calling super() at the end.

		This method tears down and cleans up any extra threads/functions that were needed.
		This does NOT simply call finish_context by default. It CAN, but should be considered
		a more severe and urgent request to drop everything and stop doing things.

		Also note that it will crash the main context thread. This should leave the system
		as safely as finish_context, but expects the context not to be used after.

		By default a KeyboardInterrupt crashes the context during an __exit__ but does not
		crash the actual thread, allowing for follow up. Any error thrown during finish_context
		or crash_context WILL be re-raised, leading to the main thread throwing up the exception.
		Blech.
		"""
		raise NotImplementedError


	
	def _launch_context(self):
		self.launch_context()

	def _finish_context(self):
		self.finish_context()
	
	def _crash_context(self):
		self.crash_context()


   
	def __enter__(self):
		"""Enter main context block (likely a sleep/timer/event loop)"""
		self.logger.trace('[__enter__] Launching context')
		self._launch_context()
		self.logger.trace('[__enter__] Context launched')
		
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		"""Exit the main context block (likely tear down and stop)"""
		self.logger.error('exiting context')
		try:
			if exc_type is None:
				self._finish_context()
				return True
			elif exc_type is KeyboardInterrupt:
				self._crash_context()
				return True # consume the error
			else:
				self.logger.error('Exiting managed context with: \n\t%r' % (exc_val,))
				raise exc_val
		
		except (Exception,JavaException) as error:
			self.logger.error(formatted_traceback(exc_val, exc_tb))
			self._crash_context() # fail safe... violently
			raise error
		
		finally:
			self.logger.error('exited context')