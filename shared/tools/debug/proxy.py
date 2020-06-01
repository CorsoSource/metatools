"""
	Proxy lets us inspect the standard in/out/err for a thread.

	This is helpful when a thread is started in a context where it is difficult
	  to observe the I/O. For example, an async thread spun up on the gateway
	  will write directly to the wrapper log via print, which is extremely
	  inconvenient.

	The streams are also buffered, allowing us to review the I/O after the fact.
"""

from StringIO import StringIO
from collections import deque
from time import sleep
from datetime import datetime

try:
	from shared.tools.compat import next
except ImportError:
	pass


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


class StreamBuffer(object):
	__slots__ = ('history', 
				 '_target_io',
				 '_parent_proxy', 
				 '_buffer_line',
				 '__weakref__',
				)
	_MAX_HISTORY = 10000
	_BUFFER_CHUNK = 1000

	def __init__(self, target_io, parent_proxy=None):
		self._buffer_line = ''
		self.history = ['[%s] %s' % (str(datetime.now()), '#! Starting log...')]
		
		# Failsafe to drill past repeated inits
		while isinstance(target_io, StreamBuffer):
			target_io = target_io._target_io
					
		self._target_io = target_io
		self._parent_proxy = parent_proxy

		system.util.getLogger('StreamBuffer').debug(repr(self._target_io))

				
	@property
	def parent(self):
		return self._parent_proxy


	def write(self, string):
		self._target_io.write(string)
		
		buffer = self._buffer_line + string
		timestamp = str(datetime.now())
		ix = 0
		while '\n' in buffer:
			line, _, buffer = buffer.partition('\n')
			self.history.append('[%s] %s' % (timestamp, line))
		self._buffer_line = buffer
		

	def writelines(self, iterable):
		self._target_io.writelines(iterable)
		
		timestamp = str(datetime.now())
		for ix, line in enumerate(iterable):
			if ix == 0:
				line = self._buffer_line + line
				self._buffer_line = ''
			self.history.append('[%s %d] %s' % (timestamp, ix, line))


	def __getattr__(self, attribute):
		"""Get from this class first, otherwise use the wrapped item."""
		try:
			return super(StreamBuffer, self).__getattr__(attribute)
		except AttributeError:
			return getattr(self._target_io, attribute)

	def __setattr__(self, attribute, value):
		"""Set to this class first, otherwise use the wrapped item."""
		try:
			return super(StreamBuffer, self).__setattr__(attribute, value)
		except AttributeError:
			return setattr(self._target_io, attribute, value)


class ProxyIO(object):
	"""Control the I/O"""
	
	__slots__ = ('_stdin', '_stdout', '_stderr', '_displayhook', 
				 '_original_displayhook',
				 '_hijacked_sys', '_installed')
	
	def __init__(self, hijacked_sys=None):
		self._installed = False

		self._original_displayhook = None
		self._stdin       = None
		self._stdout      = None
		self._stderr      = None
		self._displayhook = None

		self._hijacked_sys = hijacked_sys
	

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
	
	@property
	def _coupled_sys(self):
		return self._hijacked_sys._thread_sys
	

	def install(self):
		self._original_displayhook = self._coupled_sys.displayhook
		self._displayhook = self._original_displayhook # shared.tools.pretty.displayhook

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
