"""
	Make logging easier!
"""


from functools import wraps, partial
from shared.corso.meta import p,pdir


def add_log_levels(levels):
	"""Adds levels to the logger.
	
	Mea culpa: this was originally to make the code more streamlined and simpler. You don't need to copy/paste as much!
	  That's a good goal right? Road to hell is paved with good intentions, it seems. Let me show you why this
	  nonsense exists.
	  
	  The idea seems straight forward: generate a function for each level, wrapping the `_log` function in the class
	  and adding it to the class. A straightforward bound method for the class. A few notes:
	   - I'm using `setattr` here because `functools.partial` doesn't have a `__get__` method, which means it
	     does _not_ bind to the class.
	   - I'm using two lambdas in a row. The first is essentially the closure, and the second is what I expected to work.
	   - Closures bind late! That means that without that apparently redundant closure, all the generated lambdas
	     will essentially point to the same value! By the time the loop ends and the stuff all returns, and eventually
	     we get around to calling the new logging function (let's call it `info`), we find that `level` now has the
	     last value from the loop, //since it's the same reference//!
	"""
	# The decorator function for the class - auto fills in some additional function calls for convenience.
	def loggerUpdater(cls):
		for level in levels:
			# Force an early binding on `level` onto `loglevel`. We do that by forcing the inner lambda to have 
			#  a scope that references the outer lambda's scope, and we force the early binding 
			#  by defaulting the value. That means that the inner lambda sees the default value for loglevel, 
			#  which is the expected one.
			_genLogLevel = lambda loglevel=level: lambda self, *args, **kwargs: self._log(loglevel, *args, **kwargs)
			setattr(cls, level, _genLogLevel())
		return cls
		
	return loggerUpdater


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


@add_log_levels(['trace', 'debug', 'info', 'warn', 'error'])
class ConsoleLogger(BaseLogger):
	
	def _log(self, level, *args, **kwargs):
		message = self._generateMessage(*args, **kwargs)
		print '[%s] %s' % (level, message)