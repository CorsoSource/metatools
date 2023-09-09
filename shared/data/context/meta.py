"""
	Class convenience methods for lookup and control

	What to do after a context is hoisted and running?
	How do we get a reference to orphaned contexts?
	
	Simply look them up here!

"""
from shared.data.context.utility import re_match_groupdict, findThreads, TypeNotFoundError, get_from_thread
from shared.data.context.config import CONTEXT_USES_SLOTS
from shared.data.context.threading.base import HeadlessContext


import re




class MetaContext(type):
	__module__ = shared.tools.meta.get_module_path(1)
	
	# set to some dict-like thing that returns based on [identifier] or the slice [identifier:class_name]
	_CONTEXT_CACHE = None # ExtraGlobal (scoped to class), list/tuple, or a dict

	_META_LOGGER = shared.tools.logging.Logger('MetaContext')



	def __new__(metacls, class_name, class_bases, class_configuration):
		if CONTEXT_USES_SLOTS:
			# merge slots from subclasses
			slots = set(class_configuration.get('__slots__', tuple()))
			for subclass in class_bases:
				slots.update(getattr(subclass, '__slots__', tuple()))
				
			class_configuration['__slots__'] = slots
		
		new_class = super(MetaContext, metacls).__new__(metacls, class_name, class_bases, class_configuration)
		return new_class


	@property
	def _meta_all_threads(cls):
		"""Reimplementing for the class methods (without resorting to metaclass properties)"""
		# default the filter so it can't find just *any* threads    
		thread_base_part = cls._thread_base_name()
		assert 'base' in cls._THREAD_NAME_PARTS
		name_pattern = self._THREAD_NAME_SEPARATOR.join(
			'(?P<%s>[^%s]+)' % (part, cls._THREAD_NAME_SEPARATOR) for part in cls._THREAD_NAME_PARTS
		)
		for thread in findThreads(name_pattern):
			thread_name = thread.getName()
			match_dict = re_match_groupdict(name_pattern, thread_name, re.I)
			if match_dict['base'] == thread_base_part:
				yield thread

	@property
	def _meta_context_threads(cls):
		"""Reimplementing for the class methods (without resorting to metaclass properties)"""
		# default the filter so it can't find just *any* threads    
		thread_base_part = cls._thread_base_name()
		assert 'base' in cls._THREAD_NAME_PARTS and 'role' in cls._THREAD_NAME_PARTS
		for thread in findThreads(cls._thread_match_pattern()):
			thread_name = thread.getName()
			match_dict = re_match_groupdict(cls._thread_match_pattern(), thread_name, re.I)
			if match_dict['base'] == thread_base_part and match_dict['role'] == cls._CONTEXT_THREAD_ROLE:
				yield thread
	
	def __getitem__(cls, identifier):
		# for direct lookup (direct reference)
		if cls._CONTEXT_CACHE:
			try:
				if cls._CONTEXT_CACHE is ExtraGlobal:
					return ExtraGlobal[identifier:cls._thread_base_name()]
				else:
					raise NameError('ExtraGlobal not in use.')
			except NameError:
				if isinstance(cls._CONTEXT_CACHE, (list, tuple)):
					for entry in cls._CONTEXT_CACHE:
						if entry.identifier == identifier:
							return entry
				else:
					return cls._CONTEXT_CACHE[identifier]
		# for indirect search lookup (search threads)
		else:
			for thread in cls._meta_context_threads:
				try:
					context = get_from_thread(thread, object_type=cls)
					if context.identifier == identifier:
						return context
				except TypeNotFoundError:
					pass

	def __iter__(cls):
		# for direct lookup (direct reference)
		if cls._CONTEXT_CACHE:
			try:
				if cls._CONTEXT_CACHE is ExtraGlobal:
					for identifier in ExtraGlobal.keys(scope=cls._thread_base_name()):
						yield ExtraGlobal[identifier:cls._thread_base_name()]
				else:
					raise NameError('ExtraGlobal not in use.')
			except NameError:
				if isinstance(cls._CONTEXT_CACHE, (list, tuple)):
					for entry in cls._CONTEXT_CACHE:
						yield entry
				else:
					for identifier in cls._CONTEXT_CACHE:
						yield cls._CONTEXT_CACHE[identifier]
		# for indirect search lookup (search threads)
		else:
			for thread in cls._meta_context_threads:
				try:
					context = get_from_thread(thread, object_type=cls)
					yield context
				except TypeNotFoundError:
					pass

	def __contains__(cls, identifier):
		if cls._CONTEXT_CACHE:
			try:
				if cls._CONTEXT_CACHE is ExtraGlobal:
					try:
						context = ExtraGlobal[identifier:cls._thread_base_name()]
						return True
					except KeyError:
						return False
				else:
					raise NameError('ExtraGlobal not in use.')
			except NameError:
				if isinstance(cls._CONTEXT_CACHE, (list, tuple)):
					for entry in cls._CONTEXT_CACHE:
						if entry.identifier == identifier:
							return True
					return False
				else:
					return identifier in cls._CONTEXT_CACHE
		# for indirect search lookup (search threads)
		else:
			for thread in cls._meta_context_threads:
				try:
					context = get_from_thread(thread, object_type=cls)
					if context.identifier == identifier:
						return True
				except TypeNotFoundError:
					pass
			return False


	def stop_all(cls):
		failed = []
		for context in cls:
			try:
				context.stop_loop()
			except:
				failed.append(context)
		if failed:
			self._META_LOGGER.warn("Some contexts may not have stopped: %r" % (failed,))



