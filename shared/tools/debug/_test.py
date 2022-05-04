"""
	A simple test script to exercise the tracer against.

	This launches a thread that is immediately interdicted by a tracer.
	  The thread has just enough features to exercise and see the different
	  events and ways to control/watch/manipulate program flow.

	A tracer reference is going to be added to the tag folder
	  `[default]_Tracers/<TRACER_ID>` and will accept commands from there.
	Otherwise get the tracer from ExtraGlobal and interact with the thread!

	As a starting hint, use tracer << 'help' to get more info on available commands.
	  If the tracer is running on the gateway or on a remote client,
	  the tag command line is the only way to control it.


	Test script (run from interactive console for best results!)

		>>> debug_thread = shared.tools.debug._test.launch_target_thread()
		>>> from shared.tools.debug.tracer import Tracer
		>>> shared.tools.pretty.install()
		>>> Tracer.tracers
		>>> tracer = Tracer.tracers[0]
		>>> tracer << 'help'
		>>> tracer.current_context
"""

__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'



from shared.tools.thread import async, dangerouslyKillThreads
from shared.tools.debug.tracer import set_trace
from time import sleep


RUNNING_THREAD_NAME = 'debug_test'

TAG_CONTROL_FOLDER = '[default]_Tracers/'


def launch_target_thread(test_thread_name=RUNNING_THREAD_NAME, tag_control_folder=TAG_CONTROL_FOLDER):

	dangerouslyKillThreads(test_thread_name, bypass_interlock='Yes, seriously.')

	@async(name=test_thread_name)
	def monitored(_tcf=tag_control_folder):
		close_loop = False

		set_trace(control_tag=_tcf)

		time_delay = 0.5
		find_me = 0

		some_dict = {"j": 43.21}

		def bar(x, steps=5):

			for y in range(steps):
				x += 1
				sleep(0.05)

			y = x * 2

			return x

		while True:
			find_me = bar(find_me, steps=2)

			print 'find_me: ', find_me
			sleep(time_delay)

			if close_loop:
				break

			try:
				if throw_error:
					x = 1/0
			except NameError:
				pass

		print 'Finished'

	return monitored()

#target_thread = launch_target_thread()
