from shared.tools.thread import async, findThreads, getThreadState, dangerouslyKillThreads
from time import sleep


thread_name = 'running-thread'

dangerouslyKillThreads(thread_name, bypass_interlock='Yes, seriously.')
stop = lambda: dangerouslyKillThreads(thread_name, bypass_interlock='Yes, seriously.')

@async(name=thread_name)
def running():
	counting = 1
	
	while counting:
		counting += 1
		print 'Count: %d' % counting
		sleep(0.5)

running_thread = running()	



from shared.tools.pretty import p,pdir

from shared.tools.meta import getObjectName, getFunctionCallSigs, sentinel, isJavaObject, getReflectedField
from shared.tools.thread import async, findThreads, getThreadState
from shared.tools.compat import property

from shared.tools.global import ExtraGlobal

from java.lang import Thread, ThreadGroup
from jarray import array, zeros
from org.python.core import ThreadState, Py
from org.python.core import PythonTraceFunction

from StringIO import StringIO

from time import time

import sys
import re, math, textwrap
from pdb import Pdb
from bdb import Bdb, BdbQuit

from shared.tools.compat import next

from collections import deque


class StreamHistory():

	_MAX_HISTORY = 1000

	def __init__(self):
		self.history = deque(['#! Starting log...'])

	def log(self, string):
		self.history.append(string)
		while len(self.history) > self._MAX_HISTORY:
			_ = self.history.popleft()


class PatientInputStream(StringIO, StreamHistory):
	
	_SLEEP_RATE = 0.05 # seconds
	
	def __init__(self, *args, **kwargs):
		StringIO.__init__(self, *args, **kwargs)
		StreamHistory.__init__(self)
	
	def read(self, n=-1):
		while True:
			chunk = StringIO.read(n)
			if chunk:
				self.history.append('# %s' % chunk)
				return chunk
			else:
				sleep(self._SLEEP_RATE)

	def readline(self, length=None):
		while True:
			line = StringIO.readline(self, length)
			if line:
				self.history.append('>>> %s' % '... '.join(line.splitlines()))
				return line
			else:
				sleep(self._SLEEP_RATE)			
		
	def inject(self, string):
		current_pos = self.tell()
		self.write(string)
		self.pos = current_pos


class OutputStream(StringIO, StreamHistory):
	
	def __init__(self, *args, **kwargs):
		StringIO.__init__(self, *args, **kwargs)
		StreamHistory.__init__(self)
		
	def write(self, string):
		self.history.append(string)
		StringIO.write(self, string)

	def writelines(self, iterable):
		self.history.append(iterable)
		StringIO.writelines(self, iterable)


class ProxyIO(object):

	_SLEEP_RATE = 0.05 # seconds
	
	def __init__(self):
		self.log = lambda s: system.util.getLogger('proxy-io').info(str(s))
		
		self.stdin = PatientInputStream()
		self.stdout = OutputStream()
		self.stderr = OutputStream()
	
	@property
	def last_input(self):
		return self.stdin.history[-1]

	@property
	def last_output(self):
		return self.stdout.history[-1]

	@property
	def last_error(self):
		return self.stderr.history[-1]



class SysHijack(object):

	__slots__ = ('_thread_state', '_io_proxy', '_originals',
	             '_target_thread',)

	_BACKUP_ATTRIBUTES = ('stdin', 'stdout', 'stderr',)
	
	_FAILSAFE_TIMEOUT = 20
	
	def __init__(self, thread, stdio=None):
		self._target_thread = thread
		self._thread_state = getThreadState(self._target_thread)
		
		self._io_stream = stdio
		self._originals = {self._target_thread:{}}
		
		self._init_time = time()
		
		self._install()
		
		# @async(self._FAILSAFE_TIMEOUT)
		# def failsafe_uninstall(self=self):
		# 	self._restore()
		# failsafe_uninstall()
		
		
	def _install(self):
		for key in self._BACKUP_ATTRIBUTES:
			self._originals[self._target_thread][key] = getattr(self._thread_state.systemState, key)
			
			setattr(self._thread_state.systemState, 
				    key, 
				    getattr(self._io_stream,key) if self._io_stream else StringIO())
	
	def _restore(self):
		self._originals['last_session'] = {}
		for key in self._BACKUP_ATTRIBUTES:
			self._originals['last_session'][key] = getattr(self._thread_state.systemState, key)
			setattr(self._thread_state.systemState, key, self._originals[self._target_thread][key])
			
	
	def __getattr__(self, attribute):
		"""Get from this class first, otherwise use the wrapped item."""
		try:
			return super(SysHijack, self).__getattr__(attribute)
		except AttributeError:
			return getattr(self._thread_state.systemState, attribute)

	def __setattr__(self, attribute, value):
		"""Set to this class first, otherwise use the wrapped item."""
		try:
			return super(SysHijack, self).__setattr__(attribute, value)
		except AttributeError:
			return setattr(self._thread_state.systemState, attribute, value)


	def _getframe(self, depth=0):
		print >>self.stdout, '[~] getting frame %d' % depth
		frame = self._thread_state.frame
		while depth > 0 and frame:
			depth -= 1
			frame = frame.f_back
		return frame

	def settrace(self, tracefunc):
		print 'Setting trace function...'
		if tracefunc is None:
			self._thread_state.systemState.settrace(None)
