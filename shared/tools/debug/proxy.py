from StringIO import StringIO
from collections import deque
from time import sleep


class ProxyStream(object):
	"""I/O stream mixin to add history"""

	__slots__ = ('history', '_parent_proxyio')
	_MAX_HISTORY = 1000

	def __init__(self, parent_proxyio=None):
		self.history = deque(['#! Starting log...'])
		self._parent_proxyio = parent_proxyio

	def log(self, string):
		self.history.append(string)
		while len(self.history) > self._MAX_HISTORY:
			_ = self.history.popleft()

	@property
	def parent(self):
		return self._parent


class PatientInputStream(StringIO, ProxyStream):
	
	_SLEEP_RATE = 0.05 # seconds
	
	def __init__(self, buffer='', parent_proxyio=None):
		StringIO.__init__(self, buffer)
		ProxyStream.__init__(self, parent_proxyio)
	
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


class OutputStream(StringIO, ProxyStream):
	
	def __init__(self, buffer='', parent_proxyio=None):
		StringIO.__init__(self, buffer)
		ProxyStream.__init__(self, parent_proxyio)
		
	def write(self, string):
		if string != '\n':
			self.history.append(string)
		StringIO.write(self, string)

	def writelines(self, iterable):
		self.history.append(iterable)
		StringIO.writelines(self, iterable)


class ProxyIO(object):
	"""Control the I/O"""
	
	__slots__ = ('stdin', 'stdout', 'stderr', 'displayhook', '_logger_name', '_coupled_sys')
	
	def __init__(self, coupled_sys=None):
		self._logger_name = 'proxy-io'
		
		self._coupled_sys = coupled_sys
		
		self.stdin = PatientInputStream(parent_proxyio=self)
		self.stdout = OutputStream(parent_proxyio=self)
		self.stderr = OutputStream(parent_proxyio=self)
		self.displayhook = shared.tools.pretty.displayhook
	
	def log(self, s):
		system.util.getLogger(self._logger_name).info(str(s))
	
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


