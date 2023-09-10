"""
	Make logging easier!
"""


try:
	from com.inductiveautomation.factorypmi.application import FPMIWindow
	from com.inductiveautomation.factorypmi.application.components.template import TemplateHolder
except ImportError:
	pass # only needed for when the logger's running on a Vision client; gateway won't have this in scope.

import sys, re
from shared.tools.meta import currentStackDepth, getObjectByName, get_perspective_self
from shared.tools.meta import GLOBAL_MESSAGE_PROJECT_NAME

from exceptions import BaseException
import java.lang.Class as JavaClass
import java.lang.Object as JavaObject
from java.lang import Exception as JavaException


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


__all__ = ['Logger', 'PrintLogger', 'ConsoleLogger']


VISION_CLIENT_MESSAGE_HANDLER = 'Vision Client Log'
PERSPECTIVE_SESSION_MESSAGE_HANDLER = 'Perspective Log Relay'


BAD_FORMAT_GUESS_PATTERN = re.compile(r'unsupported format character .* at index (\d+)', re.I)


def autoRepr(obj):
	"""Cleans up repr() calls, since the string representation add quotes."""
	return obj if isinstance(obj, (str,unicode)) else repr(obj)


def uri_to_module_path(some_path):
	return re.sub('[^a-zA-Z0-9._]', '_', some_path.replace('/', '.'), re.I)


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

		# it's possible that the interpolator will get confused if there's
		# a naturally occuring formatter - it's rare, but %b shows up sometimes!
		formatted_message = message
		for i in range(20): # don't even chance infinite loops here...
			try:
				formatted_message = message % varScope
				break
			except ValueError as error:
				match = BAD_FORMAT_GUESS_PATTERN.match(str(error))
				if match:
					ix = int(match.groups()[0])
					message = message[:ix] + '%' + message[ix:]
			except Exception: # all other errors are irrecoverable
				break
		return formatted_message

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
	def __init__(self, loggerName=None, prefix=None, suffix=None, relay=False, target_context=None, logging_level=None):
		#raise NotImplementedError('This is under development and is not fully functional yet.')
		self.relay = relay
		self._logging_level = logging_level # allow for deeper logging levels for log4j

		self._autoConfigure(loggerName, target_context)

		if prefix is not None:
			if prefix == '':
				self.prefix = ''
			else:
				self.prefix = '%s%s' % (prefix, self.prefix)
		
		if suffix is not None: 
			if suffix == '':
				self.suffix = ''
			else:
				self.suffix = '%s%s' % (self.suffix, suffix)


	def _getScope(self, context=None):
		if context is None:
			frame = sys._getframe(self._stackDepth - 1)
			return frame.f_code.co_filename
		elif isinstance(context, BaseException):
			err_type, err_value, err_traceback = sys.exc_info()
			# zoom in on exception
			while err_traceback.tb_next:
				err_traceback = err_traceback.tb_next

			self.prefix = ' [%s:%d] ' % (
				#err_traceback.tb_frame.f_code.co_filename,
				err_traceback.tb_frame.f_code.co_name, 
				err_traceback.tb_frame.f_lineno)
			return err_traceback.tb_frame.f_code.co_filename
		elif isinstance(context, object):
			try:
				return context.__init__.im_func.func_code.co_filename
			except:
				try:
					return context.func_code.co_filename
				except:
					return repr(context)
		if isinstance(context, (JavaClass, JavaObject)):
			type_path = repr(context)
			if type_path.startswith('<type '):
				return '<%s>' % repr(JavaClass)[6:-1]
			else:
				return type_path
		frame = sys._getframe(self._stackDepth - 1)
		return frame.f_code.co_filename

	def _generatePerspectiveComponentPath(self, scope, component=None):
		# parsed as example in 'function: onActionPerformed' or 'custom-method someFunction'
		functionName = scope.partition(':')[2] if ':' in scope else scope.partition(' ')[2]
		
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
		
		view_path = str(view.id).partition('@')[0]
#		return '[%s - %s.%s] ' % (view.id, '/'.join(reversed(componentPath)), functionName)
		return (view_path, '/'.join(reversed(componentPath)), functionName)


	def _generateVisionComponentPath(self, scope, event=None, component=None):
		functionName = scope.partition(':')[2] if ':' in scope else scope.partition(' ')[2]
		
		if not event:
			event = getObjectByName('event', startRecent=False)
		
		if not component:
			if event is None:
				return ''
			component = event.source
		
		componentPath = []
		while not isinstance(component, FPMIWindow):
			label = component.name
			if isinstance(component, TemplateHolder):
				label = '<%s>' % component.templatePath
			componentPath.append(label)
			component = component.parent
		
		window_path = component.path
