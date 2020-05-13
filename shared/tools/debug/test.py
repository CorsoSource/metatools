from shared.tools.debug.tracer import Tracer

from shared.tools.thread import async, dangerouslyKillThreads

from time import sleep

RUNNING_THREAD_NAME = 'debug_test'

TEST_TRACER = None

def initialize_test(test_thread_name=RUNNING_THREAD_NAME, FAILSAFE=False):
	global TEST_TRACER

	dangerouslyKillThreads(test_thread_name, bypass_interlock='Yes, seriously.')

	@async(name=test_thread_name)
	def monitored():
		close_loop = False
		
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
			
			sleep(time_delay)
			
			if close_loop:
				break
		
		print 'Finished'

	running_thread = monitored()


	# Install pretty printing
	shared.tools.pretty.install()

	# Load up tracer instance
	Tracer.INTERDICTION_FAILSAFE = FAILSAFE
	TEST_TRACER = Tracer(running_thread, record=True)
	return TEST_TRACER


#from shared.tools.debug._test import initialize_test
#tracer = initialize_test()
#tracer.cursor_frame
#
#tracer.interdict()
#tracer._pending_commands.extend(['s']*8)
#for context in tracer.context_buffer:
#	print repr(context)
