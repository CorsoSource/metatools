from weakref import WeakValueDictionary
from time import sleep

from shared.tools.thread import getThreadState, Thread, async, getThreadInfo
from shared.tools.global import ExtraGlobal
from shared.tools.data import randomId, chunks

from shared.tools.debug.hijack import SysHijack
from shared.tools.debug.frame import iter_frames
from shared.tools.debug.breakpoint import Breakpoint

from shared.tools.debug.codecache import CodeCache, trace_entry_line
from shared.tools.debug.snapshot import Snapshot

from shared.tools.debug.trap import TransientTrap, Step, Next, Until, Return

from ast import literal_eval
from time import sleep
from collections import deque 
from datetime import datetime, timedelta
import textwrap, math

from shared.tools.pretty import p,pdir


# Standardize the string keys that will be used
# NOTE: Enum will break the message handlers when in payloads, apparently. 
#   It's _literally_ a string, but the Jython reflection gets hung up on the details, it seems.
# Python doesn't treat it as different, but Java has a different opinion.

from shared.tools.enum import Enum

class ExtraGlobalScopes(Enum):
	INSTANCES = 'Tracers'
	REMOTE_INFO = 'Remote Tracers'
	REMOTE_COMMANDS = 'Remote Tracer Commands'

class MessageTypes(Enum):
	LISTING = 'list'
	INPUT = 'input'
	COMMAND = 'command'
	STATE_UPDATE = 'update'
	STATE_CHECK = 'check'
	
class MessageScopes(Enum):
	GATEWAY = 'G'
	CLIENT = 'C'
	ALL = 'GC'

class IgnitionContexts(Enum):
	DESIGNER = 'D'
	GATEWAY = 'G'
	VISION_CLIENT = 'V'
	PERSPECTIVE_SESSION = 'P'


#==========================================================================
# SCRAM
#==========================================================================
#   Makes kill -9 an option

def SCRAM():
	"""Iterate over all the currently tracked tracers, shut 'em down, and remove them."""
	for tracer_id in Tracer.tracers:
		tracer = Tracer[tracer_id]
		tracer.shut
		del Tracer[tracer_id]
			
SCRAM_DEADMAN_SIGNAL = {'SCRAMS on empty': True}


#==========================================================================
# NOP Trace function
#==========================================================================
#   Keeps the motor running

def NOP_TRACE(frame=None, event=None, arg=None, SCRAM_DEADMAN_SIGNAL=SCRAM_DEADMAN_SIGNAL):
	"""
	The trace mechanics need to be active, but it only needs to keep itself running.
	This acts mostly like a no-op function, returning itself for frames that
	  are not explicitly blocked (by Tracer.skip_frame(...)).
	It also checks if a SCRAM has been requested, and if so begins the flush.
	"""	
	if not SCRAM_DEADMAN_SIGNAL:
		SCRAM()
		return None
	
	# Overhead likely worth it to avoid tracing builtins and such
	if _skip_frame(frame):
		return None
	
	return NOP_TRACE


SKIP_NAMESPACES = set([
	'weakref', 'datetime', 'encodings',
	])

SKIP_FILES = set([
	'<module:shared.tools.debug.breakpoint>',
	'<module:shared.tools.debug.codecache>',
	'<module:shared.tools.debug.frame>',
	'<module:shared.tools.debug.hijack>',
	'<module:shared.tools.debug.proxy>',
	'<module:shared.tools.debug.snapshot>',
	'<module:shared.tools.debug.tracer>',
	'<module:shared.tools.debug.trap>',
	])

def _skip_frame(frame):
	return any((
		frame.f_globals.get('__name__') in SKIP_NAMESPACES,
		frame.f_code.co_filename in SKIP_FILES,
		))


#==========================================================================
# Meta - Tracer class methods
#==========================================================================


