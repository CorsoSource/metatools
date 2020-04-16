"""
	Make logging easier!
"""


try:
	from com.inductiveautomation.factorypmi.application import FPMIWindow
	from com.inductiveautomation.factorypmi.application.components.template import TemplateHolder
except ImportError:
	pass # only needed for when the logger's running on a Vision client; gateway won't have this in scope.

import sys, re
from shared.tools.meta import currentStackDepth, getObjectByName, GLOBAL_MESSAGE_PROJECT_NAME


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


VISION_CLIENT_MESSAGE_HANDLER = 'Vision Client Log'
PERSPECTIVE_SESSION_MESSAGE_HANDLER = 'Perspective Log Relay'


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
	# (0) <calling scope> > (1) self.log > (2) self._log > (3) self._generateMessage > (4) self._formatString
	_stackDepth = 4
	
	def _bracketString(self, message):
		"""Applies a prefix and suffix to the message (if any available).
		Missing values are assumed to be empty string.
		>>> baseLogger = BaseLogger()
		>>> baseLogger.prefix = '[log] '
		>>> baseLogger._bracketString('This is a log message.')
		'[log] This is a log message.'
		"""
		prefix = getattr(self, 'prefix', '')
		suffix = getattr(self, 'suffix', '')
		return '%s%s%s' % (prefix, message, suffix)

	def _formatString(self, message, *args, **kwargs):
		"""Looks back on the stack and injects values in the calling scope.
		Note that this is dead reckoning
		>>> def foo(x):
		...   y = 4
		...   BaseLogger().log('asdf %(y)s %(x)r %(foo)r')	
		>>> foo(11)
		asdf 4 11 <function foo at ...>
		"""
		## Add positional arguments to the interpolation
		#for i,arg in enumerate(args):
		#	kwargs[str(i)] = arg
		frame = sys._getframe(self._stackDepth)
		varScope = dict(frame.f_globals.items() + frame.f_locals.items() + kwargs.items())
		
		return message % varScope
	
	def _generateMessage(self, *args, **kwargs):
		"""Given arguments and some specific values generate the message.
		
		>>> z = 'zxcv'
		>>> BaseLogger().log('asdf %(z)s', 3, '%(qwer)r', qwer=45)
		asdf zxcv 3 45
		"""
		message = self.argsSeparator.join(autoRepr(arg) for arg in args)
		message = self._bracketString(message)
		message = self._formatString(message, *args, **kwargs)
		return message
			
	def _log(self, *args, **kwargs):
		"""A wrapper to ensure the call stack depth is consistent."""
		message = self._generateMessage(*args, **kwargs)
		print message

	def log(self, *args, **kwargs):
		"""Logs a message.
		The args are concatenated strings (like print), and the kwargs 
		  are used to fill in string interpolation references.
		"""
		self._log(*args, **kwargs)


