"""
    Classes to make adding things to the Ignition runtime easier

"""
from uuid import UUID


__all__ = ['RuntimeAddition']


def nop(*args, **kwargs):
    pass


class RuntimeAddition(object):
    _cls_static_uuid = None
    
    _EVENT_NAME_TYPES = 'mouse action'.split()

    def __init__(self, configuration=None):
        super(RuntimeAddition, self).__init__()
        self._config = configuration or {}

        for possible_attribute, value in self._config.items():
            if not possible_attribute in self._EVENT_NAME_TYPES:
                try:
                    getattr(self, 'set' + possible_attribute.capitalize())(value)
                except AttributeError:
                    pass

        # Generalized for simple convenience
        #   Don't configure mouse events if the class combined with RuntimeAddition 
        #   doesn't support mouse events.
        # That would be silly.
        # This covers the swing components in general.
        if 'mouse' in self._config:
            mouse_listener = MouseReaction(configuration=self._config['mouse'])
            self.addMouseListener(mouse_listener)
            
        if 'action' in self._config:
            action_listener = ActionReaction(configuration=self._config['action'])
            self.addActionListener(action_listener)
            
            
    def _call_or_iterate_calls(self, config_key, event):
        todo = self._config.get(config_key, nop)
        try:
            for call in todo:
                print 'iterating %s with %r' % (config_key, call)
                call(event)
        except TypeError:
            print 'iteration failed, calling %r' % (todo,)
            todo(event)
            

    @classmethod
    def isInstance(cls, something):
        assert cls._cls_static_uuid, "Listener classes must have a hard-coded uuid set for sanity's sake."
        try:
            if cls._cls_static_uuid == something._cls_static_uuid:
                return True
        except:
            # name-based check (perhaps less safe)
            if ('$%s$' % cls.__name__) in repr(something):
                return True
        return False


from java.awt.event import MouseAdapter, MouseEvent, MouseWheelEvent 

class MouseReaction(RuntimeAddition, MouseAdapter):
    _cls_static_uuid = UUID('51ad3eb6-737a-4cfb-96ac-fc29f2cb10b5')

    def mouseClicked(self, mouse_event):
        assert isinstance(mouse_event, MouseEvent)
        self._call_or_iterate_calls('clicked', mouse_event)

    def mouseDragged(self, mouse_event):
        assert isinstance(mouse_event, MouseEvent)
        self._call_or_iterate_calls('dragged', mouse_event)

    def mouseEntered(self, mouse_event):
        assert isinstance(mouse_event, MouseEvent)
        self._call_or_iterate_calls('entered', mouse_event)

    def mouseExited(self, mouse_event):
        assert isinstance(mouse_event, MouseEvent)
        self._call_or_iterate_calls('exited', mouse_event)

    def mouseMoved(self, mouse_event):
        assert isinstance(mouse_event, MouseEvent)
        self._call_or_iterate_calls('moved', mouse_event)

    def mousePressed(self, mouse_event):
        assert isinstance(mouse_event, MouseEvent)
        self._call_or_iterate_calls('pressed', mouse_event)
        
    def mouseReleased(self, mouse_event):
        assert isinstance(mouse_event, MouseEvent)
        self._call_or_iterate_calls('released', mouse_event)

    def mouseWheelMoved(self, wheel_event):
        assert isinstance(wheel_event, MouseWheelEvent)
        self._call_or_iterate_calls('wheel', wheel_event)


from java.awt.event import ActionListener, ActionEvent

class ActionReaction(RuntimeAddition, ActionListener):
    _cls_static_uuid = UUID('c6f3836e-aa92-4489-b796-4f5834adbcc0')

    def actionPerformed(self, action_event):
        assert isinstance(action_event, ActionEvent)
        self._call_or_iterate_calls('performed', action_event)  
    
