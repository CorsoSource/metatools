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


# from shared.tools.debug._test import initialize_test
# tracer = initialize_test()


# Jython 2.5.3 (, Dec 6 2018, 12:34:00) 
# [Java HotSpot(TM) 64-Bit Server VM (Oracle Corporation)] on java1.8.0_221

# >>> 
# Tracing from Thread[SwingWorker-pool-2-thread-2,5,javawsApplicationThreadGroup] onto Thread[debug_test,5,javawsApplicationThreadGroup]
# >>> tracer.cursor_frame
#   Properties of <'frame'>
#   =========================
#   <frame object at 0x682>
#   -------------------------
#   Attribute      (P)   Repr                                                                                                                         <Type>       
#   ----------     ---   ------------------------------------------------------------------------------------------------------------------------     -----------  
#   f_back               <frame in "<module:shared.tools.thread>" of "full_closure" on line 170>                                                                   
#   f_builtins           {'coerce': <built-in function coerce>, 'callable': <built-in function callable>, 'AttributeError': <type 'exceptions....     dict         
#   f_code               <code object monitored at 0x683, file "<module:shared.tools.debug._test>", line 16>                                          tablecode    
#   f_globals            {'app': <app package app at 1668>, 'shared': <app package shared at 1669>, 'initialize_test': <function initialize_te...     dict         
#   f_lasti              0                                                                                                                            int          
#   f_lineno             36                                                                                                                           int          
#   f_locals             <'dict'> of 4 elements                                                                                                                    
#                                   bar : λ(x, steps=5)
#                            close_loop : False
#                               find_me : 22   
#                            time_delay : 0.5  
#   f_trace              None                                                                                                                         NoneType     

# >>> tracer.cursor_frame
#   Properties of <'frame'>
#   =========================
#   <frame object at 0x68d>
#   -------------------------
#   Attribute      (P)   Repr                                                                                                                         <Type>       
#   ----------     ---   ------------------------------------------------------------------------------------------------------------------------     -----------  
#   f_back               <frame in "<module:shared.tools.debug._test>" of "monitored" on line 34>                                                                  
#   f_builtins           {'coerce': <built-in function coerce>, 'callable': <built-in function callable>, 'AttributeError': <type 'exceptions....     dict         
#   f_code               <code object bar at 0x68e, file "<module:shared.tools.debug._test>", line 23>                                                tablecode    
#   f_globals            {'app': <app package app at 1668>, 'shared': <app package shared at 1669>, 'initialize_test': <function initialize_te...     dict         
#   f_lasti              0                                                                                                                            int          
#   f_lineno             27                                                                                                                           int          
#   f_locals             <'dict'> of 3 elements                                                                                                                    
#                            steps : 2 
#                                x : 28
#                                y : 1 
#   f_trace              None                                                                                                                         NoneType     

# >>> tracer.interdict()
# >>> 
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer._command_step()
# >>> tracer.shutdown()
# >>> tracer.shutdown()
