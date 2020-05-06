from shared.tools.thread import async, dangerouslyKillThreads

from time import sleep

RUNNING_THREAD_NAME = 'debug_test'

dangerouslyKillThreads(RUNNING_THREAD_NAME, bypass_interlock='Yes, seriously.')

@async(name='debug_test')
def monitored():
	close_loop = False
	
	time_delay = 0.5
	find_me = 0
	
	def bar(x, steps=5):
		
		for y in range(steps):
			x += 1
		
		y = x * 2
		
		return x
		
	while True:
		find_me = bar(find_me, steps=10)
		
		sleep(time_delay)
		
		if close_loop:
			break
	
	print 'Finished'

running_thread = monitored()


shared.tools.pretty.install()

# from shared.tools.debug.tracer import Tracer
from metatools.debug.tracer import Tracer

# Load up tracer instance
#tracer = Tracer(running_thread)
