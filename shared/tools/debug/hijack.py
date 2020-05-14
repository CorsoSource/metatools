from shared.tools.thread import getThreadState, Thread

from shared.tools.debug.proxy import ProxyIO


class SysHijack(object):
	"""Capture a thread's system state and redirect it's standard I/O."""

	__slots__ = (
				 '_target_thread', 
				 '_io_proxy',
	             )
		
	def __init__(self, thread):
		self._target_thread = thread
		self._io_proxy = ProxyIO(hijacked_sys=self)
		self._install()
		
		
	def _install(self):
		"""Redirect all I/O to proxy's endpoints"""
		self._io_proxy.install()
			
	def _restore(self):
		"""Restore all I/O to original's endpoints"""
		self._io_proxy.uninstall()
		

	@property
	def _thread_state(self):
		return getThreadState(self._target_thread)
	
	@property
	def _thread_sys(self):
		return self._thread_state.systemState
	

	# I/O proxy redirection
	# NOTE: This will not play well with other things attempting to hijack I/O
	#       I think this is fair - only one bully per playground

	@property
	def stdin(self):
		if self._io_proxy.installed:
			return self._io_proxy.stdin
		else:
			return self._thread_sys.stdin
	@property
	def stdout(self):
		if self._io_proxy.installed:
			return self._io_proxy.stdout
		else:
			return self._thread_sys.stdout
	@property
	def stderr(self):
		if self._io_proxy.installed:
			return self._io_proxy.stderr
		else:
			return self._thread_sys.stderr
	@property
	def displayhook(self):
		if self._io_proxy.installed:
			return self._io_proxy.displayhook
		else:
			return self._thread_sys.displayhook
			

	def _getframe(self, depth=0):
		#print >>self.stdout, '[~] getting frame %d' % depth
		frame = self._thread_state.frame
		while depth > 0 and frame:
			depth -= 1
			frame = frame.f_back
		return frame


	def settrace(self, tracefunc=None):
		self._thread_sys.settrace(tracefunc)


	def setprofile(self, profilefunc=None):
		self._thread_sys.setprofile(None)


	# Context management

	def __enter__(self):
		self._install()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self._restore()

	def __del__(self):
		self._restore()
	

	# Override masking mechanic (the hijack)
	
	def __getattr__(self, attribute):
		"""Get from this class first, otherwise use the wrapped item."""
		try:
			return super(SysHijack, self).__getattr__(attribute)
		except AttributeError:
			return getattr(self._thread_sys, attribute)
	
	
	def __setattr__(self, attribute, value):
		"""Set to this class first, otherwise use the wrapped item."""
		try:
			super(SysHijack, self).__setattr__(attribute, value)
		except AttributeError:
			setattr(self._thread_sys, attribute, value)
