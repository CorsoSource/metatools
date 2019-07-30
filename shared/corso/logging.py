"""
	Make logging easier!
"""

try:
	from com.inductiveautomation.factorypmi.application import FPMIWindow
	from com.inductiveautomation.factorypmi.application.components.template import TemplateHolder
except ImportError:
	pass # only needed for when the logger's running on a Vision client; gateway won't have this in scope.

import sys, re
from shared.corso.meta import getObjectByName, GLOBAL_MESSAGE_PROJECT_NAME


VISION_CLIENT_MESSAGE_HANDLER = 'Vision Client Log'


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


class PrintLogger(object):
	"""The most basic logger."""
	@staticmethod
	def trace(message):
		print '[%s] %s' % ('trace', message)
	@staticmethod	
	def debug(message):
		print '[%s] %s' % ('debug', message)
	@staticmethod	
	def info(message):
		print '[%s] %s' % ('info', message)
	@staticmethod	
	def warn(message):
		print '[%s] %s' % ('warn', message)
	@staticmethod	
	def error(message):
		print '[%s] %s' % ('error', message)	


class Logger(BaseLogger):

	_stackDepth = 4
		
	def __init__(self, loggerName=None, prefix=None, suffix=None, relay=True):
		#raise NotImplementedError('This is under development and is not fully functional yet.')
		
		self.relay = relay
		
		self._autoConfigure(loggerName)
		
		if prefix is not None: self.prefix = '%s%s' % (prefix, self.prefix)
		if suffix is not None: self.suffix = '%s%s' % (self.suffix, suffix)
				
	def _getScope(self):
		frame = sys._getframe(self._stackDepth - 1)
		return frame.f_code.co_filename
	
	def _autoConfigure(self, loggerName=None):
		scope = self._getScope()[1:-1] # remove the angle brackets
		self.prefix = ''
		self.suffix = ''
		
		# Playground!
		if scope == 'buffer':
			self.loggerName = loggerName or 'Script Console'
			self.logger = PrintLogger()
			self.relay = False
		# Scripts!
		elif scope.startswith('module:'):
			self.loggerName = loggerName or scope[7:]
			self.logger = system.util.getLogger(self.loggerName)
		# Tags!
		elif scope.startswith('tagevent:'):
			tagPath = getObjectByName('tagPath')
			provider,_,tagPath = tagPath[1:].partition(']')
			self.loggerName = loggerName or '[%s] Tag %s Event' % (provider, scope[9:])
			self.prefix = '{%s} ' % tagPath
			self.logger = system.util.getLogger(self.loggerName)
		# Clients!
		elif scope.startswith('event:') and self._isVisionScope(): 
			self.loggerName = '%s %s' % ('Designer' if self._isVisionDesigner() else 'Client', system.util.getClientId())
			self.logger = system.util.getLogger(self.loggerName)
			
			event = getObjectByName('event', mostDeep=True)
			window = system.gui.getParentWindow(event)
			component = event.source
			
			componentPath = []
			while not isinstance(component, FPMIWindow):
				label = component.name
				if isinstance(component, TemplateHolder):
					label = '<%s>' % component.templatePath
				componentPath.append(label)
				component = component.parent
			self.prefix = '[%s: %s.%s] ' % (window.path, '/'.join(reversed(componentPath[:-3])), scope[6:])
			if self.relay:
				self.relayScope = {'scope': 'G'}
				self.relayHandler = VISION_CLIENT_MESSAGE_HANDLER
				self.relayProject = GLOBAL_MESSAGE_PROJECT_NAME or system.util.getProjectName()
	
	@staticmethod
	def _isVisionScope():
		sysFlags = system.util.getSystemFlags()
		return sysFlags & system.util.DESIGNER_FLAG or sysFlags & system.util.CLIENT_FLAG
	@staticmethod
	def _isVisionDesigner():
		return system.util.getSystemFlags() & system.util.DESIGNER_FLAG
	@staticmethod
	def _isVisionClient():
		return system.util.getSystemFlags() & system.util.CLIENT_FLAG
		
		
	def _relayMessage(self, level, message):
		if not self.relay: return
		
		payload = {'logLevel': level, 'message': message, 'loggerName': self.loggerName}
		results = system.util.sendMessage(self.relayProject, self.relayHandler, payload, **self.relayScope)
		if not results: # sure hope someone sees this...
			print "WARNING: Logger message handler not found!" 
	
	def _log(self, level, *args, **kwargs):
		message = self._generateMessage(*args, **kwargs)
		getattr(self.logger, level)(message)
		if self.relay:
			self._relayMessage(level, message)
	
	
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


	_messagePayloadKeys = set(['message', 'logLevel', 'loggerName'])
	@classmethod
	def messageHandler(cls, payload):
		"""This is the relay handler. Place this in a gateway message event script:	
		from shared.corso.logging import Logger
		Logger.messageHandler(payload)
		"""
		payloadKeys = set(payload.keys())
		assert payloadKeys.issuperset(cls._messagePayloadKeys), 'Missing message payload key(s): %s' % cls._messagePayloadKeys.difference(payloadKeys)
		
		message = payload['message']
		logLevel = payload['logLevel']
		loggerName = payload['loggerName']
		
		getattr(system.util.getLogger(loggerName), logLevel)(message)