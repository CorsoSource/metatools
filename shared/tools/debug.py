from shared.tools.thread import async, findThreads, getThreadState, dangerouslyKillThreads
from time import sleep


thread_name = 'running-thread'

dangerouslyKillThreads(thread_name, )

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

from java.lang import Thread, ThreadGroup
from jarray import array, zeros
from org.python.core import ThreadState, Py
from org.python.core import PythonTraceFunction

from StringIO import StringIO

from time import time

import sys
import re, math, textwrap
from pdb import Pdb



class ProxyIO(object):

	_SLEEP_RATE = 0.05 # seconds
	
	def __init__(self):
		self.log = lambda s: system.util.getLogger('proxy-io').info(str(s))
		self.buffer_raw_out = ''
		self.buffer_in = []
		self.history = []
		
		
	def write(self, string=''):
		self.buffer_raw_out += string
		
		while string:
			
			newline, _, string = self.buffer_raw_out.partition('\n')
			print 'looooooop'
			print newline
			print string
			if string:
				self.log(newline)
				self.history.append(newline)
			else:
				self.buffer_raw_out = newline
	
	def flush(self):
		self.write()
		if self.buffer_raw_out:
			self.log(self.buffer_raw_out)
			self.buffer_raw_out = ''
		
		
	def readline(self):
		
		while True:

			if self.buffer_in:
				line = self.buffer_in.pop(0)
				self.history.append('>>> %s' % '... '.join(line.splitlines()))
				return line + '\n'
				
			else:
				sleep(self._SLEEP_RATE)



class SysHijack(object):

	__slots__ = ('_thread_state', '_io_proxy', '_originals',
	             '_source_thread', '_target_thread',)

	_BACKUP_ATTRIBUTES = ('stdin', 'stdout', 'stderr',)
	
	_FAILSAFE_TIMEOUT = 20
	
	def __init__(self, thread):
		self._source_thread = Thread.currentThread()
		self._target_thread = thread
		self._thread_state = getThreadState(self._target_thread)
		self._originals = dict((t,{}) for t in (self._source_thread, self._target_thread))
		
		self._init_time = time()
		
		self._install()
		
		@async(self._FAILSAFE_TIMEOUT)
		def failsafe_uninstall(self=self):
			self._restore()
		failsafe_uninstall()
		
		
	def _install(self):
		for key in self._BACKUP_ATTRIBUTES:
			self._originals[self._source_thread][key] = getattr(sys, key)
			self._originals[self._target_thread][key] = getattr(self._thread_state.systemState, key)
			
			setattr(self._thread_state.systemState, key, getattr(sys, key))
			setattr(sys, key, StringIO())
#			getattr(self._thread_state.systemState, key)
#			setattr(self._thread_state.systemState, key, StringIO())
	
	def _restore(self):
		for key in self._BACKUP_ATTRIBUTES:
			setattr(self._thread_state.systemState, key, self._originals[self._target_thread][key])
			setattr(sys,                            key, self._originals[self._source_thread][key])
			
	
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
		print '[~] getting frame %d' % depth
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
		
		self.sys = SysHijack(thread)
		
		self.install()
		
		# Pdb is not a new-style class, so we can't use super(...) here
		Pdb.__init__(self, 
					 completekey='tab', 
					 stdin=self.io_interface, 
					 stdout=self.io_interface)

	def install(self):
		pass

	def uninstall(self):
		self.sys._restore()


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

	
	# Cleanly exit and catch Bdb quit exception

	def trace_dispatch(self, frame, event, arg):
		print 'Dispatching trace event %r' % event
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