class MetaTracer(type):
	"""
	Class-level details are broken out here as a metaclass. 

	It allows certain convenience functions to work and makes 
	  instance/class methods easier to tell apart.
	"""

	def __getitem__(cls, tracer_id):
		"""Get the tracer from the global cache"""
		if isinstance(tracer_id, (str,unicode)):
			return ExtraGlobal[tracer_id:ExtraGlobalScopes.INSTANCES]
		if isinstance(tracer_id, (int, long)):
			for tracer in cls:
				if tracer.thread.id == tracer_id:
					return tracer
			raise KeyError("Tracer working on Thread ID %d not found" % tracer_id)
		if isinstance(tracer_id, Thread):
			for tracer in cls:
				if tracer.thread is tracer_id:
					return tracer
			raise KeyError("Tracer working on Thread %r not found" % tracer_id)
		
		raise KeyError("Tracer associated with %r not found" % tracer_id)

	def __setitem__(cls, *args):
		"""Tracers are internally managed. This is a ERRNOP"""
		raise NotImplementedError("Tracers may not be manually set.")

	def __delitem__(cls, tracer_id):
		"""Trash a tracer from the global cache"""
		try:
			tracer = ExtraGlobal[tracer_id:ExtraGlobalScopes.INSTANCES]
			tracer.shutdown()
			del ExtraGlobal[tracer_id:ExtraGlobalScopes.INSTANCES]
		except Exception, err:
			system.util.getLogger('MetaTracer').error("Tracer [%s] did NOT shutdown gracefully" % tracer_id)
			raise err
			
	def __iter__(cls):
		"""Iterate over all tracers currently tracked"""
		for tracer_id in cls.tracer_ids:
			yield ExtraGlobal[tracer_id:ExtraGlobalScopes.INSTANCES]

	@property
	def tracers(cls):
		return list(cls.__iter__())

	@property
	def tracer_ids(cls):
		return ExtraGlobal.keys(scope=ExtraGlobalScopes.INSTANCES)


	#==========================================================================
	# Ignition Messages
	#==========================================================================

	#--------------------------------------------------------------------------
	# Remote API
	#--------------------------------------------------------------------------

	def request_ids(cls):
		"""Requests the listing of currently active tracers (from the hub's perspective)"""
		if cls.REMOTE_MESSAGING:
			return system.util.sendRequest(
					project=cls.IGNITION_MESSAGE_PROJECT,
					messageHandler=cls.IGNITION_MESSAGE_HANDLER,
					payload = {
						'message': str(MessageTypes.LISTING),
						'id': None,
					},
					timeoutSec=cls._MESSAGE_CALLBACK_TIMEOUT,
					scope=MessageScopes.GATEWAY,
				)
		else:
			raise RuntimeError("Tracer REMOTE_MESSAGING is not enabled.")


	def request_state(cls, tracer_id):
		"""Requests the last logged state for the tracer id given."""
		if cls.REMOTE_MESSAGING:
			return system.util.sendRequest(
					project=cls.IGNITION_MESSAGE_PROJECT,
					messageHandler=cls.IGNITION_MESSAGE_HANDLER,
					payload = {
						'message': str(MessageTypes.STATE_CHECK),
						'id': tracer_id,
					},
					timeoutSec=cls._MESSAGE_CALLBACK_TIMEOUT,
					scope=MessageScopes.GATEWAY,
				)
		else:
			raise RuntimeError("Tracer REMOTE_MESSAGING is not enabled.")


	def send_command(cls, tracer_id, command):
		"""Send a request to the tracer hub (gateway) to set up a command."""
		if cls.REMOTE_MESSAGING:
			_ = system.util.sendMessage(
				project=cls.IGNITION_MESSAGE_PROJECT,
				messageHandler=cls.IGNITION_MESSAGE_HANDLER,
				payload={
					'id': tracer_id,
					'message': str(MessageTypes.COMMAND),
					'command': command,
					},
				scope=MessageScopes.GATEWAY,
				)
		else:
			raise RuntimeError("Tracer REMOTE_MESSAGING is not enabled.")


	#--------------------------------------------------------------------------
	# Message Handler
	#--------------------------------------------------------------------------

	def _handle_payload(cls, payload):
		"""
		Handle payloads sent for debug messages.
		To use, paste this in the event script at IGNITION_MESSAGE_HANDLER in IGNITION_MESSAGE_PROJECT

			return shared.tools.debug.tracer.Tracer._handle_payload(payload)
		"""
		tracer_id = payload['id']
		message_type = payload['message']

		# system.util.getLogger('Tracer %s' % (tracer_id,)).info('Message "%s" for "%s" recieved' % (message_type, tracer_id))

		# Replate with the current tracer IDs available for remote control
		if message_type == MessageTypes.LISTING:
			return ExtraGlobal.keys(scope=ExtraGlobalScopes.REMOTE_INFO)

		# Reply to a tracer's request for commands (if any have been buffered)
		if message_type == MessageTypes.INPUT:
			commands = ExtraGlobal.get(label=tracer_id, 
									   scope=ExtraGlobalScopes.REMOTE_COMMANDS, 
									   default=[])
			if commands:
				ExtraGlobal.trash(label=tracer_id, 
								  scope=ExtraGlobalScopes.REMOTE_COMMANDS)
			return commands

		# Enqueue a command sent to the hub
		if message_type == MessageTypes.COMMAND:
			command = payload.get('command', payload.get('commands', []))
			system.util.getLogger('Tracer %s' % (tracer_id,)).info('Message "%s" for "%s" recieved: %r' % (message_type, tracer_id, command))
			cls._queue_command(tracer_id, command)
			return

		# Update currently known state
		if message_type == MessageTypes.STATE_UPDATE:
			def heartbeat_check(cls=cls, tracer_id=tracer_id):
				cls._check_heartbeat(tracer_id)
			ExtraGlobal.stash(payload,
							  label=tracer_id, 
							  scope=ExtraGlobalScopes.REMOTE_INFO,
							  lifespan=30, # seconds
							  callback=heartbeat_check)
			return 
			
		# Reply with tracer state
		if message_type == MessageTypes.STATE_CHECK:
			state = ExtraGlobal.get(label=tracer_id,
								   scope=ExtraGlobalScopes.REMOTE_INFO,
								   default=None)
			if not state:
				return None
			state['message'] = str(MessageTypes.STATE_CHECK)
			return state

			
	def _check_heartbeat(cls, tracer_id):
		#system.util.getLogger('Tracer %s' % (tracer_id,)).info('Heartbeat check...')

		pending_commands = ExtraGlobal.get(label=tracer_id, 
									   scope=ExtraGlobalScopes.REMOTE_COMMANDS, 
									   default=[])
		if isinstance(pending_commands, (list, tuple)):
			# Check if we've already tried to send the command and failed
			if 'heartbeat' in pending_commands:
				return
		elif isinstance(pending_commands, (str, unicode)):
			if 'heartbeat' == pending_commands:
				return
		
		#system.util.getLogger('Tracer %s' % (tracer_id,)).info('Heartbeat extending')

		cls._queue_command(tracer_id, 'heartbeat')
		ExtraGlobal.extend(label=tracer_id, 
						   scope=ExtraGlobalScopes.REMOTE_INFO,
						   additional_time=self._MESSAGE_CALLBACK_TIMEOUT)


	def _queue_command(cls, tracer_id, command):
		"""Enqueue a command onto the local ExtraGlobal remote control list"""
		commands = ExtraGlobal.get(label=tracer_id, 
								   scope=ExtraGlobalScopes.REMOTE_COMMANDS, 
								   default=[])
		if not commands:
			commands = command
		if isinstance(commands, (list, tuple)):
			if isinstance(command, (list, tuple)):
				commands += command
			else:
				commands.append(command)
		elif isinstance(commands, (str, unicode)):
			commands = command

		ExtraGlobal.stash(commands,
						  label=tracer_id, 
						  scope=ExtraGlobalScopes.REMOTE_COMMANDS)


#==========================================================================
# Tracer definition
#==========================================================================

