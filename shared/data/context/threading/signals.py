"""
	Signaling support
	
	Allow context to contact child processes

"""
from uuid import uuid1
import functools

from shared.data.context.base import ContextManagementForContexts
from shared.data.context.utility import async, JavaException, apply_jitter
from shared.data.context.threading.base import ThreadContexts, ThreadZombie
from shared.data.context.threading.polling import EventLoop, RoleSpecificEventLoop
from shared.data.context.config import CONTEXT_USES_SLOTS


class ContextSignal(Exception): """A signal for use withint a context, often between its roles."""
class LatchedSignal(ContextSignal): """This signal will be removed reinserted when popped until removed."""

# role signals
class StopSignal(StopIteration, LatchedSignal): """Signal that all threads for the role should stop."""
class StopTimeout(ThreadZombie): """A type of zombie, the thread timed out while waiting for it to stop itself gracefully."""

class RestartSignal(StopIteration, LatchedSignal): """Signal that the role should stop and let the context know that it should restart."""




class Signalling(ContextManagementForContexts):
	__module__ = shared.tools.meta.get_module_path(1)
	
	if CONTEXT_USES_SLOTS:
		__slots__ = (
			'_signals',
		)


	def __init__(self, *args, **kwargs):
		self._signals = {}
		super(Signalling, self).__init__(*args, **kwargs)
	
	def _new_message_id(self):
		"""Generated a new message id. This is a UUID which is sequential, useful as a random ordered key for dicts."""
		return uuid1(node=None, clock_seq = hash(self))

	
	def signal(self, role, message):
		"""Notify the role of a message."""
		if role is None:
			role = self._CONTEXT_THREAD_ROLE
		if role not in self._signals:
			self._signals[role] = {}
		self._signals[role][self._new_message_id()] = message

	
	def cancel_signal(self, role, message):
		if role is None:
			role = self._CONTEXT_THREAD_ROLE
		for key in frozenset(self._signals[role]):
			try:
				# note: yes, this means cancelling a signal doesn't dequeueue it.
				# signals aren't a queue - they act like one out of neccesity,
				# but they're meant to be used directly
				if self._signals[role][key] == message:
					del self._signals[role][key]
			except:
				pass # already missing

	
	def _pop_signal(self, role):
		while role in self._signals:
			try:
				next_key = min(frozenset(self._signals[role].keys()))
				signal = self._signals[role].pop(next_key)
				if isinstance(signal, LatchedSignal):
					self._signals[role][next_key] = signal
				if not self._signals[role]:
					del self._signals[role]
				return signal
			except (KeyError, ValueError):
				# if it's already been popped off, assume another thread of the same role took it
				# and simply try again
				pass
		return None


class EventLoopSignalProcessing(
		Signalling,
		EventLoop,
	):
	__module__ = shared.tools.meta.get_module_path(1)
	
	def poll_context_signal(self, signal):
		"""
		Override to customize signal handling for 
		
		"""
		pass

	def _method_polling_loop_pre_iter(self, role_method, *args, **kwargs):
		role = self.role
		
		# before running, check if any signals have been thrown
		signal = self._pop_signal(role)
		if signal is not None:
			# rethrow if the signal is an instance of an Exception...
			if isinstance(signal, Exception):
				raise signal
			else:
				try: # ... or if an unqualified exception was passed in - throw it!
					if issubclass(signal, Exception):
						raise signal
				except TypeError:
					pass # not an Exception (and not an instance of one)
			
			# IFF not an Exception or an instance of one, treat it as a message to be handled
			# Note that this will be called _within_ the thread of that role
			method_signal_handler = getattr(self, role_method.__name__ + '_signal', None)
			role_signal_handler = getattr(self, 'handle_signal_' + role.lower(), None)
		
			if method_signal_handler:
				# handle signal for this method if it has specialized needs
				method_signal_handler(signal)
			elif role_signal_handler:
				# handle signal for this role if it's available
				role_signal_handler(signal)
			else:
				raise NotImplementedError('Signal handler missing for %r (or %r) given %r' % (role, role_method.__name__, signal))
		
		super(Signalling, self)._method_polling_loop_pre_iter(role_method, *args, **kwargs)



