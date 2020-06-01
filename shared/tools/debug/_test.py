"""
	A simple test script to exercise the tracer against.
"""

__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


#from shared.tools.debug._test import initialize_test
#tracer = initialize_test()
#tracer.cursor_frame

from shared.tools.thread import async, dangerouslyKillThreads
from shared.tools.debug.tracer import set_trace
from time import sleep


RUNNING_THREAD_NAME = 'debug_test'


def launch_target_thread(test_thread_name=RUNNING_THREAD_NAME):
	
	dangerouslyKillThreads(test_thread_name, bypass_interlock='Yes, seriously.')
	
	@async(name=test_thread_name)
	def monitored():
		close_loop = False
		
		set_trace(control_tag='[default]_Tracers')
		
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