class Tracer(object):
	"""A variant of the Python Debugger (Pdb)
	
	This is designed to overcome and take advantage of the different
	  constraints that running Pdb in a multi-threaded environment
	  creates.

	Breakpoints are created globally, enabled PER TRACER, and break by default.
	Traps are created for a tracer, enabled by default, and break only on success.

	Breakpoints are evaluated _before_ the line is executed.
	  For example, if a breakpoint is set for the line 'x += 1' and 
	  has a condition 'x == 20', then trace.cursor_frame (lowest frame) will show
	  x is 20, _not_ 21.

	NOTE: If this is activated inline with the code (same thread), it will NOT
	      wait indefinitely. You MUST turn off the Tracer instance's INTERDICTION_FAILSAFE
	      or it will time out quickly!
	  
	For more information and the cool implementation that we're tweaking here,
	  see also rpdb at https://github.com/tamentis/rpdb
	"""
	__metaclass__ = MetaTracer

	__slots__ = (
				 # Event attributes
				 '_map_for_dispatch', 
				 'monitoring',

				 # Command attributes

				 '_cursor_index', '_cursor_stack', '_cursor_context_index',
				 '_pending_commands', 
				 '_map_o_commands', '_logged_commands',
				 '_current_context', 'recording', 'context_buffer',
				 
				 '_alias_commands', 
				 'traps', 'active_traps', 
				 
				 # Tracer attributes
				 'thread', 'sys', 'tracer_thread',
				 'interdicting',
				 '_top_frame',

				 'step_speed',
				 '_FAILSAFE_TIMEOUT', '_debug', # DeprecationWarning
				 'logger', 'id',

				 # Ignition details
				 '_ignition_host', '_ignition_scope', '_ignition_client', '_ignition_project',

				 # Remote control handles
				 '_remote_request_handle', '_remote_request_thread',
				 'tag_path', 'tag_acked',
				 
				 '__weakref__', # Allows the weakref mechanics to work on this slotted class.
				)


	#==========================================================================
	# Constants and references
	#==========================================================================
	
	SCRAM_DEADMAN_SIGNAL = SCRAM_DEADMAN_SIGNAL
	
	CONTEXT_BUFFER_LIMIT = 1000
	COMMAND_BUFFER_LIMIT = 1000
	_UPDATE_CHECK_DELAY = 0.200 # seconds (leave relatively high since it should be driven by human input.)
	INTERDICTION_FAILSAFE = False # True
	INTERDICTION_FAILSAFE_TIMEOUT = 30000 # milliseconds (seconds if failsafe disabled)
		
	# _event_labels = set(['call', 'line', 'return', 'exception', 
	# 					 'c_call', 'c_return', 'c_exception',
	# 					 ])	

	#--------------------------------------------------------------------------
	# Ignition Messaging
	#--------------------------------------------------------------------------

	IGNITION_MESSAGE_PROJECT = 'Debugger'
	IGNITION_MESSAGE_HANDLER = 'Remote Tracer Control'

	# If possible, allow Ignition message traffic to request inputs
	REMOTE_MESSAGING = False # True if getattr(system.util, 'sendRequest', None) else False

	# Make sure the sendRequest is not called more often than a few times a second, 
	#   or the client starts to log jam events a bit.
	_MESSAGE_CALLBACK_TIMEOUT = 1.50 # seconds


	#==========================================================================
	# Tracer INIT
	#==========================================================================


	def __init__(self, thread=None, *args, **kwargs):
	
		self._ignition_host = ''
		self._ignition_scope = None
		self._ignition_client = None
		self._ignition_project = ''
		self._resolve_ignition_scope()

		self.id = randomId(5)
		self.logger = system.util.getLogger('Tracer %s' % self.id)

		# Remote control handles
		self._remote_request_handle = None
		self._remote_request_thread = None

		self.tag_path = ''
		self.tag_acked = False

		# Event init
		
		self.monitoring = False

		self._map_for_dispatch = dict(
			(attribute[10:], getattr(self, attribute))
			for attribute in dir(self)
			if attribute.startswith('_dispatch_'))

		# Command init

		self._map_o_commands = dict(
			(attribute[9:], getattr(self, attribute))
			for attribute in dir(self)
			if attribute.startswith('_command_'))
		
		self._pending_commands = []
		self._logged_commands = deque()
		self._cursor_context_index = 0
		self._cursor_index = 0
		self._cursor_stack = tuple()

		self.recording = record
		self.context_buffer = deque()
		self._current_context = None

		self._alias_commands = {}
		self.traps = set()
		self.active_traps = set()

		# Tracer init

		self.tracer_thread = Thread.currentThread()
		self.thread = thread or self.tracer_thread
		
		self.logger.info("Tracing [%s] from %r onto %r" % (self.id, self.tracer_thread, self.thread))
		
		self.sys = SysHijack(self.thread)

		self.interdicting = False		
		self._top_frame = None
		self._debug = {}
		self.step_speed = 0

		self._FAILSAFE_TIMEOUT = datetime.now()


		self._add_tracer(self)
		self._log_command('<INIT>', 'Done.')

		self._send_update()

		#start the machinery so we can inject directly
		#self.sys.settrace(Tracer.dispatch)
		self.sys.settrace(NOP_TRACE)
		
		
	def __repr__(self):	
		"""Custom high level glance at tracer"""
		return '<Tracer [%s] (%s) on %r>' % (self.id, self.state, self.thread)

		
	def SCRAM(self):
		# Clear out any active traces running
		for frame in iter_frames(self.current_frame):
			if frame.f_trace:
				del frame.f_trace
		self.shutdown()


	def _add_tracer(self, tracer):
		ExtraGlobal.stash(tracer, 
						  tracer.id, 
						  scope=ExtraGlobalScopes.INSTANCES, 
						  callback=tracer._renew_cache_entry)


	def _renew_cache_entry(self):
		"""Drop the tracer if its monitoring thread dies."""
		if self.thread.getState() != Thread.State.TERMINATED:
			return self

	#--------------------------------------------------------------------------
	# Context control - start and stop active tracing
	#--------------------------------------------------------------------------


	def __enter__(self):
		self.monitor()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.shutdown()


	#--------------------------------------------------------------------------
	# Un/Install to the call stack
	#--------------------------------------------------------------------------

	def _stack_install(self):
		"""Install the trace dispatcher to every level of the stack 
		and then set the trace machinery in motion.
		"""
		frame = self.sys._getframe()
		while frame:
			frame.f_trace = self.dispatch
			# track the furthest up the stack goes
			self._top_frame = frame
			frame = frame.f_back
		
		# Trace is already initialized by this point, and setting
		#  the frame's trace ensures dispatch will trigger on the
		#  next line. That dispatch will call sys.settrace as well,
		#  but strictly from within the target thread.
		#self.sys.settrace(self.dispatch)


	def _stack_uninstall(self):
		"""Turn off trace and remove the trace dispatcher from every level 
		in the stack.
		"""
		self.sys.settrace(None)
		
		frame = self.sys._getframe()
		while frame:
			if frame.f_trace:
				del frame.f_trace
			frame = frame.f_back


	#--------------------------------------------------------------------------
	# Run state status controls
	#--------------------------------------------------------------------------

	def monitor(self):
		"""Begin trace, watching each frame event."""
		self.monitoring = True
		self._stack_install()
	
		self._debug['entry'] = self.sys._getframe()		

	def interdict(self):
		"""Begin trace, interdicting each frame event and waiting for commands."""
		self.interdicting = True
		self.monitor()		
		
	def shutdown(self):
		"""Stop the trace and tear down the setup."""
		self.interdicting = False
		self.monitoring = False
		self._cursor_stack = tuple()
		try:
			self._stack_uninstall()
			self.sys._restore()
			if self._remote_request_handle:
				self._remote_request_handle.cancel()
			self.logger.info('Tracer shutdown complete.')
		except:
			raise RuntimeError('Tracer shutdown gracelessly - traced thread is likely already dead and cleanup thus failed.')


	#==========================================================================
	# Convenience properties
	#==========================================================================

	@property
	def state(self):
		"""Quick convenience label"""
		if self.interdicting:
			state = 'interdicting'
		elif self.monitoring:
			state = 'monitoring'
		else:
			state = 'inactive'
		
		if self.thread.state == Thread.State.BLOCKED:
			thread_info = getThreadInfo(self.thread)
			try:
				blocker = Tracer[thread_info.getLockOwnerId()]
				if blocker is self:
					state += ", possible self-deadlock!"
				else:
					state += ", currently [%s] tracing" % blocker.id
			except KeyError:
				state += ", currently blocked by Thread[%s, %d]" % (thread_info.getLockOwnerName(), thread_info.getLockOwnerId())
		return state
		
	@property
	def debug(self):
		return self._debug

	@property
	def current_frame(self):
		if self._current_context:
			return self._current_context.frame
		else:
			return self.sys._getframe()

	@property 
	def current_locals(self):
		return self.current_frame.f_locals
	@property
	def current_globals(self):
		return self.current_frame.f_globals
	@property
	def current_code(self):
		return self.current_frame.f_code

	@property
	def current_context(self):
		return self._current_context


	@property 
	def cursor_frame(self):
		# Though technically the same, 
		# we'll treat the very most present context directly instead of via buffer
		if self._cursor_context_index == 0:
			# Override to fail safe to local context (if we're not actively monitoring...)
			if self._cursor_index < len(self._cursor_stack):
				return self._cursor_stack[self._cursor_index]
			else:
				return self.sys._getframe()
		else:
			frame = self.cursor_context.frame
			for i in range(self._cursor_index):
				if frame.f_back:
					frame = frame.f_back
				else:
					break
			return frame

	@property
	def cursor_context(self):
		return self.context_buffer[self._cursor_context_index]

	@property 
	def cursor_locals(self):
		return self.cursor_frame.f_locals
	@property
	def cursor_globals(self):
		return self.cursor_frame.f_globals
	@property
	def cursor_code(self):
		return self.cursor_frame.f_code
	
	@property
	def context_recent_traceback(self, past=20):
		context_traceback = []
		for i, context in enumerate(self.context_buffer):
			context_traceback.append(repr(context))
			if i >= past:
				break
		return context_traceback

	@property
	def stdin_log(self):
		return self.sys._io_proxy.stdin.history
	@property
	def stdout_log(self):
		return self.sys._io_proxy.stdout.history
	@property
	def stderr_log(self):
		return self.sys._io_proxy.stderr.history


	def __lshift__(self, command):
		"""
		Run command like 
		tracer << 'source 5'
		"""
		return self.command(command)

	def __rrshift__(self, command):
		"""
		Run command like
		'source 5' >> tracer
		"""
		return self.command(command)

	
	#==========================================================================
	# Interdiction Triggers
	#==========================================================================

	def interdict_context(self, frame, event, arg):
		"""Determine if execution should be stopped."""
		# Poorman's decorator
		self.interdicting = self._interdict_context(frame, event, arg)
		return self.interdicting


	def _interdict_context(self, frame, event, arg):
		"""Do the actual interdiction checks against the context."""		
		if self.interdicting:
			return True # if already interdicting, continue

		if self.active_traps:
			return True

		if Breakpoint.relevant_breakpoints(frame, self):
			return True

		return False 


	def check_traps(self):
		"""Check any traps, and mark them active if the context triggers it.

		Any transient traps are removed when placed on the active set.
		"""		
		self.active_traps = set()
		for trap in frozenset(self.traps):
			if trap.check(self.current_context):
				
				#self.logger.info('TRIP: %r on %r' % (trap, self.current_context,))
				
				if isinstance(trap, TransientTrap):
					self.active_traps.add(trap)
					self.traps.remove(trap)
				else:
					self.active_traps.add(trap)
					
		#if not self.active_traps:
		#	self.logger.info('No active traps on %r' % (self.current_context,))


	#==========================================================================
	# Trace Events
	#==========================================================================


	#--------------------------------------------------------------------------
	# Dispatch
	#--------------------------------------------------------------------------
	
	def dispatch(self, frame, event, arg):
		"""
		The master dispatch called from the sys.settrace tracing functionality.
		
		NOTE: Due to the way Jython performs tracing, this WILL block other
		      trace threads. This is part of the Jython implementation of 
		      the tracing call function, where it forces a synchronized state.
		"""		
		if not self.SCRAM_DEADMAN_SIGNAL:
			self.SCRAM(frame)
			return None
		
		self.cursor_reset()
		
		if not self.monitoring:
			self._cursor_stack = tuple()
			return None
				
		if _skip_frame(frame):
			return None
			
		if self.step_speed:
			sleep(self.step_speed) # DEBUG
		
		self._cursor_stack = tuple(iter_frames(frame))
		self._current_context = Snapshot(frame, event, arg, clone=self.recording)
		
		# Buffer's most present is always index 0
		if self.recording:
			self.context_buffer.appendleft(self._current_context)
			#self.context_buffer.insert(0,self._current_context)
		while len(self.context_buffer) > self.CONTEXT_BUFFER_LIMIT:
			_ = self.context_buffer.pop()

		self.logger.info('%r' % self._current_context)

		# From user code to overrides, this is the section that can go wrong.
		# Blast shield this with a try/except
		try:
			# Dispatch and continue as normal
			# Note that we don't really do anything with this...
			#   The rest of the function determines how we reply to sys' trace
			dispatch_retval = self._map_for_dispatch.get(event, NOP_TRACE)(frame, arg)
			
			self.check_traps()

			# Check if execution should be interdicted for debugging
			if self.interdict_context(frame, event, arg):
				self.command_loop()
				
		except Exception, err:
			self.logger.error('Dispatch Error: %r' % err)
		

		# Ensure trace continues in this context
		if frame.f_trace is None:
			frame.f_trace = self.dispatch
		
		# Ideally we'd use sys.gettrace but that ain't a thing in Jython 2.5
		if self.monitoring and not _skip_frame(frame):
			self.sys.settrace(self.dispatch)
		else:
			self.shutdown()
		
		# TRAMPOLINE GOOOOO
		return self.dispatch
		

	#--------------------------------------------------------------------------
	# Event Dispatch
	#--------------------------------------------------------------------------

	def _dispatch_call(self, frame, _=None):
		self.on_call(frame)

	def _dispatch_line(self, frame, _=None):
		self.on_line(frame)

	def _dispatch_return(self, frame, return_value):
		self.on_return(frame, return_value)

	def _dispatch_exception(self, frame, (exception, value, traceback)):
		self.on_exception(frame, (exception, value, traceback))


	# Jython shouldn't ever call these, so they're here for completeness/compliance
	def _dispatch_c_call(self, frame, _=None):
		pass
	def _dispatch_c_return(self, frame, return_value):
		pass
	def _dispatch_c_exception(self, frame, (exception, value, traceback)):
		pass


	#--------------------------------------------------------------------------
	# User overridable hooks
	#--------------------------------------------------------------------------
	
	def on_call(self, frame):
		pass
	def on_line(self, frame):
		pass
	def on_return(self, frame, return_value):
		pass
	def on_exception(self, frame, (exception, value, traceback)):
		pass


	#==========================================================================
	# Ignition Messages
	#==========================================================================


	def _resolve_ignition_scope(self):

		self._ignition_project = system.util.getProjectName()
		self._ignition_host = system.net.getHostName()

		if getattr(system.util, 'getSystemFlags', None):
			sysFlags = system.util.getSystemFlags()
			if sysFlags & system.util.DESIGNER_FLAG:
				self._ignition_scope = IgnitionContexts.DESIGNER
				self._ignition_client = system.util.getClientId()
			elif sysFlags & system.util.CLIENT_FLAG:
				self._ignition_scope = IgnitionContexts.VISION_CLIENT
				self._ignition_client = system.util.getClientId()
		else:
			try:
				session = getObjectByName('session', startRecent=False)
				self._ignition_scope = IgnitionContexts.PERSPECTIVE_SESSION
				self._ignition_client = session.props.id
			except:
				self._ignition_scope = IgnitionContexts.GATEWAY
				self._ignition_client = None


	#--------------------------------------------------------------------------
	# Ignition message hooks
	#--------------------------------------------------------------------------

	def _request_command(self, blocking=True):
		"""
		Ask the debug project for input. 
		This supplements the self._pending_commands waiting loop.
		"""
		if not self.REMOTE_MESSAGING:
			raise RuntimeError("Remote messaging is not enabled.")

		# Don't attempt a request if already in progress
		if self._remote_request_handle:
			return

		if blocking:
			result = system.util.sendRequest(
					project=self.IGNITION_MESSAGE_PROJECT,
					messageHandler=self.IGNITION_MESSAGE_HANDLER,
					payload = {
						'message': str(MessageTypes.INPUT),
						'id': self.id,
					},
					timeoutSec=self._MESSAGE_CALLBACK_TIMEOUT,
					scope=MessageScopes.GATEWAY
					)

			if result:
				self._remote_request_handle = True
				self._request_command_onSuccess(result)
			
			sleep(self._UPDATE_CHECK_DELAY)
			return

		# Run in an async, since we don't want to risk waiting for GUI to finish
		#   while we're blocking it with a tracer
		@async(startDelaySeconds=self._UPDATE_CHECK_DELAY, name='Tracer-%s-CommandRequest' % self.id)
		def request_command(self=self):

			# Don't attempt a request if already in progress
			if self._remote_request_handle:
				return

			self._remote_request_handle = request_handle = system.util.sendRequestAsync(
					project=self.IGNITION_MESSAGE_PROJECT,
					messageHandler=self.IGNITION_MESSAGE_HANDLER,
					payload = {
						'message': str(MessageTypes.INPUT),
						'id': self.id,
					},
					timeoutSec=self._MESSAGE_CALLBACK_TIMEOUT,
					scope=MessageScopes.GATEWAY,

					# This runs on the GUI thread. That... may go badly if we're tracing a GUI script.
					#   So for that reason we'll just not use callbacks, and instead block explicitly.
					#onSuccess=self._request_reply_onSuccess,
					#onError=self._request_reply_onError
				)

			# Pass in request_handle as a sanity check.
			# It's possible that the request has been cancelled, replaced, or otherwise ignored.
			try:
				self._request_command_onSuccess(request_handle.get(), request_handle)
			except:
				self._request_command_onError(request_handle.getError(), request_handle)

		self._remote_request_thread = request_command()


	def _request_command_onSuccess(self, result, request_handle=None):
		# Fail if callback is deprecated or already handled
		if not self._remote_request_handle:
			return
		if request_handle and (self._remote_request_handle is not request_handle):
			return

		if result:
			if isinstance(result, (str, unicode)):
				self._pending_commands.append(result)
			elif isinstance(result, (list, tuple, set)):
				for command in result:
					self._pending_commands.append(command)

		# Request complete - clear it. 
		#   Assume that if not sanity check request_handle was passed in, this was correctly called back. 
		sleep(self._UPDATE_CHECK_DELAY)
		self._remote_request_handle = None


	def _request_command_onError(self, error, request_handle=None):
		# Fail if callback is deprecated or already handled
		if not self._remote_request_handle:
			return
		if request_handle and (self._remote_request_handle is not request_handle):
			return

		pass # don't do anything on error yet...

		# Request complete - clear it. 
		#   Assume that if not sanity check request_handle was passed in, this was correctly called back. 
		sleep(self._UPDATE_CHECK_DELAY)
		self._remote_request_handle = None


	def _send_update(self):
		pass