class EventLoopStopSignal(EventLoopSignalProcessing):
	__module__ = shared.tools.meta.get_module_path(1)
	
	_DEFAULT_ROLE_STOP_WAIT = 3 * EventLoopSignalProcessing._EVENT_LOOP_DELAY # seconds


	def stop_loop(self):
		self.signal(self._CONTEXT_THREAD_ROLE, StopSignal)
	
	def _finish_context(self):
		super(EventLoopStopSignal, self)._finish_context()
		self._stop_roles()
		self._cull_terminated()

	@property
	def _stop_wait_delay(self):
		return self._DEFAULT_ROLE_STOP_WAIT
	
	@property
	def _stop_wait_max_delay(self):
		return self._DEFAULT_ROLE_STOP_WAIT * 1.1


	def _stop_role(self, role):
		self.signal(role, StopSignal)
		now = datetime.now()
		delay = timedelta(seconds=self._stop_wait_delay)
		while datetime.now() < (now + delay):
			# check if all the threads have terminated
			if all([self._is_thread_terminated(thread) 
					for thread
					in self._role_threads(role)
				   ]):
				return
			sleep(self._EVENT_LOOP_DELAY / 2.0)
		raise StopTimeout("""Not all threads stopped: %r""" % (
			[thread.getName() 
			 for thread in self._role_threads(role)
			 if not self._is_thread_terminated(thread)
			],
		))
			
	def _stop_roles(self):
		for role in self.active_roles:
			self.signal(role, StopSignal)
		now = datetime.now()
		delay = timedelta(seconds=self._stop_wait_max_delay)
		while datetime.now() < (now + delay):
			# check if all the threads have terminated
			if all([self._is_thread_terminated(thread)
					for role, threads in self._all_role_threads.items()
					for thread in threads
					if role # skip main context handler, since that's probably what called for this
				   ]):
				return
			sleep(self._EVENT_LOOP_DELAY / 2.0)
		raise StopTimeout("""Not all threads stopped: %r""" % (
			[thread.getName() 
			 for role, threads in self._all_role_threads.items()
			 for thread in threads
			 if not self._is_thread_terminated(thread)
			],
		))



class RoleSpecificEventLoopStopSignaling(
		EventLoopStopSignal, 
		RoleSpecificEventLoop,
	):
	__module__ = shared.tools.meta.get_module_path(1)

	if CONTEXT_USES_SLOTS:
		__slots__ = (
			'_role_stop_wait_delays',
		)
	

	def __init__(self, *args, **kwargs):
		self._role_stop_wait_delays = {}
		super(RoleSpecificEventLoopStopSignaling, self).__init__(*args, **kwargs)

	@property
	def _stop_wait_delay(self):
		delay = self._role_stop_wait_delay(self.role)
		if self._EVENT_LOOP_JITTER:
			offset = delay * self._EVENT_LOOP_JITTER
			delay += 2* offset
		return delay
		
	def _role_stop_wait_delay(self, role):
		delay = self._role_stop_wait_delays.get(role, self._DEFAULT_ROLE_STOP_WAIT)
		if self._EVENT_LOOP_JITTER:
			offset = delay * self._EVENT_LOOP_JITTER
			delay += 2* offset
		return delay

	@property
	def _stop_wait_max_delay(self):
		return max(self._role_stop_wait_delay(role) for role in self.active_roles)

	def _set_role_stop_wait_delay(self, role, delay=None):
		if delay is None:
			delay = self._DEFAULT_ROLE_STOP_WAIT
		if isinstance(delay, timedelta):
			delay = delay.total_seconds()
		self._role_stop_wait_delays[role] = delay


