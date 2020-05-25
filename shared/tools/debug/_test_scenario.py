#shared.tools.pretty.install()
#from time import sleep
#from shared.insitu import launch_target_thread
#target_thread = launch_target_thread()
#sleep(0.5)
#
#from shared.tools.debug.tracer import Tracer
#tracer = Tracer.tracers[0]
#tracer

# print "Pausing before scenario..."
# sleep(2.0)
# print "initializing scenario:"
from shared.tools.data import randomId
from shared.tools.thread import async
from shared.tools.debug.codecache import CodeCache
import textwrap
# So: build a new thread bootstrapped with the given code

def fork_scenario(frame, backref='', sys_context=None):
	
	if not backref:
		backref = '<%s>' % randomId(6)
	
	source = CodeCache.get_lines(frame, radius=0, sys_context=sys_context)
	
	# frame lines are one-indexed
	frame_first_line_number = frame.f_code.co_firstlineno
	frame_first_line = source[frame_first_line_number - 1]
	
	spacer = frame_first_line[0]
	
	for indent_count, c in enumerate(frame_first_line):
		# zero-index means we end on the count
		if c != spacer:
			break
	
	# increase the indent by one since the frame is actually executed
	#   inside the definition, not _on_ it.
	indent = spacer * (indent_count + 1)
	code_block = []
	for line in source[frame_first_line_number:]:
		# add any lines that are the expected indent
		if line.startswith(indent):
			code_block.append(line)
		# once we're past the def statement, break if we dedent
		elif code_block:
			break
	
	while not code_block[-1].strip():
		_ = code_block.pop(-1)
	
	head_code = [indent + line for line in """
from shared.tools.debug.tracer import set_trace
set_trace()
""".splitlines() if line]
	
	code_block = head_code + code_block
	
	#CodeCache._render_tabstops(code_block)
	code = compile(textwrap.dedent('\n'.join(code_block)), '<tracer-scenario:%s>' % backref, 'exec')
	
	argument_names = frame.f_code.co_varnames[:frame.f_code.co_argcount]
	
	scenario_locals = dict((arg_name, frame.f_locals[arg_name]) 
						   for arg_name in argument_names)
	
	scenario_globals = frame.f_globals.copy()
	#del scenario_globals['Tracer']
	
	@async(name='Tracer Scenario - %s' % backref)
	def initialize_scenario(code=code, 
							scenario_globals=scenario_globals, 
							scenario_locals=scenario_locals):
		exec(code, scenario_globals, scenario_locals)
		
	return initialize_scenario()

scenario_thread = fork_scenario(tracer.cursor_frame, tracer.id, tracer.sys)

sleep(0.5)

from shared.tools.thread import getThreadState, getThreadInfo
scenario_thread.state
getThreadState(scenario_thread).frame


#h = lambda o, scenario_thread=scenario_thread: scenario_thread.holdsLock(o)