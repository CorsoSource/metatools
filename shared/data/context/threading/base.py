"""
	Base of the threading management

"""
from shared.data.context.base import ContextManagementForContexts
from shared.data.context.config import CONTEXT_USES_SLOTS


from java.lang import Thread
from java.lang.System import identityHashCode # not used, but same as `hash()` in practice

import sys
from time import sleep



# make sure that a context can't keep itself in memory just because it's pointing to itself
from weakref import WeakValueDictionary #, WeakKeyDictionary, WeakSet

class ThreadValidation(RuntimeError): """Signal something wrong in the thread management"""

class ThreadZombie(ThreadValidation): """For when threads fail to be interrupted."""

class ThreadGuard(ThreadValidation): """Throw an exception to be handled by the calling function"""
class ContextSelfReferenceGuard(ThreadGuard): """Prevent contexts from pulling the rug out from under themselves"""



class ThreadContexts(ContextManagementForContexts):
	"""
	Wrap context management with bookkeeping to make sure that threads aren't zombies or orphans.

	Lo and behold: all under Context control's context management shall be managed by Context.    
	"""
	__module__ = shared.tools.meta.get_module_path(1)
	
	
	if CONTEXT_USES_SLOTS:
		__slots__ = (
			'_role_thread_ids',
			'_thread_id_role', 
			'_thread_references',
		)


	_THREAD_DEATH_LOOP_WAIT = 0.01 # sec
	_THREAD_DEATH_LOOP_RETRIES = 5

	_CONTEXT_THREAD_ROLE = 'context'

	
	def __init__(self, *args, **kwargs):
		self._role_thread_ids = {} # get a set of thread_ids for each role
		self._thread_id_role = {} # get a thread_id's role
		# NOTE: Can't use a WeakKeyDictionary() because it can't properly do contains    # reverse lookup

		# store the thread references for each thread_id (just the hash of the thread 
		# - that's a direct reference to the memory address of the thread)
		self._thread_references = WeakValueDictionary()
		
		super(ThreadContexts, self).__init__(*args, **kwargs)

	
	def launch(self, role, async_context_function, *args, **kwargs):
		"""Run an async function within our context!"""
		thread = async_context_function(self, *args, **kwargs)
		self._add_thread(role, thread)

	
	###########################
	# context management overrides

	def _launch_context(self):
		# assume ownership of thread once context is launched
		self._add_thread(role=None, thread=Thread.currentThread(), is_context_init=True)
		super(ThreadContexts, self)._launch_context()
	
	def _finish_context(self):
		super(ThreadContexts, self)._finish_context()
		self._cull_terminated()
	
	def _crash_context(self):
		try:
			super(ThreadContexts, self)._crash_context()
		finally:
			self._kill_threads() 
			self._scram()
	
		
	###########################
	# thread-local conveniences

	@property
	def logger(self):
		return system.util.getLogger(type(self).__name__)

	@property
	def active_roles(self):
		return frozenset(role for role in self._role_thread_ids if role)
	
	@property
	def role(self):
		return self._role()

	def _role(self, thread=None):
		return self._get_thread_role(thread)
	
	def _has_role(self, thread=None):
		try:
			role = self._get_thread_role(thread)
			return True
		except KeyError:
			return False

	def _has_threads(self, role):
		if role == _CONTEXT_THREAD_ROLE:
			role = None
		try:
			thread_ids = self._role_thread_ids[role]
			if thread_ids:
				return True
			else:
				return False
		except:
			return False


	
	@property
	def _all_threads(self):
		return frozenset(self._thread_references.values())

	@property
	def _all_role_threads(self):
		role_threads = {}
		for role, thread_ids in self._role_thread_ids.items():
			for thread_id in thread_ids:
				try:
					thread = self._thread_references[thread_id]
					if not role in role_threads:
						role_threads[role] = set()
					role_threads[role].add(thread)
				except KeyError:
					pass # already culled from weak ref dict
		return role_threads

	@property
	def _context_threads(self):
		return self._role_threads(None)
	
	def _role_threads(self, role):
		if role == self._CONTEXT_THREAD_ROLE:
			role = None
		threads = []
		for thread_id in self._role_thread_ids.get(role, set()):
			try:
				threads.append(self._thread_references[thread_id])
			except KeyError:
				pass # Weak ref culled it during iteration, probably
		return frozenset(threads)

	def _is_context_thread(self, thread=None):
		if thread is None:
			thread = Thread.currentThread()
		return self._role(thread) is None
	

	@staticmethod
	def _is_thread_terminated(thread):
		return thread.getState() == Thread.State.TERMINATED


			
	# GET/SET/DEL threads from context
	# 
	# NOTE: This should be the ONLY place _thread_role and _role_thread_ids should be referenced!
	
	def _get_thread_reference_id(self, thread):
		return hash(thread)
	
	def _set_thread_role(self, thread, role):
		if thread is None:
			thread = Thread.currentThread()
		thread_id = self._get_thread_reference_id(thread)

		self.logger.debug('[set role] %(thread)r as %(role)r with %(thread_id)s')
		
		self._thread_references[thread_id] = thread
		self._thread_id_role[thread_id] = role
		if not role in self._role_thread_ids:
			self._role_thread_ids[role] = set()
		self._role_thread_ids[role].add(thread_id)

	
	def _del_thread_role(self, thread=None):
		"""
		Remove the thread from the role tracking.

		Not that this is susceptible ot multiple threads potentially performing a purge
		of themselves at once. That's ok - the goal is to remove tracking, so if something
		else scrams those references, it really is ok. 

		In that case, it's a race condition, but one that converges on the same result,
		which means it fails safe.
		"""
		if thread is None:
			thread = Thread.currentThread()
		thread_id = self._get_thread_reference_id(thread)
		
		self.logger.debug('[del role] %(thread)r with %(thread_id)s')
		
		try:
			role = self._thread_id_role.pop(thread_id)
			assert role, 'Do not remove the hub context role'
			self._role_thread_ids[role].remove(thread_id)
		except KeyError:
			pass # already removed (race conditions possible, but safe)
		except AssertionError:
			raise ContextSelfReferenceGuard
		try:
			del self._thread_references[thread_id]
		except KeyError:
			pass # already removed (race conditions possible, but safe)
		
		# clean out role if vacated
		try:
			if not self._role_thread_ids[role]:
				del self._role_thread_ids[role]
		except KeyError:
			pass # already removed (race conditions possible, but safe)

	
	def _get_thread_role(self, thread=None):
		if thread is None:
			thread = Thread.currentThread()
		thread_id = self._get_thread_reference_id(thread)
		role = self._thread_id_role[thread_id]
		if role is None:
			return self._CONTEXT_THREAD_ROLE
		else:
			return role

	
	def _gc_thread_refs(self):
		current_thread_ids = frozenset(self._thread_references)
		for thread_id in (frozenset(self._thread_id_role) - current_thread_ids):
			try:
				del self._thread_id_role[thread_id]
			except:
				pass # already removed
		for role, thread_ids in self._role_thread_ids.items():
			thread_ids &= current_thread_ids

			
	###########################
	# thread handle bookkeeping
	
	def _add_thread(self, role, thread=None, is_context_init=False):
		"""
		Add a thread to the context.        
		"""
		self.logger.debug('[add thread] %(role)s with %(thread)r (%(is_context_init)s)')
		if role == self._CONTEXT_THREAD_ROLE: role = None
		if thread is None: thread = Thread.currentThread()
		assert role is not None or is_context_init, 'Only one context management thread allowed per context.'
		self._set_thread_role(thread, role)

	
	def _remove_thread(self, thread=None, interrupt_thread=True):
		"""
		Remove a thread from the context.
		
		Note that interrupt_thread is True by default. This is because we don't want threads doing things out of our watchful control.
		It's possible that we may _not_ want to, but it's assumed that the context controls and manages all threads related to it.
		"""
		self.logger.debug('[remove thread] %(thread)r (interrupt: %(interrupt_thread)r)')

		if thread is None: thread = Thread.currentThread()
		try:
			self._del_thread_role(thread)
		except ContextSelfReferenceGuard:
			# deal with context trying to off itself
			# don't orphan the context thread from it's own control
			if thread in self._context_threads and interrupt_thread:
				self._kill_threads()
				if interrupt_thread:
					raise KeyboardInterrupt('Context thread attempted to remove itself. Children closed and interrupting itself.')
		
		# ensure that the thread is interrupted even if cleanup failed, somehow
		# put another way, a messy context is better than zombie threads
		finally:
			if interrupt_thread:
				self._kill_thread(thread)

	###########################
	# scram functionality

	def _cull_terminated(self):
		for thread in self._all_threads:
			try:
				if self._is_context_thread(thread):
					continue # regardless of state, the holding thread doesn't cull itself
			except KeyError:
				pass # thread already culled via weakref (should be impossible, but not risking a bizarre race)
			if self._is_thread_terminated(thread):
				self._remove_thread(thread)
		self._gc_thread_refs()

	
	def _kill_threads(self):
		"""Interrupt all threads at once."""
		self.logger.warn('Killing all threads')

		theads_to_kill = self._all_threads
		for retry_attempt in range(self._THREAD_DEATH_LOOP_RETRIES):
			all_stopped = True
			for thread in theads_to_kill:
				try:
					if self._is_context_thread(thread):
						continue # don't kill the main context this way
				except KeyError:
					pass # thread already culled via weakref (should be impossible, but not risking a bizarre race)
				
				if self._is_thread_terminated(thread):
					continue
				
				all_stopped = False
				
				try:
					# hammer interrupt harder each loop in case of aggresive
					# (and potentially inappropriate) exception handling
					for i in range(retry_attempt+1):
						thread.interrupt()
				except:
					pass
			# break out of retry loop if all threads are terminated
			if all_stopped:
				break
			else:
				sleep(self._THREAD_DEATH_LOOP_WAIT)
		else:
			undead_threads = sorted(
				thread.getName() for thread in theads_to_kill 
				if not self._is_thread_terminated(thread)
			)
			if undead_threads:
				raise ThreadZombie('These threads did not terminate in time: %r' % (undead_threads))


	def _kill_thread(self, thread):
		"""Interrupt a single thread."""
		for retry_attempt in range(self._THREAD_DEATH_LOOP_RETRIES):
			if self._is_thread_terminated(thread):
				break
			self.logger.warn('[>%d] Killing thread: %r' % (retry_attempt + 1, thread,))
			try:
				# this isn't merely "trying harder" ;)
				# if we are trying to KILL -9 a thread, we may need to overcome
				# poorly set up exception handling that may gobble up the interrupt
				# so this will hammer it harder every loop, hopefully before all of
				# them can be caught and handled.
				for i in range(retry_attempt+1):
					thread.interrupt()
			except:
				pass
			sleep(self._THREAD_DEATH_LOOP_WAIT)
		else:
			if not self._is_thread_terminated(thread):
				raise ThreadZombie('Thread failed to be interrupted and stoped: %r' % (thread,))
		# thread interrupted and stopped.

		
	def _scram(self):
		try:
			self._kill_threads()
		except ThreadZombie as error:
			self.logger.error('Interrupt failed! Thread(s) may be a zombie: %r' % (error,))
		except (Exception,JavaException) as error:
			exc_type, exc_val, exc_tb = sys.exc_info()
			self.logger.error('Interrupt failed! Thread(s) may still be running.'
							  '\nFailure due to: %r'
							  '\n%s' % (error, formatted_traceback(exc_val, exc_tb)))
		finally:
			terminate_self = False
			for context_thread in self._context_threads:
				if Thread.currentThread() is context_thread:
					terminate_self = True
				else:
					context_thread.interrupt()
			# do this last (so the loop can be finished terminating any other tracked holding threads)
			# there may be other threads containing the context, but they're not in a context management mode
			if terminate_self:
				raise KeyboardInterrupt('Context requested to scram itself. Interrupting.')