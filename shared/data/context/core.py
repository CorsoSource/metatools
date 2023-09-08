"""
	The core context example class

"""
from shared.data.context.utility import DictLikeAccessMixin
from shared.data.context.threading.naming import NamedThreadContexts
from shared.data.context.threading.logging import NamedThreadSpecificLogging
from shared.data.context.threading.polling import EventLoop, RoleSpecificEventLoop, poll
from shared.data.context.threading.signals import Signalling, EventLoopSignalProcessing, RoleSpecificEventLoopStopSignaling

from shared.data.context.meta import MetaContext



class Context(
	# event loop reactions
	RoleSpecificEventLoopStopSignaling,
	
	# event loop control
	EventLoopSignalProcessing,
	Signalling,
	
	# event loops
	RoleSpecificEventLoop,
	EventLoop,
	
	# core thread control
	NamedThreadSpecificLogging,
	NamedThreadContexts,
	
	# utility
	DictLikeAccessMixin,
	):
	__module__ = shared.tools.meta.get_module_path(1)
	__metaclass__ = MetaContext

	def initialize_context(self, *init_args, **init_kwargs):
		raise NotImplementedError

	def launch_context(self):
		raise NotImplementedError

	def finish_context(self):
		pass

	def crash_context(self):
		pass

		
	def poll_context(self):
		raise NotImplementedError()
	
	
	@staticmethod
	def poll(role):
		"""Convenience method to make sure decorator is available"""
		return poll(role)
		



def _run_tests():

	#from shared.tools.thread import findThreads
	#[thread.interrupt() for thread in findThreads('TestContext-.+-context')]

	from shared.tools.pretty import p,pdir,install;install()
	from shared.data.context.core import Context

	from time import sleep


	class TestContext(Context):
		
		__slots__ = ('one', 'two',)
		
		def initialize_context(self, one=0, two=0):
			self.one = one
			self.two = two

		def launch_context(self):
			self.poll_one()
			self.poll_two()
			self.poll_two()
		
		def poll_context(self):
			if self.one > self.two:
				self.logger.debug('Two seems to have reset. Fast forwarding.')
				self.two = self.one*2

		@Context.poll('one')
		def poll_one(self):
			self.one += 1
			self.logger.trace('%(one)d', one=self.one)

		@Context.poll('two')
		def poll_two(self):
			self.two += 2

		def handle_signal_two(self, signal):
			self.logger.debug('Signal sent to [two]: %(signal)r')
			if signal == 'reset':
				self.two = 0


	threads = []

	for i in range(4):
		tc = TestContext()
		threads.append(
			tc.start_loop()
		)

	# let it run a moment
	sleep(3)


	# stop the last gracefully
	tc.stop_loop()

	sleep(2)

	# crash the first
	threads[0].interrupt()

	sleep(2)

	# request the rest to stop
	[tc.stop_loop() for tc in TestContext]

	# NOTE: Make sure to read the logs and verify this behaved!
	# none of these are catastrophic crashes - the interrupt merely
	# halts the main context's loop, which tears all the other threads down.