#			self._thread_state.systemState.tracefunc = None
		else:
			self._thread_state.systemState.settrace(tracefunc)
#			self._thread_state.systemState.tracefunc = tracefunc

	def setprofile(self, profilefunc):
		if profilefunc is None:
			self._thread_state.systemState.setprofile(None)
#			self._thread_state.systemState.profilefunc = None
		else:
			self._thread_state.systemState.setprofile(profilefunc)
#			self._thread_state.systemState.profilefunc = profilefunc

	# def displayhook(self, obj):



class IgnitionPDB(Pdb):
	"""A variant of the Python Debugger (Pdb)
	
	This is designed to overcome and take advantage of the different
	  constraints that running Pdb in a multi-threaded environment
	  creates.
	  
	For more information and the cool implementation that we're tweaking here,
	  see also rpdb at https://github.com/tamentis/rpdb
	"""
		
	intro = 'PROTOTYPE Interactive Python debugger in Ignition'

	def __init__(self, thread=None):
		
		if not thread:
			raise RuntimeError("Prototype should not be run on main thread!")
			thread = Thread.currentThread()
		
		self.thread_state = getThreadState(thread)
		self.io_interface = ProxyIO()
		
		self.sys = SysHijack(thread, stdio=self.io_interface)
		
		# Pdb is not a new-style class, so we can't use super(...) here
		# Worse, the individual inits need fixing, so we'll jam them here

#		Pdb.__init__(self, 
#					 completekey='tab', 
#					 stdin=self.io_interface.stdin, 
#					 stdout=self.io_interface.stdout)
#
		Bdb.__init__(self) # skip is a glob-style pattern of things to skip jumping into
