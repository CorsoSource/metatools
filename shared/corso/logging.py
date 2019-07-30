"""
	Make logging easier!
"""


from functools import wraps, partial
from shared.corso.meta import p,pdir


def autoRepr(obj):
	return obj if isinstance(obj, (str,unicode)) else repr(obj)


class BaseLogger(object):
	
	def processArgs(self, *args, **kwargs):
		output = ''
		if args: output += autoRepr(args)
		if kwargs: output += autoRepr(kwargs) 
		return output
		
	def bracketString(self, message):
		prefix = getattr(self, 'prefix', '')
		suffix = getattr(self, 'suffix', '')
		return '%s%s%s' % (prefix, message, suffix)
		
	def formatString(self, message, **kwargs):
		return message % kwargs
	
	def _generateMessage(self, *args, **kwargs):
		message = self.processArgs(*args, **kwargs)
		message = self.bracketString(message)
		message = self.formatString(message, **kwargs)
		return message
			
	def _log(self, level, *args, **kwargs):
		message = self._generateMessage(*args, **kwargs)
		print message


class ConsoleLogger(BaseLogger):
	
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
		