#		return '[%s: %s.%s] ' % (window_path, '/'.join(reversed(componentPath[:-3])), functionName)
		return (window_path, '/'.join(reversed(componentPath[:-3])), functionName)


	def _autoConfigure(self, loggerName=None, context=None):
		"""The master configuration routine. This will branch down and check if a known state is set.
		If so, it will try to name itself something appropriate, with a focus on making gateway logs
		  easier to filter for the specific situation getting logged.
		Additional information may be bolted on via the prefix/suffix to provide context.
		"""
		self.prefix = ''
		self.suffix	= ''

		scope = self._getScope(context)[1:-1] # remove the angle brackets

		# Playground!
		if scope in ('buffer', 'input'):
			self.loggerName = loggerName or 'Script Console'
			self.logger = PrintLogger()
		# Scripts!
		elif scope.startswith('module:'):
			project_name = system.util.getProjectName()
			self.loggerName = loggerName or ('%s.%s' % (project_name, scope[7:]) if project_name else scope[7:])
			self._set_ignition_logger()
			if self._isVisionDesigner() or self._isVisionClient():
				self._configureVisionClientRelay()
				try:
					window_path, component_path, component_method = self._generateVisionComponentPath(scope)
					self.prefix +=  '[%s: %s.%s] ' % (view_path, component_path, component_method,)
					self.suffix += ' [Client %s]'  % self._getVisionClientID()
				except (Exception, JavaException):
					pass
			elif self._isPerspective():
				try:
					view_path, component_path, component_method = self._generatePerspectiveComponentPath(scope)
					self.prefix +=  '[%s: %s.%s] ' % (view_path, component_path, component_method,)
					self.suffix += ' [Session %s]' % self._getPerspectiveClientID()
				except (Exception, JavaException):
					pass
		# WebDev endpoint!
		elif self._isWebDev():
			self.loggerName = loggerName or '[%s] WebDev' % system.util.getProjectName()
			self._set_ignition_logger()
			endpoint,_,eventName = scope.rpartition(':')
			self.prefix += '[%s %s] ' % (eventName[2:].upper(), '/'.join(endpoint.split('/')[1:]))
		# Tags!
		elif scope.startswith('tagevent:'):
			tagPath = getObjectByName('tagPath')
			provider,_,tagPath = tagPath[1:].partition(']')
			self.loggerName = loggerName or '[%s] Tag %s Event' % (provider, scope[9:])
			self.prefix += '{%s} ' % tagPath
			self._set_ignition_logger()
			if provider == 'client':
				self._configureVisionClientRelay()
		# Perspective!
		elif self._isPerspective():
			view_path, component_path, component_method = self._generatePerspectiveComponentPath(scope)
			self.loggerName = '%s.%s.%s' % ('PerspectiveView', system.util.getProjectName(), uri_to_module_path(view_path))
			self._set_ignition_logger()
			self.prefix += '[%s.%s] ' % (component_path, component_method,)
			self.suffix += ' [Session %s]' % self._getPerspectiveClientID()
#			try:
#				self.prefix += self._generatePerspectiveComponentPath(scope)
#			except (Exception, JavaException):
#				pass
			self.relay = False # NotImplementedError
			# if self.relay:
			# 	self.relayScope = {'scope': 'C', 'hostName': session.props.host}
			# 	self.relayHandler = PERSPECTIVE_SESSION_MESSAGE_HANDLER
			# 	self.relayProject = GLOBAL_MESSAGE_PROJECT_NAME or system.util.getProjectName()
		# Clients!
		elif self._isVisionScope():
			window_path, component_path, component_method = self._generateVisionComponentPath(scope)
			self.loggerName = '%s.%s.%s' % ('Vision', system.util.getProjectName(), uri_to_module_path(window_path))
			self._set_ignition_logger()
			self.prefix += '[%s.%s] ' % (component_path, component_method,)
			self.suffix += ' [Client %s]' % self._getVisionClientID()
			self._configureVisionClientRelay()
		else:
			self.loggerName = loggerName or 'Logger'
			self._set_ignition_logger()


	def _set_ignition_logger(self):
		self.logger = system.util.getLogger(self.loggerName)
		if self._logging_level in self._ignition_logLevels:
			system.util.setLoggingLevel(self.loggerName, self._logging_level)


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
		try:
			perspective_self = get_perspective_self()
			assert perspective_self, 'Perspective component wrapper that kicked off script not found in execution stack'
			return str(perspective_self.session.props.id)[:6]
		except (AssertionError, AttributeError):
			client_address = system.tag.read('[System]Client/Network/IPAddress').value
			system.util.getLogger('FailLog').info(repr(client_address))
			if client_address:
				return 'Perspective on %r' % (client_address,)
			else:
				return 'Perspective (???)' 
	
	def _configureVisionClientRelay(self):
		self.relay = True
		self.relayScope = {'scope': 'G'}
		self.relayHandler = VISION_CLIENT_MESSAGE_HANDLER
		self.relayProject = GLOBAL_MESSAGE_PROJECT_NAME or system.util.getProjectName()

	@staticmethod
	def _isPerspective():
		"""Returns True when we simply have access to Perspective module stuff."""
		if not 'perspective' in dir(system):
			return False
		# almost everything in Perspective refers to a self object, like a normal Python class
		# so we'll look for the event that kicked off everything and see if it's actually
		# a Perspective object wrapper
		# (specifically com.inductiveautomation.perspective.gateway.script.ComponentModelScriptWrapper$SafetyWrapper)
		try:
			perspective_self = get_perspective_self()
			return perspective_self is not None
		except Exception as error:
			return False
		
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
	_ignition_logLevels = ["trace", "debug", "info", "warn", "error"]

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
		
		try:
			results = system.util.sendMessage(self.relayProject, self.relayHandler, payload, **self.relayScope)
		except:
			results = None # relay not configured or broken
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
