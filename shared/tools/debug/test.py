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
		
		def bar(x, steps=5):
			
			for y in range(steps):
				x += 1
				sleep(0.05)
			
			y = x * 2
			
			return x
			
		while True:
			find_me = bar(find_me, steps=10)
			
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


# from shared.tools.debug._test import initialize_test
# tracer = initialize_test()


# Jython 2.5.3 (, Dec 6 2018, 12:34:00) 
# [Java HotSpot(TM) 64-Bit Server VM (Oracle Corporation)] on java1.8.0_221

# >>> 
# Tracing from Thread[SwingWorker-pool-2-thread-2,5,javawsApplicationThreadGroup] onto Thread[debug_test,5,javawsApplicationThreadGroup]
# >>> tracer
# <tracer.Tracer object at 0x2>
# >>> tracer.interdict()
# >>> tracer.current_context
# <Snapshot [ |   3:  Line]   25 of <module:shared.tools.debug._test> at bar>
# >>> len(tracer.context_buffer)
# 1
# >>> tracer._pending_commands.append('s')
# >>> len(tracer.context_buffer)
# 2
# >>> tracer.current_context
# <Snapshot [ |   3:  Line]   26 of <module:shared.tools.debug._test> at bar>
# >>> tracer._pending_commands.append('s')
# >>> tracer.current_context
# <Snapshot [ |   3:  Line]   27 of <module:shared.tools.debug._test> at bar>
# >>> tracer._pending_commands.append('u')
# >>> tracer.current_context
# <Snapshot [ |   3:  Line]   25 of <module:shared.tools.debug._test> at bar>
# >>> tracer.traps
# set([])
# >>> tracer.active_traps
# set([<trap.Until object at 0x3c>])
