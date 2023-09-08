"""
    The core context example class

"""
from shared.data.context.utility import DictLikeAccessMixin
from shared.data.context.threading.naming import NamedThreadContexts
from shared.data.context.threading.logging import NamedThreadSpecificLogging
from shared.data.context.threading.polling import EventLoop, RoleSpecificEventLoop, poll
from shared.data.context.threading.signals import Signalling, EventLoopSignalProcessing, RoleSpecificEventLoopStopSignaling

from shared.data.context.meta import MetaContext



class Context(
    # event loop reactions
    RoleSpecificEventLoopStopSignaling,
    
    # event loop control
    EventLoopSignalProcessing,
    Signalling,
    
    # event loops
    RoleSpecificEventLoop,
    EventLoop,
    
    # core thread control
    NamedThreadSpecificLogging,
    NamedThreadContexts,
    
    # utility
    DictLikeAccessMixin,
    ):
    __module__ = shared.tools.meta.get_module_path(1)
    __metaclass__ = MetaContext

    def initialize_context(self, *init_args, **init_kwargs):
        raise NotImplementedError

    def launch_context(self):
        raise NotImplementedError

    def finish_context(self):
        pass

    def crash_context(self):
        pass

        
    def poll_context(self):
        raise NotImplementedError()
    
    
    @staticmethod
    def poll(role):
        """Convenience method to make sure decorator is available"""
        return poll(role)
        



def _run_tests():

    class TestContext(Context):
        
        def initialize_context(self, one=0, two=0):
            self.one = 0
            self.two = 0
    
        def launch_context(self):
            self.logger.trace('in %(self)r launch_context')
            self.poll_one()
            self.poll_two()
            self.poll_two()
        
        def poll_context(self):
            if self.one > self.two:
                self.logger.debug('Two seems to have reset. Fast forwarding.')
                self.two = self.one*2
    
        @poll('one')
        def poll_one(self):
            self.one += 1
    
        @poll('two')
        def poll_two(self):
            self.two += 2
    
        def handle_signal_two(self, signal):
            self.logger.debug('Signal sent to [two]: %(signal)r')
            if signal == 'reset':
                self.two = 0
    
    raise NotImplementedError