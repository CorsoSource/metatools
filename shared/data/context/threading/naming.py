"""
    Threads should be named.
    
    Not just for documentation, but it's safer. Even if references
    are lost or things go out of scope, the JVM can always search 
    for a thread. We'll use this at the metaclass layer to be
    absolutely sure we're iterating over all live contexts - even
    if the scope of the module isn't the same for each context
    (as in different modules/threads/subsystems load it in separately)

"""
from shared.data.context.utility import findThreads, re_match_groupdict, random_id
from shared.data.context.threading.base import ThreadContexts, Thread

import re



class NamedThreadContexts(ThreadContexts):
    """
    Add additional context control via named threads.

    Honestly, this should always be used over the base just because naming your stuff is better 
    than just throwing things to the wind and hoping they don't get lost.    
    """
    __module__ = shared.tools.meta.get_module_path(1)
    
    _THREAD_BASE_NAME = None
    _THREAD_NAME_SEPARATOR = '-'
    _THREAD_NAME_PATTERN = 'base-identifier-role-counter'.split(_THREAD_NAME_SEPARATOR)
    _AUTO_NAME_THREADS = True


    def __init__(self, identifier=None, *args, **kwargs):
        self._identifier = identifier or random_id()
        self._role_threads_counter = {}
        super(NamedThreadContexts, self).__init__(*args, **kwargs)

    @property
    def identifier(self):
        return self._identifier

    @identifier.setter
    def identifier(self, new_id):
        raise ValueError("No changing an identifier after init - too much stuff and contexts already know about it.")

    @classmethod
    def _thread_base_name(cls):
        return (cls._THREAD_BASE_NAME or cls.__name__)

    @classmethod
    def _thread_match_pattern(cls, pending=False):
        return cls._THREAD_NAME_SEPARATOR.join((['PENDING'] if pending else [])
            + ['(?P<%s>[^%s]+)' % (part, cls._THREAD_NAME_SEPARATOR) for part in cls._THREAD_NAME_PATTERN]
        )

    @classmethod
    def _thread_name_format(self, pending=False):
        return self._THREAD_NAME_SEPARATOR.join((['PENDING'] if pending else [])
            + ['%%(%s)s' % part for part in self._THREAD_NAME_PATTERN]
        )

    def _thread_name_parts(self, role):
        return {
                'base': self._thread_base_name(),
                'identifier': self._identifier,
                'role': role,
            }
    
    def _name_thread(self, thread=None):
        if thread is None: thread = Thread.currentThread()
        assert self._has_role(thread), 'Thread naming should happen after role is resolved and set'
        try:
            name = self._thread_name_format() % self._thread_name_parts(role=self._role(thread))
            thread.setName(name)
        except KeyError:
            raise RuntimeError('Bizarre race condition in NamedThreadContexts where thread was culled from roles before getting named.')


    def __enter__(self):
        # take ownership of the thread this context is running in
        self._add_thread(None, Thread.currentThread(), is_context_init=True)
        super(NamedThreadContexts, self).__enter__()
        return self

    
    def _find_threads(self, **part_filter):
        # default the filter so it can't find just *any* threads
        if not 'base'       in part_filter: part_filter['base'] = self._thread_base_name()
        assert part_filter['base'], 'Must have a base pattern to filter threads on!'
        if not 'identifier' in part_filter: part_filter['identifier'] = self._identifier
        # allow an explicit part filter for other contexts
        if not part_filter['identifier']:   part_filter['identifier'] = '.*'
        
        for thread in findThreads(self._thread_match_pattern()):
            thread_name = thread.getName()
            for key, part in re_match_groupdict(self._thread_match_pattern(), thread_name, re.I).items():
                # match by default (pre-filtering set above)
                filter_part = part_filter.get(key, '.*')
                if not re.match(filter_part, part):
                    break # skip this thread since it doesn't match
            else:
                # only if all parts match will the thread be provided
                yield thread


    def _add_thread(self, role, thread=None, is_context_init=False):
        super(NamedThreadContexts, self)._add_thread(role, thread, is_context_init)
        if self._AUTO_NAME_THREADS:
            self._name_thread(thread)


    @property
    def _all_threads(self):
        """Widen the search to include all threads."""
        all_found_threads = frozenset(
            thread 
            for thread
            in self._find_threads(base=self._thread_base_name(), identifier=self._identifier)
            if not self._is_thread_terminated(thread)
        )
        tracked_threads = frozenset(
            thread 
            for thread
            in frozenset(self._thread_references.values())
            if not self._is_thread_terminated(thread)
        )
        assert all_found_threads >= tracked_threads, (
            'Warning: Naming convention was broken. Context-tracked thread not found!'
            '\n\n\tIn %r the convention broke with %r' % (self, 
                sorted(t.getName() for t in (tracked_threads - all_found_threads))
            ))
        return all_found_threads

    def __repr__(self):
        return '<%s %s>' % (type(self).__name__, self.identifier)