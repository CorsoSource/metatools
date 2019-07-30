"""
	Make logging easier!
"""


import sys, re


def autoRepr(obj):
	"""Cleans up repr() calls, since the string representation add quotes."""
	return obj if isinstance(obj, (str,unicode)) else repr(obj)


class BaseLogger(object):
	"""A logger with extra features. This is a base class to be expanded on depending on the destination.
	Notably, it will inject values from the calling scope to fill in its messages.
		Essentially, messages are built from the arguments (args)
		and filled in with values from keyword arguments (kwargs)
	"""
	
	argsSeparator = ' ' # to allow for print-style argument concatenation
	_stackDepth = 3
	
	def bracketString(self, message):
		prefix = getattr(self, 'prefix', '')
		suffix = getattr(self, 'suffix', '')
		return '%s%s%s' % (prefix, message, suffix)

	def formatString(self, message, *args, **kwargs):
		"""Looks back on the stack and injects values in the calling scope.
		
		For example, this allows the following to work:
		
		def foo(x):
			y = 4
			BaseLogger()._log('asdf %(y)s %(x)r %(foo)r')	
		foo(11)
		>>> [info] ('asdf 4 11 <function foo at 0xc>',)
		"""
		## Add positional arguments to the interpolation
		#for i,arg in enumerate(args):
		#	kwargs[str(i)] = arg
		frame = sys._getframe(self._stackDepth)
		varScope = dict(frame.f_globals.items() + frame.f_locals.items() + kwargs.items())
		
		return message % varScope
	
	def _generateMessage(self, *args, **kwargs):
		"""Given arguments and some specific values generate the message.
		For example: BaseLogger()._log('asdf', 3, '%(qwer)r', qwer=45)
		>>> asdf 3 45
		"""
		message = self.argsSeparator.join(autoRepr(arg) for arg in args)
		message = self.bracketString(message)
		message = self.formatString(message, *args, **kwargs)
		return message
			
	def _log(self, *args, **kwargs):
		message = self._generateMessage(*args, **kwargs)
		print message


class ConsoleLogger(BaseLogger):
	
	_stackDepth = 4
	
	def _log(self, level, *args, **kwargs):
		message = self._generateMessage(*args, **kwargs)
		print '[%s] %s' % (level, message)
	
	
	def trace(self, *args, **kwargs):
		self._log('trace', *args, **kwargs)
		
	def debug(self, *args, **kwargs):
		self._log('debug', *args, **kwargs)
		
	def info(self, *args, **kwargs):
		self._log('info', *args, **kwargs)
		
	def warn(self, *args, **kwargs):
		self._log('warn', *args, **kwargs)
		
	def error(self, *args, **kwargs):
		self._log('error', *args, **kwargs)
		