#		cmd.Cmd.__init__(self, completekey, stdin, stdout)
		
		#		"""Instantiate a line-oriented interpreter framework.
		#
		#		The optional argument 'completekey' is the readline name of a
		#		completion key; it defaults to the Tab key. If completekey is
		#		not None and the readline module is available, command completion
		#		is done automatically. The optional arguments stdin and stdout
		#		specify alternate input and output file objects; if not specified,
		#		sys.stdin and sys.stdout are used.
		#
		#		"""
		self.stdin = self.io_interface.stdin
		self.stdout = self.io_interface.stdout
		self.cmdqueue = []
		self.completekey = 'tab'
		
		# Finally, PDB's init. Pared down:		
		self.use_rawinput = 0
		
		self.prompt = '(Pdb) '
		self.aliases = {}
		self.mainpyfile = ''
		self._wait_for_mainpyfile = 0

		self.rcLines = []

		self.commands = {} # associates a command list to breakpoint numbers
		self.commands_doprompt = {} # for each bp num, tells if the prompt
									# must be disp. after execing the cmd list
		self.commands_silent = {} # for each bp num, tells if the stack trace
								  # must be disp. after execing the cmd list
		self.commands_defining = False # True while in the process of defining
									   # a command list
		self.commands_bnum = None # The breakpoint number for which we are
								  # defining a list



	def uninstall(self):
		self.sys._restore()
		self.sys.settrace(None)

	
	# Cleanly exit and catch Bdb quit exception

	def trace_dispatch(self, frame, event, arg):
		print >>self.stdout, 'Dispatching trace event %r' % event
		try:
			return Pdb.trace_dispatch(self, frame, event, arg)
		except BdbQuit:
			self.uninstall()
			return

	def do_continue(self, arg):
		"""Clean-up and do underlying continue."""
		try:
			return Pdb.do_continue(self, arg)
		except BdbQuit:
			pass
		finally:
			self.uninstall()

	do_c = do_cont = do_continue

	def do_quit(self, arg):
		"""Clean-up and do underlying quit."""
		try:
			return Pdb.do_quit(self, arg)
		except BdbQuit:
			pass
		finally:
			self.uninstall()

	do_q = do_exit = do_quit

	def do_EOF(self, arg):
		"""Clean-up and do underlying EOF."""
		try:
			return Pdb.do_EOF(self, arg)
		except BdbQuit:
			pass
		finally:
			self.uninstall()
			
			
	
	# Use the hijacked sys for the basic debugger (bdb)
	def set_trace(self, frame=None):
		"""Start debugging from `frame`.

		If frame is not specified, debugging starts from caller's frame.
		"""
		if frame is None:
			# This is called from outside the thread, so calling frame is actually correct.
			frame = self.sys._getframe()
			# frame = self.sys._getframe().f_back
		self.reset()
		while frame:
			frame.f_trace = self.trace_dispatch
			self.botframe = frame
			frame = frame.f_back
		self.set_step()
		self.sys.settrace(self.trace_dispatch)

	def set_continue(self):
		# Don't stop except at breakpoints or when finished
		self._set_stopinfo(self.botframe, None, -1)
		if not self.breaks:
			# no breakpoints; run without debugger overhead
			self.sys.settrace(None)
			frame = self.sys._getframe().f_back
			while frame and frame is not self.botframe:
				del frame.f_trace
				frame = frame.f_back

	def set_quit(self):
		self.stopframe = self.botframe
		self.returnframe = None
		self.quitting = 1
		self.sys.settrace(None)

	# The following two methods can be called by clients to use
	# a debugger to debug a statement, given as a string.

	def run(self, cmd, globals=None, locals=None):
		if globals is None:
			import __main__
			globals = __main__.__dict__
		if locals is None:
			locals = globals
		self.reset()
		self.sys.settrace(self.trace_dispatch)
		if not isinstance(cmd, types.CodeType):
			cmd = cmd+'\n'
		try:
			exec cmd in globals, locals
		except BdbQuit:
			pass
		finally:
			self.quitting = 1
			self.sys.settrace(None)

	def runeval(self, expr, globals=None, locals=None):
		if globals is None:
			import __main__
			globals = __main__.__dict__
		if locals is None:
			locals = globals
		self.reset()
		self.sys.settrace(self.trace_dispatch)
		if not isinstance(expr, types.CodeType):
			expr = expr+'\n'
		try:
			return eval(expr, globals, locals)
		except BdbQuit:
			pass
		finally:
			self.quitting = 1
			self.sys.settrace(None)

	def runctx(self, cmd, globals, locals):
		# B/W compatibility
		self.run(cmd, globals, locals)

	# This method is more useful to debug a single function call.

	def runcall(self, func, *args, **kwds):
		self.reset()
		self.sys.settrace(self.trace_dispatch)
		res = None
		try:
			res = func(*args, **kwds)
		except BdbQuit:
			pass
		finally:
			self.quitting = 1
			self.sys.settrace(None)
		return res



	# Use the hijacked sys for the Python wrapped debugger (pdb)
	# (ignoring sys.path and sys.argv)
	
	def default(self, line):
		if line[:1] == '!': line = line[1:]
		locals = self.curframe_locals
		globals = self.curframe.f_globals
		try:
			code = compile(line + '\n', '<stdin>', 'single')
			save_stdout = self.sys.stdout
			save_stdin = self.sys.stdin
			save_displayhook = self.sys.displayhook
			try:
				self.sys.stdin = self.stdin
				self.sys.stdout = self.stdout
				self.sys.displayhook = self.displayhook
				exec code in globals, locals
			finally:
				self.sys.stdout = save_stdout
				self.sys.stdin = save_stdin
				self.sys.displayhook = save_displayhook
		except:
			t, v = self.sys.exc_info()[:2]
			if type(t) == type(''):
				exc_type_name = t
			else: exc_type_name = t.__name__
			print >>self.stdout, '***', exc_type_name + ':', v


	def do_debug(self, arg):
		raise NotImplementedError("Recursive debugging not available in (this) Jython debugging setup.")
		# self.sys.settrace(None)
		# globals = self.curframe.f_globals
		# locals = self.curframe_locals
		# p = Pdb(self.completekey, self.stdin, self.stdout)
		# p.prompt = "(%s) " % self.prompt.strip()
		# print >>self.stdout, "ENTERING RECURSIVE DEBUGGER"
		# self.sys.call_tracing(p.run, (arg, globals, locals))
		# print >>self.stdout, "LEAVING RECURSIVE DEBUGGER"
		# self.sys.settrace(self.trace_dispatch)
		# self.lastcmd = p.lastcmd


	def _getval(self, arg):
		try:
			return eval(arg, self.curframe.f_globals,
						self.curframe_locals)
		except:
			t, v = self.sys.exc_info()[:2]
			if isinstance(t, str):
				exc_type_name = t
			else: exc_type_name = t.__name__
			print >>self.stdout, '***', exc_type_name + ':', repr(v)
			raise

	def do_whatis(self, arg):
		try:
			value = eval(arg, self.curframe.f_globals,
							self.curframe_locals)
		except:
			t, v = self.sys.exc_info()[:2]
			if type(t) == type(''):
				exc_type_name = t
			else: exc_type_name = t.__name__
			print >>self.stdout, '***', exc_type_name + ':', repr(v)
			return
		code = None
		# Is it a function?
		try: code = value.func_code
		except: pass
		if code:
			print >>self.stdout, 'Function', code.co_name
			return
		# Is it an instance method?
		try: code = value.im_func.func_code
		except: pass
		if code:
			print >>self.stdout, 'Method', code.co_name
			return
		# None of the above...
		print >>self.stdout, type(value)



