#		if self.REMOTE_MESSAGING:
#			_ = system.util.sendMessage(
#				project=self.IGNITION_MESSAGE_PROJECT,
#				messageHandler=self.IGNITION_MESSAGE_HANDLER,
#				payload=self._payload_tracer_state,
#				scope=MessageScopes.GATEWAY,
#				)


	#--------------------------------------------------------------------------
	# Payloads
	#--------------------------------------------------------------------------

	@property
	def _payload_tracer_state(self):
		return {
			'message': str(MessageTypes.STATE_UPDATE),
			'id': self.id,
			'ignition': self._payload_ignition_info,
			'cursor': self._payload_cursor_info,
			'log': self._payload_last_log,
		}
	
	@property
	def _payload_ignition_info(self):
		return {
			'host': self._ignition_host,			
			'project': self._ignition_project,
			'client': self._ignition_client,
			'scope': str(self._ignition_scope),
		}

	def _payload_last_logs(self, n=5):
		return {
 			'stdout': self.sys.stdout.history[-n:],
			'stdin': self.sys.stdin.history[-n:],
			'stderr': self.sys.stderr.history[-n:],
			'commands': [ {
					'in': self._logged_commands[i][0],
					'out': self._logged_commands[i][1],
				} for i in reversed(range(n)) if i < len(self._logged_commands)
			] 				
		}

	@property 
	def _payload_last_log(self, n=5):
		return {
 			'stdout': self.sys.stdout.history[-1:],
			'stdin': self.sys.stdin.history[-1:],
			'stderr': self.sys.stderr.history[-1:],
			'command': {
				'in': self._logged_commands[0][0],
				'out': self._logged_commands[0][1],
			}
		}

	@property
	def _payload_cursor_info(self):

		frame = self.cursor_frame

		radius = 10
		source_lines, source_start = self._command_source(radius=radius)

		return {
			'source': source_lines,
			'source_start': source_start,
			'locals': p(frame.f_locals, directPrint=False),
			'globals': p(frame.f_globals, directPrint=False),
			'code': pdir(frame.f_code, directPrint=False),
			'index': {
				'stack': self._cursor_index,
				'context': self._cursor_context_index,
			},
			'line': frame.f_lineno,
			'filename': frame.f_code.co_filename,
		}
		

	#==========================================================================
	# Interaction
	#==========================================================================

	#--------------------------------------------------------------------------
	# Command controls
	#--------------------------------------------------------------------------


	def command(self, command):
		"""
		Interpret commands like PDB: '!' means execute, 
		otherwise it's a command word followed by optional arguments.
		"""
		if not command:
			return

		# In case a command runs slower than fast, or if you want to compare cause and effect
		#   in the std* histories, then the timestamp should happen before it is run.
		# So capture here, then log after.
		timestamp = datetime.now()

		if command.lstrip()[0] == '!':
			result = self._command_statement(command)
		else:
			args = []
			for arg in command.split():
				try:
					args.append(literal_eval(arg))
				except:
					args.append(arg)
			result = self._map_o_commands.get(args[0], self._command_default)(command, *args[1:])

		self._log_command(command, result, timestamp)
		return result


	def command_loop(self):
		"""Run commands until interdiction is disabled."""

		if not self.interdicting:
			return
	
		# if Thread.currentThread() is self.tracer_thread:
		# 	raise RuntimeError("Await called from the wrong context! %r instead of %r" % (
		# 					self.tracer_thread, self.thread,) )
		
		if self.INTERDICTION_FAILSAFE:
			self._FAILSAFE_TIMEOUT = datetime.now() + timedelta(microseconds=self.INTERDICTION_FAILSAFE_TIMEOUT * 1000)
		
		while self.interdicting:
			if not self._pending_commands:

				# Attempt to allow remote control of tracer (in case of gui thread blocking, for example)
				if self.REMOTE_MESSAGING and not self._remote_request_handle:
					self._request_command(blocking=True)

				# If given a tag for input, check if it has a command ready.
				# To prevent repeated commands, value must be cleared between commands.
				if self.tag_path:
					tag_command = system.tag.read(self.tag_path).value
					if tag_command:
						if self.tag_acked:
							self._pending_commands.append(tag_command)
						self.tag_acked = False
					else:
						self.tag_acked = True

				sleep(self._UPDATE_CHECK_DELAY)

				# Failsafe off ramp
				if self.INTERDICTION_FAILSAFE and self._FAILSAFE_TIMEOUT < datetime.now():
					self.interdicting = False
					self.logger.warn('Interaction pause timed out!')
		
			while self._pending_commands and self.interdicting:
				#self.logger.info('Command: %s' % self.command)
				result = self.command(self._pending_commands.pop())

				# Reply to the tag's command with results
				if self.tag_path:
					if not self.tag_acked:
						if isinstance(result, (list, tuple, dict)):
							system.tag.write(self.tag_path, system.util.jsonEncode(result))
						else:
							system.tag.write(self.tag_path, str(result))
	
			# Send update after all commands are run (query for logs if batch set...)
			self._send_update()



	def _log_command(self, command, result, timestamp=None):
		format_string = '[%s] (IPD) %s'
		self._logged_commands.appendleft((format_string % (timestamp or datetime.now(), command), result))
		# self._logged_commands.insert(0, (format_string % (timestamp or datetime.now(), command), result))
		while len(self._logged_commands) > self.COMMAND_BUFFER_LIMIT:
			_ = self._logged_commands.pop()	


	def _await_pause(self):
		while not self._pending_commands:
			sleep(self._UPDATE_CHECK_DELAY)


	def _compile(self, expression, mode='eval'):
		return self.sys.builtins['compile'](expression, '<tracer:expression>', mode)
	
	def cursor_eval(self, expression):
		code = self._compile(expression)
		return self.sys.builtins['eval'](code, self.cursor_frame.f_globals, self.cursor_frame.f_locals)
	

	def cursor_reset(self):
		self._cursor_context_index = 0
		self._cursor_index = 0


	#==========================================================================
	# PDB Commands
	#==========================================================================


	def _command_heartbeat(self, command='heartbeat'):
		"""Sends an update to prove the tracer is still alive."""
		self._send_update()


	#--------------------------------------------------------------------------
	# Meta commands
	#--------------------------------------------------------------------------


	def _command_help(self, command='help', context=''):
		"""
		Print available commands. If given a command print the command data.
		"""
		# Return the info for the specific command, if requested
		if context:
			comfunc = self._map_o_commands[context]

			aliases = ', '.join(alias for alias,cf in self._map_o_commands.items() 
								if cf == comfunc)
			doc = textwrap.dedent(comfunc.__doc__.strip())

			return 'Aliases: %s\n%s' % (aliases, doc)

		# Otherwise list everything available
		else:
			help_columns = 5

			command_aliases = {}
			for alias, comfunc in self._map_o_commands.items():
				if comfunc in command_aliases:
					command_aliases[comfunc].append(alias)
				else:
					command_aliases[comfunc] = [alias]
			for comfunc, aliases in command_aliases.items():
				aliases.sort()
				# move the main alias to the head of the list (in place)
				# (name is _command_ALIAS, so skip first 9...)
				aliases.insert(0, aliases.pop(aliases.index(comfunc.__name__[9:])))

			all_aliases = [', '.join(aliases) for aliases in sorted(command_aliases.values())]

			width = max(len(a) for a in all_aliases)

			format_string = '%%-%ds' % width

			return 'Commands available (with aliases)\n|%s| ' % '|\n| '.join(
				' | '.join(
					format_string % a for a in chunk
				) for chunk in chunks(all_aliases, help_columns))
	_command_h = _command_help


	def _command_where(self, command='where'):
		"""
		Print a stack trace, with the most recent frame at the bottom, pointing to cursor frame.
		"""
		stack = [trace_entry_line(frame, indent= ('-> ' if index == self._cursor_index else '   ') )
				 for index, frame
				 in iter_frames(self.cursor_frame)]

		stack.append('Cursor is %s current execution frame in %s context' % (
			'at' if not self._cursor_index else ('%d from' % self._cursor_index),
			'the present' if not self._cursor_context_index else ('%d step(s) past' % self._cursor_context_index),
			))

		return '\n'.join(reversed(stack))

	_command_w = _command_where 


	# Position frame

	def _command_down(self, command='up'):
		"""
		Move the cursor to a more recent frame (down the stack)
		"""
		if self._cursor_index:
			self._cursor_index -= 1
		return self._cursor_index
	_command_d = _command_down

	def _command_up(self, command='up'):
		"""
		Move the cursor to an older frame (up the stack)
		"""
		if self._cursor_index < (len(self._cursor_stack) - 1):
			self._cursor_index += 1
		return self._cursor_index
	_command_u = _command_up


	# Position context

	def _command_back(self, command='back'):
		"""
		Move the context to an older executed line (into the past)
		"""
		if self._cursor_context_index < (len(self.context_buffer)-1):
			self._cursor_context_index += 1
		return self._cursor_context_index
	_command_b = _command_back

	def _command_forward(self, command='forward'):
		"""
		Move the context to a more recent executed line (towards the present)
		"""
		if self._cursor_context_index:
			self._cursor_context_index -= 1
		return self._cursor_context_index
	_command_f = _command_forward


	#--------------------------------------------------------------------------
	# Breakpoint controls
	#--------------------------------------------------------------------------


	def _command_clear(self, command='clear', *breakpoints):
		"""
		Clear breakpoint(s). Breakpoints can be by ID, location, or instance.
		If none are provided, clear all.
		"""
		breakpoints = Breakpoint.resolve_breakpoints(breakpoints)

		if not breakpoints:
			# self.logger.warn("Please confirm clearing all breakpoints (yes/no)")
			# self._await_pause()
			# command = self._pending_commands.pop()
			# if command.lower() in ('y','yes',):
			self.logger.warn("Clearing all breakpoints")
			breakpoints = Breakpoint._instances.values()
			# else:
			# 	self.logger.warn("Breakpoints were not cleared.")
			# 	return

		for breakpoint in breakpoints:
			breakpoint._remove()

	_command_cl = _command_clear


	def _command_enable(self, command='enable', *breakpoints):
		"""
		Enable the given breakpoints
		"""
		breakpoints = Breakpoint.resolve_breakpoints(breakpoints)

		for breakpoint in breakpoints:
			breakpoint.enable(self)


	def _command_disable(self, command='disable', *breakpoints):
		"""
		Disable the given breakpoints
		"""
		breakpoints = Breakpoint.resolve_breakpoints(breakpoints)

		for breakpoint in breakpoints:
			breakpoint.disable(self)


	def _command_ignore(self, command='ignore', breakpoint=None, num_passes=0):
		"""
		Run past breakpoint num_passes times. 
		Once count goes to zero the breakpoint activates.
		"""
		if breakpoint is None:
			return
		breakpoint.ignore(self, num_passes)


	def _command_break(self, command='break', stop_location='', stop_condition=lambda:True):
		"""
		Create a breakpoint at the given location.
		
		The stop_location can be
		 - a line in the current file
		 - a function in the current file
		 - a filename and line (i.e "shared.tools.debug:45")
		 - a filename and a function (i.e. "shared.tools.meta:getFunctionSigs")

		If a condition is provided, then the breakpoint will be ignored until true.

		If no location or condition is provided, then list all breakpoints:
		 - breakpoint location and ID
		 - number of times hit
		 - remaining ignore count
		 - conditions, if any
		 - is temporary
		"""
		raise NotImplementedError


	def _command_tbreak(self, command='tbreak', stop_location='', stop_condition=lambda:True):
		"""
		Create a temporary breakpoint at the given location. Same usage otherwise as break.
		"""
		raise NotImplementedError


	def _command_condition(self, command='condition', breakpoint=None, condition=None):
		"""
		Stop on breakpoint if condition is True
		"""
		if condition is None:
			raise RuntimeError("Condition is required for conditional breakpoints.")
		raise NotImplementedError


	def _command_commands(self, command='commands', breakpoint=None):
		"""
		Run commands when breakpoint is reached. 
		Commands entered will be assigned to this breakpoint until 'end' is seen.

		To clear a breakpoint's commands, enter this mode and enter 'end' immediately.

		Any command that resumes execution will prematurely end command list execution.
		  (This is continue, step, next, return, jump, quit)

		Entering 'silent' will run the breakpoint commands but not stop.
		"""
		if breakpoint is None:
			raise RuntimeError("In order for commands to be run on a breakpoint, a breakpoint is needed.")
		raise NotImplementedError


	#--------------------------------------------------------------------------
	# Execution control
	#--------------------------------------------------------------------------

	def _command_scram(self, command='scram'):
		"""
		Halt interdiction, monitoring, tracing, and remove from callstack and hijacked sys.
		"""
		self.SCRAM()
	_command_SCRAM = _command_scram

	def _command_release(self, command='release'):
		"""
		Stop monitoring the thread (but do not tear down)
		"""
		self.traps = set()
		self.interdicting = False
		self.monitoring = False	

	def _command_interdict(self, command='interdict'):
		"""
		Halt execution and hold for command inputs
		"""
		self.interdict()
	_command_i = _command_interdict

	def _command_monitor(self, command='monitor', step_speed=0):
		"""
		Resume execution but watch for breaks. 
		If step_speed is nonzero, wait that many seconds between steps.
		"""
		self.step_speed = step_speed
		self.monitor()
	_command_m = _command_monitor


	def _command_step(self, command='step'):
		"""
		Step into the next function in the current line (or to the next line, if done).
		"""
		self.traps.add(Step())
		self.interdicting = False
		self.monitoring = True
	_command_s = _command_step


	def _command_next(self, command='next'):
		"""
		Continue to the next line (or return statement). 
		Note step 'steps into a line' (possibly making the call stack deeper)
		  while next goes to the 'next line in this frame'. 
		"""
		self.traps.add(Next(self.current_context))
		self.interdicting = False
		self.monitoring = True
	_command_n = _command_next


	def _command_until(self, command='until', target_line=0):
		"""
		Continue until a higher line number is reached, or optionally target_line.
		"""
		self.traps.add(Until(self.current_context))
		self.interdicting = False
		self.monitoring = True
	_command_u = _command_until


	def _command_return(self, command='return'):
		"""
		Continue until the current frame returns.
		"""
		self.traps.add(Return(self.current_context))
		self.interdicting = False
		self.monitoring = True
	_command_r = _command_return


	def _command_continue(self, command='continue'):
		"""
		Resume execution until a breakpoint is reached. Clears all traps.
		"""
		self.traps = set()
		self.interdicting = False
		self.monitoring = True
	_command_c = _command_cont = _command_continue


	def _command_jump(self, command='jump', target_line=0):
		"""
		Set the next line to be executed. Only possible in the bottom frame.
		
		Use this to re-run code or skip code in the current frame.
		NOTE: You can note jump into the middle of a for loop or out of a finally clause.
		"""
		if target_line == 0:
			raise RuntimeError('Jump lines are in the active frame only, and must be within range')
		raise NotImplementedError
	_command_j = _command_jump


	#--------------------------------------------------------------------------
	# Info commands
	#--------------------------------------------------------------------------


	def _command_list(self, command='list', first=0, last=0):
		"""
		List the source code for the current file, +/- 5 lines.
		Given just first, show code +/- 5 lines around first.
		Given first and last show code between the two given line numbers.
		If last is less than first it goes last lines past the first. 
		"""
		frame = self.cursor_frame

		code_lines = CodeCache.get_lines(frame, radius=0, sys_context=self.sys)

		if not code_lines:
			self.logger.warn('Code is empty in listing: %s %d %d' % (command, first, last))
			
		if last == 0:
			if first == 0:
				start = self.cursor_frame.f_lineno - 5
				end   = self.cursor_frame.f_lineno + 5
			else:
				start = first - 5
				end   = first + 5
		else:
			if last < first:
				start = first
				end   = first + last
			else:
				start = first
				end   = last
		
		# sanity check
		if start < 0:
			start = 0
		if end >= len(code_lines):
			end = len(code_lines) - 1

		rendered_code = CodeCache._render_tabstops(code_lines[start:end])

		line_order = (int(math.log10(end)) + 1)
		fmt_line = '[ %%%dd]  %%s' % line_order
		cur_line = ' >%%%dd > %%s' % line_order
		annotated_block = '\n'.join([(cur_line 
										if (i + start + 1) == frame.f_lineno 
										else fmt_line
										) % (i + start + 1, line)
									 for i, line in enumerate(rendered_code)])
		return 'Source in "%s"\n%s' % (frame.f_code.co_filename, annotated_block)
	_command_l = _command_list


	def _command_source(self, command='source', radius=0):
		"""
		Returns the source code for the file at the cursor frame.
		Just source code lines returned by default, otherwise the starting 
		  line is also returned (to contextualize block of code).
		"""
		if radius:
			return CodeCache.get_lines_with_start(self.cursor_frame, radius=radius, sys_context=self.sys)
		else:
			return CodeCache.get_lines(self.cursor_frame, radius=radius, sys_context=self.sys)


	def _command_args(self, command='args'):
		"""
		Show the argument list to the function at the cursor frame.
		"""
		frame = self.cursor_frame
		frame_code = frame.f_code
		argnames = frame_code.co_varnames[:frame_code.co_argcount]
		return dict((name, frame.f_locals[name]) for name in argnames)
	_command_a = _command_args


	def _command_p(self, command='p', expression=''):
		"""
		(Pretty) Print the expression.
		"""
		if expression == '':
			return
		return p(self.cursor_eval(expression), directPrint=False)


	def _command_pp(self, command='pp', expression=''):
		"""
		Print the expression via pretty printing. This is actually how p works, too.
		"""
		if expression == '':
			return
		return p(self.cursor_eval(expression), directPrint=False)


	def _command_pdir(self, command='pdir', expression='', skip_private=True):
		"""
		Print the dir() command via pretty printing.
		"""
		if expression == '':
			return
		return pdir(self.cursor_eval(expression), skipPrivate=skip_private, directPrint=False)
		
		
	def _command_alias(self, command='alias', name='', command_string=''):
		"""
		Create an alias called name that executes command. 
		If no command, then show what alias is. If no name, then show all aliases.

		NOTE: The command should not be in quotes.

		Parameters can be indicated by %1, %2, and so on, while %* is replaced by all parameters.
		"""
		raise NotImplementedError


	def _command_unalias(self, command='unalias', name=''):
		"""
		Delete the specified alias.
		"""
		if not name:
			raise RuntimeError("Unalias must have a name to, well, un-alias.")
		raise NotImplementedError


	def _command_statement(self, raw_command, *tokens):
		"""
		Execute the (one-line) statement. 
		Start the statement with '!' if it starts with a command.

		To set a global variable, prefix the assignment command with `global`
		  (IPDB) global list_options; list_options['-1']
		"""
		# remove '!' or 'statement' from start first!
		raw_command = raw_command.strip()
		if raw_command.startswith('!'):
			raw_command = raw_command[1:].strip()
		elif raw_command.startswith('statement'):
			raw_command = raw_command[10:].strip()
			
		if isinstance(raw_command, (str, unicode)):
			raw_command += '\n'
		
		code = self._compile(raw_command, mode='exec')
		
		frame = self.cursor_frame
		exec code in frame.f_globals, frame.f_locals	

		# DO NOT RUN THIS - Frames can't be generated from within the Python
		#   engine, it seems, and this just... locks everything up.
		# frame = self.cursor_frame
		# thread_state = self.sys._thread_state
		# code.call(thread_state, frame)
	_command_default = _command_bang = _command_statement


	def _command_run(self, command, *args):
		"""
		Warning: NotImplementedError

		Restart the debugged program. This is not and will not be implemented.
		"""
		raise NotImplementedError("IPDB will not implement the 'run' command.")
	

	def _command_quit(self, command):
		"""
		Quit the debugger. Unlike in PDB, this will _not_ kill the program thread.
		"""
		self.shutdown()
		self.sys._restore()
	_command_shutdown = _command_die = _command_q = _command_quit


	def fork_scenario(self, **local_overrides):
		"""
		Fork another tracer off from the cursor frame to inspect as a new scenario. 
		
		Returns the new thread that is getting traced.
		
		WARNING: Other tracers may block until they exit!
		"""	
		back_reference = tracer.id
		frame = self.cursor_frame

		source = CodeCache.get_lines(frame, radius=0, sys_context=self.sys)
		
		# frame lines are one-indexed
		frame_first_line_number = frame.f_code.co_firstlineno
		frame_first_line = source[frame_first_line_number - 1]
		
		spacer = frame_first_line[0]
		
		for indent_count, c in enumerate(frame_first_line):
			# zero-index means we end on the count
			if c != spacer:
				break
		
		# increase the indent by one since the frame is actually executed
		#   inside the definition, not _on_ it.
		indent = spacer * (indent_count + 1)
		code_block = []
		for line in source[frame_first_line_number:]:
			# add any lines that are the expected indent
			if line.startswith(indent):
				code_block.append(line)
			# once we're past the def statement, break if we dedent
			elif code_block:
				break
		
		while not code_block[-1].strip():
			_ = code_block.pop(-1)
		
		head_code = [indent + line.strip() for line in """
			from shared.tools.debug.tracer import set_trace
			set_trace()
			""".splitlines() if line]
		
		code_block = head_code + code_block
		
		#CodeCache._render_tabstops(code_block)
		code = compile(textwrap.dedent('\n'.join(code_block)), '<tracer-scenario:%s>' % back_reference, 'exec')
		
		argument_names = frame.f_code.co_varnames[:frame.f_code.co_argcount]
		
		scenario_locals = local_overrides
		scenario_locals.update(dict((arg_name, frame.f_locals[arg_name]) 
							   for arg_name in argument_names))
		
		scenario_globals = frame.f_globals
		#del scenario_globals['Tracer']
		
		@async(name='Tracer Scenario: %s' % back_reference)
		def initialize_scenario(code=code, 
								scenario_globals=scenario_globals, 
								scenario_locals=scenario_locals):
			exec(code, scenario_globals, scenario_locals)
			
		return initialize_scenario()






def set_trace():
	"""Crashstop execution and begin interdiction."""
	Tracer().interdict()


def record():
	raise NotImplementedError("TODO: ADD FEATURE")
