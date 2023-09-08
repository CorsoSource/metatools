"""
    Class convenience methods for lookup and control

    What to do after a context is hoisted and running?
    How do we get a reference to orphaned contexts?
    
    Simply look them up here!

"""
from shared.data.context.utility import re_match_groupdict, findThreads, TypeNotFoundError, get_from_thread
import re




class MetaContext(type):
    __module__ = shared.tools.meta.get_module_path(1)
    
    # set to some dict-like thing that returns based on [identifier] or the slice [identifier:class_name]
    _CONTEXT_CACHE = None # ExtraGlobal (scoped to class), list/tuple, or a dict

    _META_LOGGER = shared.tools.logging.Logger('MetaContext')

    @property
    def _meta_all_threads(cls):
        """Reimplementing for the class methods (without resorting to metaclass properties)"""
        # default the filter so it can't find just *any* threads    
        thread_base_part = cls._thread_base_name()
        assert 'base' in cls._THREAD_NAME_PATTERN
        name_pattern = self._THREAD_NAME_SEPARATOR.join(
            '(?P<%s>[^%s]+)' % (part, cls._THREAD_NAME_SEPARATOR) for part in cls._THREAD_NAME_PATTERN
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
        assert 'base' in cls._THREAD_NAME_PATTERN and 'role' in cls._THREAD_NAME_PATTERN
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

    def __contains__(cls):
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

    def scram_pending(cls):
        theads_to_kill = findThreads(cls._thread_match_pattern(pending=True))
        
        for retry_attempt in range(cls._THREAD_DEATH_LOOP_RETRIES):
            for thread in theads_to_kill:
                if not cls._is_thread_terminated(thread):
                    thread.interrupt()
            if all(cls._is_thread_terminated(thread) for thread in theads_to_kill):
                break
            sleep(cls._THREAD_DEATH_LOOP_WAIT)
        else:
            undead_threads = sorted(
                thread.getName() for thread in theads_to_kill 
                if not self._is_thread_terminated(thread)
            )
            raise ThreadZombie('Some pending threads did not terminate in time: %r' % (undead_threads))