from StringIO import StringIO
from collections import deque
from time import sleep
from datetime import datetime


class StreamBuffer(object):
	__slots__ = ('history', 
				 '_target_io',
				 '_parent_proxy', 
				 '_cursors'
				)
	_MAX_HISTORY = 10000
	_BUFFER_CHUNK = 1000

	def __init__(self, target_io, parent_proxy=None):
		self.history = []
		self.log_entry(self.__init__, '#! Starting log...')
		
		self._target_io = target_io
		self._parent_proxy = parent_proxy


	@property
	def parent(self):
		return self._parent_proxy


	def log_entry(self, target, string):
		self.history.append((datetime.now(), string))

		if len(self.history) > self._MAX_HISTORY:
			self.history = self.history[-(self._MAX_HISTORY - self._BUFFER_CHUNK):]


	def write(self, string):
		self._target_io.write(self, string)
		self.log_entry(self.write, string)

	def writelines(self, iterable):
		self._target_io.writelines(self, iterable)
		self.log_entry(self.writelines, iterable)



class ProxyIO(object):
	"""Control the I/O"""
	
	__slots__ = ('_stdin', '_stdout', '_stderr', '_displayhook', 
				 '_original_displayhook',
				 '_coupled_sys', '_installed')
	
	def __init__(self, coupled_sys=None):
		self._installed = False

		self._original_displayhook = None
		self._stdin       = None
		self._stdout      = None
		self._stderr      = None
		self._displayhook = None

		self._coupled_sys = coupled_sys
	

	@property
	def installed(self):
		return self._installed	

	@property
	def coupled_sys(self):
		return self._coupled_sys
		
	@property
	def last_input(self):
		return self.stdin.history[-1]
	@property
	def last_output(self):
		return self.stdout.history[-1]
	@property
	def last_error(self):
		return self.stderr.history[-1]


	@property
	def stdin(self):
		return self._stdin
	
	@property
	def stdout(self):
		return self._stdout
	
	@property
	def stderr(self):
		return self._stderr
	
	@property
	def displayhook(self):
		return self._displayhook
	

	def install(self):
		self._original_displayhook = self._coupled_sys.displayhook
		self._displayhook = shared.tools.pretty.displayhook

		self._stdin  = StreamBuffer(self._coupled_sys.stdin,  parent_proxy=self)
		self._stdout = StreamBuffer(self._coupled_sys.stdout, parent_proxy=self)
		self._stderr = StreamBuffer(self._coupled_sys.stderr, parent_proxy=self)
		
		self._coupled_sys.stdin       = self.stdin
		self._coupled_sys.stdout      = self.stdout
		self._coupled_sys.stderr      = self.stderr
		self._coupled_sys.displayhook = self.displayhook
		
		self._installed = True


	def uninstall(self):
		if not self._installed:
			return

		self._coupled_sys.stdin       = self._stdin._target_io
		self._coupled_sys.stdout      = self._stdout._target_io
		self._coupled_sys.stderr      = self._stderr._target_io
		self._coupled_sys.displayhook = self._original_displayhook

		self._installed = False


	# Context management

	def __enter__(self):
		self.install()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.uninstall()

	def __del__(self):
		"""NOTE: This is NOT guaranteed to run, but it's a mild safeguard."""
		self.uninstall()