db = IgnitionPDB(running_thread)

#
#def nopTrace(frame, event, arg, testSys=db.sys):
#	log = lambda s: system.util.getLogger('failbug').info( str(s) )
#	log( 'Current tracefunc: %r' % testSys.tracefunc )
#	log( 'Event fired: %r' % event )
#	
#	db.sys.settrace(None)
#
#	log( 'After clear tracefunc: %r' % testSys.tracefunc )
#	
#	return
#	
#db.sys.settrace(nopTrace)
#






# THIS WORKS:
# from shared.tools.pretty import p,pdir

# from shared.tools.thread import async, findThreads, getThreadState, dangerouslyKillThreads
# from time import sleep

# from java.lang import Thread, ThreadGroup

# from shared.tools.global import ExtraGlobal


# thread_name = 'running-thread'

# dangerouslyKillThreads(thread_name, bypass_interlock='Yes, seriously.')
# stop = lambda: dangerouslyKillThreads(thread_name, bypass_interlock='Yes, seriously.')


# ExtraGlobal['debug'] = ''

# def debugPrinter(frame, event, arg):
# 	print '[%5d %s in %s] Event: %r with %r' % (frame.f_lineno, frame.f_code.co_filename, frame.f_code.co_name, event, arg)
	
# 	while not ExtraGlobal['debug']:
# 		sleep(0.05)
	
# 	if ExtraGlobal['debug'] == 'q':
# 		print 'Stopping debug...'
# 		raise KeyboardInterrupt
# 	else:
# 		print 'Echo: %r' % ExtraGlobal['debug']
	
# 	ExtraGlobal['debug'] = ''
	
# 	return debugPrinter


# def foo(x):
# 	x += 5
# 	return x
	

# @async(name=thread_name)
# def running():
	
# 	localsys = getThreadState(Thread.currentThread()).systemState
# #	localsys.setprofile(debugPrinter)
# 	localsys.settrace(debugPrinter)
	
# 	try:
# 		counting = 1
		
# 		while counting:
# 			#counting += 1
# 			counting = foo(counting)
# 			print 'Count: %d' % counting
# 			sleep(0.5)
			
# 	except KeyboardInterrupt:
# 		print 'Thread dying....'
# 		sleep(0.01)
		
# #		localsys.setprofile(None)
# 		localsys.settrace(None)
		
# running_thread = running()	