class ScrammingMetaContext(MetaContext):
	"""
	

	"""

	def _check_undead(cls, threads):
		# a final pause before a final death toll check...
		sleep(cls._THREAD_DEATH_LOOP_WAIT * cls._THREAD_DEATH_LOOP_RETRIES)

		undead_threads = sorted(
			thread.getName() for thread in theads_to_kill 
			if not cls._is_thread_terminated(thread)
		)
		if undead_threads:
			raise ThreadZombie('Some threads did not terminate in time: %r' % (undead_threads))


	def _interrupt_threads(cls, theads_to_kill):
		for retry_attempt in range(cls._THREAD_DEATH_LOOP_RETRIES):
			for thread in theads_to_kill:
				if not cls._is_thread_terminated(thread):
					thread.interrupt()
			if all(cls._is_thread_terminated(thread) for thread in theads_to_kill):
				break
			sleep(cls._THREAD_DEATH_LOOP_WAIT)
		else:
			cls._check_undead(threads_to_kill)


	def SCRAM_ALL(cls, pending=True):
		"""
		Indiscriminate.

		This is slightly different from scramming each context individually.
		Here, threads are gathered and then an interrupt is hammered across all as a bulk group.

		Honestly, I'm not sure it's better than one context at a time. In theory it blankets
		interrupts faster and wider, but it won't *hammer* the interrupts quite as fast per 
		retry loop. But it IS simpler, so that's likely a win when simply murdering the processes
		is what matters.
		"""
		try:
			# stop pending first, then move onto the other contexts
			if pending:
				threads_to_kill = cls._find_threads(pending=True)
				cls._interrupt_threads(threads_to_kill)
		finally:
			# note that this does not stop all, but rather scrams every associated thread!
			threads_to_kill = cls._find_threads()
			cls._interrupt_threads(threads_to_kill)


	def SCRAM(cls, identifier):
		# first, try to have the context scram itself
		try:
			context = cls[identifier]
			context._scram()
		except KeyError:
			pass # no context object retrieved - resort to killing threads by name
		except Exception:
			pass # something went wrong -_- resort to killing threads by name

		# then verify that it's done
		try:
			try:
				# first try to tear down only the contexts
				# assume the death loop wait is configured to be sufficient
				threads_to_kill = cls._find_threads(identifier=identifier, role=cls._CONTEXT_THREAD_ROLE)
				if not threads_to_kill:
					raise HeadlessContext
				else:
					cls._interrupt_threads(threads_to_kill)
			except HeadlessContext:
				# if there are no contexts, check if there's any other roles live
				threads_to_kill = cls._find_threads(identifier=identifier)
				# ... if not, then good! we're done :D
				if not threads_to_kill:
					return
				# ... otherwise attempt to kill them
				else:
					cls._interrupt_threads(threads_to_kill)
				# if after all that there are still threads, throw an error
				if cls._find_threads(identifier=identifier):
					raise ThreadZombie
		except ThreadZombie:
			# final check
			threads_to_kill = cls._find_threads(identifier=identifier)