class ConsoleLogger(BaseLogger):
	"""A basic logger that prints log messages.
	This exposes the more sophisticated message formatting utilities.
	"""	
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
	"""The most basic logger. 
	Essentially, this just a printer, but it interfaces like a logger.
	"""
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
	"""Autoconfiguring logger. This detects its calling environment and tries to set itself up.
	"""		
	def __init__(self, loggerName=None, prefix=None, suffix=None, relay=False):
		#raise NotImplementedError('This is under development and is not fully functional yet.')
		
		self.relay = relay
		
		self._autoConfigure(loggerName)
		
		if prefix is not None: self.prefix = '%s%s' % (prefix, self.prefix)
		if suffix is not None: self.suffix = '%s%s' % (self.suffix, suffix)
				
				
	def _getScope(self):
		frame = sys._getframe(self._stackDepth - 1) 
		return frame.f_code.co_filename
	
	
	def _generatePerspectiveComponentPath(self, scope, component=None):
		# parsed as example in 'function: onActionPerformed' or 'custom-method someFunction'
		functionName = scope.partition(':')[2] if ':' in scope else scope.partition(' ')[2]
		
		try:
			if not component:
				component = getObjectByName('self', startRecent=False)
			assert 'com.inductiveautomation.perspective' in str(type(component)), 'Incorrectly detected Perspective context'
			session = component.session
			page = component.page
			view = component.view
			componentPath = []
			while component:
				componentPath.append(component.name)
				component = component.parent
				
			return '[%s - %s.%s] ' % (view.id, '/'.join(reversed(componentPath)), functionName)
		except AssertionError:
			return '[%s] ' % scope
			
	
	def _generateVisionComponentPath(self, scope, event=None, component=None):
		
		try:
			functionName = scope.partition(':')[2] if ':' in scope else scope.partition(' ')[2]
			
			if not event:
				event = getObjectByName('event', startRecent=False)
				window = system.gui.getParentWindow(event)
			if not component:
				component = event.source
	
			componentPath = []
			while not isinstance(component, FPMIWindow):
				label = component.name
				if isinstance(component, TemplateHolder):
					label = '<%s>' % component.templatePath
				componentPath.append(label)
				component = component.parent
						
			return '[%s: %s.%s] ' % (window.path, '/'.join(reversed(componentPath[:-3])), functionName)
	
		except AttributeError:
			return '[%s] ' % scope

				
	def _autoConfigure(self, loggerName=None):
		"""The master configuration routine. This will branch down and check if a known state is set.
		If so, it will try to name itself something appropriate, with a focus on making gateway logs
		  easier to filter for the specific situation getting logged.
		Additional information may be bolted on via the prefix/suffix to provide context.
		"""
		scope = self._getScope()[1:-1] # remove the angle brackets
		self.prefix = ''
		self.suffix = ''
		
		# Playground!
		if scope == 'buffer':
			self.loggerName = loggerName or 'Script Console'
			self.logger = PrintLogger()
		# Scripts!
		elif scope.startswith('module:'):
			self.loggerName = loggerName or scope[7:]
			self.logger = system.util.getLogger(self.loggerName)
			if self._isVisionDesigner() or self._isVisionClient():
				self._configureVisionClientRelay()			
				self.prefix = self._generateVisionComponentPath(scope)
				self.suffix = ' [Vision %s]' % self._getVisionClientID()
			elif self._isPerspective():
				self.prefix = self._generatePerspectiveComponentPath(scope)
				self.suffix = ' [%s]' % self._getPerspectiveClientID()
		# Tags!
		elif scope.startswith('tagevent:'):
			tagPath = getObjectByName('tagPath')
			provider,_,tagPath = tagPath[1:].partition(']')
			self.loggerName = loggerName or '[%s] Tag %s Event' % (provider, scope[9:])
			self.prefix = '{%s} ' % tagPath
			self.logger = system.util.getLogger(self.loggerName)
			if provider == 'client':
				self._configureVisionClientRelay()			
		# Perspective!
		elif self._isPerspective():
			self.loggerName = self._getPerspectiveClientID()
			self.logger = system.util.getLogger(self.loggerName)
			
			self.prefix = self._generatePerspectiveComponentPath(scope)
			self.relay = False # NotImplementedError
			# if self.relay:
			# 	self.relayScope = {'scope': 'C', 'hostName': session.props.host}
			# 	self.relayHandler = PERSPECTIVE_SESSION_MESSAGE_HANDLER
			# 	self.relayProject = GLOBAL_MESSAGE_PROJECT_NAME or system.util.getProjectName()
		# Clients!
		elif self._isVisionScope(): 
			self.loggerName = self._getVisionClientID()
			self.logger = system.util.getLogger(self.loggerName)
			
			self.prefix = self._generateVisionComponentPath(scope)
			self._configureVisionClientRelay()
		# WebDev endpoint!
		elif self._isWebDev():
			self.loggerName = loggerName or '[%s] WebDev' % system.util.getProjectName()
			self.logger = system.util.getLogger(self.loggerName)
			endpoint,_,eventName = scope.rpartition(':')
			self.prefix = '[%s %s] ' % (eventName[2:].upper(), '/'.join(endpoint.split('/')[1:]))
		else:
			self.loggerName = loggerName or 'Logger'
			self.logger = system.util.getLogger(self.loggerName)

			
	@staticmethod
	def _isVisionScope():
		"""Returns True if the system flags imply this is a designer or client. 
		(Gateway will throw an AttributeError, since system.util.getSystemFlags is out of scope for it.) 
		"""
		if getattr(system.util, 'getSystemFlags', None):
			sysFlags = system.util.getSystemFlags()
			return sysFlags & system.util.DESIGNER_FLAG or sysFlags & system.util.CLIENT_FLAG
		return False

	@staticmethod
	def _isVisionDesigner():
		if getattr(system.util, 'getSystemFlags', None):
			return system.util.getSystemFlags() & system.util.DESIGNER_FLAG
		return False
	
	@staticmethod
	def _isVisionClient():
		if getattr(system.util, 'getSystemFlags', None):
			return system.util.getSystemFlags() & system.util.CLIENT_FLAG
		return False
			
	@classmethod
	def _getVisionClientID(cls):
		return '%s %s' % ('Designer' if cls._isVisionDesigner() else 'Client', system.util.getClientId())
	
	@classmethod
	def _getPerspectiveClientID(cls):
		#session = getObjectByName('session', startRecent=False)
		try:
			return 'Perspective %s' % session.props.id
		except NameError:
			return 'Perspective on %s' % (system.tag.read('[System]Client/Network/IPAddress').value)

	def _configureVisionClientRelay(self):
		self.relay = True
		self.relayScope = {'scope': 'G'}
		self.relayHandler = VISION_CLIENT_MESSAGE_HANDLER
		self.relayProject = GLOBAL_MESSAGE_PROJECT_NAME or system.util.getProjectName()
	
	@staticmethod
	def _isPerspective():
		"""Returns True when we simply have access to Perspective module stuff."""
		return 'perspective' in dir(system)
	
	_webDevFunctions = set(['doGet','doPost','doPut','doDelete','doHead','doOptions','doTrace'])
	@classmethod
	def _isWebDev(cls):
		rootFrame = sys._getframe(currentStackDepth()-1)
		expectedInitialVars = set(['request','session']).intersection(rootFrame.f_locals)
		expectedFunction = cls._webDevFunctions.intersection(rootFrame.f_globals)
		return expectedInitialVars and expectedFunction
	
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


	_messagePayloadKeys = set(['message', 'level', 'loggerName'])
	_logLevels = ['trace', 'debug', 'info', 'warn', 'error', 'log']

	@classmethod
	def _validatePayload(cls, payload):
		"""Make sure the log payload is sane."""
		payloadKeys = set(payload.keys())
		assert payloadKeys.issuperset(cls._messagePayloadKeys), 'Missing message payload key(s): %s' % cls._messagePayloadKeys.difference(payloadKeys)
		assert payload['level'] in cls._logLevels, 'Log levels must be one of: %r (not %s)' % (cls._logLevels, level)
		assert payload['message'], 'Log messages should not be blank. Really now.'
		assert payload['loggerName'], "Logger needs a name. Don't leave messages with no filterable context."

	def _relayMessage(self, level, message):
		"""Some logging contexts do not output to a convenient location for remote troubleshooting.
		Adding a relay helps simplify this. For example, with a relay vision clients can emit logs
		  that show on the gateway (similar in effect to how Perspective does).
		Be sure to place the Logger.messageHandler(payload) script in the gateway.
		"""
		if not self.relay: return
		
		payload = {'level': level, 'message': message, 'loggerName': self.loggerName}
		self._validatePayload(payload)

		results = system.util.sendMessage(self.relayProject, self.relayHandler, payload, **self.relayScope)
		if not results: # sure hope someone sees this...
			print "WARNING: Logger message handler not found!" 

	@classmethod
	def messageHandler(cls, payload):
		"""This is the relay handler. Note that by this should be placed in a message handler
		  that matches whatever is in self.relayHandler (typically VISION_CLIENT_MESSAGE_HANDLER). 

		Copy and paste the following directly into a gateway message event script:	
		
		from shared.tools.logging import Logger
		Logger.messageHandler(payload)
		"""
		cls._validatePayload(payload)
		
		message = payload['message']
		level = payload['level']
		loggerName = payload['loggerName']
		
		getattr(system.util.getLogger(loggerName), level)(message)