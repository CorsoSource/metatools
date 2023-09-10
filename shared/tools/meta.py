"""
	Utilities for Ignition introspection.

	WARNING: These provide easy access to wildly powerful objects. Use caution!

	And have fun!

	The object retrieval functions reach backwards in the Python call stack. It's useful
	  to keep in mind that low number call stack frame numbers are closer to the most recent.
"""


import math,re, sys
import java.lang.Class as JavaClass


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'

__all__ = [] # This is meant to be empty. No `from corso.meta import *`!


GLOBAL_MESSAGE_PROJECT_NAME = None #'global'


class MetaSingleton(object):
	"""Use this as a base class for a metaclass. It will exist without instances.

	We'll almost never _actually_ want a singleton in Python, but we have a weird situation
	  in Jython. In our case, we occasionally want to make some truly single objects,
	  since a number of guarantees from the global interpreter lock (GIL) just don't exist
	  here. Worse, if something is going to be a _true_ singleton, we'll want the control
	  a metaclass provides. This leads to the likely scenario we don't want _anything_
	  to be generated and just use it as a fake module (which again, isn't _quite_ possible
	  in our environment otherwise).

	TL;DR: the Ignition environment is a bit special.
	"""

	def __new__(cls):
		raise NotImplementedError("%s does not support instantiation." % cls.__name__)

	def __init__(cls):
		raise NotImplementedError("%s does not support instantiation." % cls.__name__)

	def __setattr__(cls, key, value):
		raise AttributeError("%s attributes are not mutable. Use methods to manipulate them." % cls.__name__)


def sentinel(iterable, stopValue):
	"""A helper to make it simpler to implement sentinel values more idomatically.
	This is a good way to replace a while True loop, removing the need for a break-on-value clause.

	>>> [i for i in iter((x for x in range(5)).next, 3)]
	[0, 1, 2]
	>>> [i for i in sentinel(range(5), 3)]
	[0, 1, 2]
	"""
	return iter((x for x in iterable).next, stopValue)


def getIgnitionContext():
	try:
		if system.util.getSystemFlags() & system.util.DESIGNER_FLAG:
			return getDesignerContext()
		else:
			return getGatewayContext()
	except:
		return getGatewayContext()


def getGatewayContext():
	"""Attempts to get the gateway context."""
	from com.inductiveautomation.ignition.gateway import IgnitionGateway
	return IgnitionGateway.get()


def getDesignerContext(anchor=None):
	"""Attempts to grab the Ignition designer context.
	This is most easily done with a Vision object, like a window.
	If no object is provided as a starting point, it will attempt to
	  get one from the designer context.
	"""
	from com.inductiveautomation.ignition.designer import IgnitionDesigner

	if anchor is None:
		try:
			return IgnitionDesigner.getFrame().getContext()
		except:
			for windowName in system.gui.getWindowNames():
				try:
					anchor = system.gui.getWindow(windowName)
					break
				except:
					pass
			else:
				raise LookupError("No open windows were found, so no context was derived by default.")

	try:
		anchor = anchor.source
	except AttributeError:
		pass
		# Just making sure we've a live object in the tree, not just an event object

	for i in range(50):
		if anchor.parent is None:
			break
		else:
			anchor = anchor.parent

		if isinstance(anchor,IgnitionDesigner):
			break
	else:
		raise RuntimeError("No Designer Context found in this object's heirarchy")

	context = anchor.getContext()
	return context


def get_module_path(depth=1):
	"""Return the module path in the calling context's scope.
	
	returns something like `shared.tools.meta` (if it were called in this module)
	"""
	return sys._getframe(depth).f_code.co_filename[8:-1]

def currentStackDepth(maxDepth=100):
	"""Returns the calling function's stack depth.
	The easiest way to do this is to simply scan the stack
	  until the function declares the end of it by ValueError.
	Remember: 0 is THIS frame, 1 is the previous calling frame,
	  and there's no globally available stack depth value or length.

	For safety's sake, this will stop at maxDepth.

	From https://stackoverflow.com/a/47956089
	"""
	for size in range(2,maxDepth):
		try:
			_ = sys._getframe(size)
			size += 1
		except ValueError:
			return size - 1 # ignore this called frame
	else:
		return None


def stackRootFrame(maxDepth=100):
	"""Returns the calling function's stack depth.
	The easiest way to do this is to simply scan the stack
	  until the function declares the end of it by ValueError.
	Remember: 0 is THIS frame, 1 is the previous calling frame,
	  and there's no globally available stack depth value or length.
	For safety's sake, this will stop at maxDepth.
	From https://stackoverflow.com/a/47956089
	"""
	frame = sys._getframe()
	while frame.f_back:
		frame = frame.f_back
	return frame



def get_perspective_self():
	"""
	Reach up to the root of the call stack and grab the Perspective object that kicked it all off.	
	"""
	try:
		root_frame = stackRootFrame()
		self = root_frame.f_locals.get('self', None)
		self_type_fqn = repr(type(self))[7:-2]
		assert self_type_fqn.startswith('com.inductiveautomation.perspective.'), 'Not obviously the Perspective component wrapper'
		return self
	except:
		return None # something out of context happened, so simply fail the attempt


def isJavaObject(o):
	"""Walk up the object inheritance heirarchy to determine if the object is Java-based"""
	cutoff = 10
	
	oType = o
	while cutoff:
		cutoff -= 1
		oType = type(oType)

		if oType is JavaClass:
			return True

		if oType is type:
			return False

	raise RuntimeError('Checking object type of "%s" exceeded recursion depth' % repr(o)[:40])


def isPythonObject(o):
	"""Walk up the object inheritance heirarchy to determine if the object is Python-based"""
	return not isJavaObject(o)


def getObjectName(o, estimatedDepth=None, startRecent=True, ignore_names=set()):
	"""Get an item's name by finding its first reference in the stack.

	If an estimatedDepth is provided, the search will start there,
	  scanning from that frame and go in the direction startRecent implies.
	  (If startRecent is True, it will scan from the estimatedDepth
	   towards the maximum stack depth, going up the call tree.)
	"""
	# if no shortcut is provided, start at the furthest point
	if estimatedDepth is None:
		estimatedDepth = 1 if startRecent else currentStackDepth()-1
	try:
		while True:
			frame = sys._getframe(estimatedDepth)
			for key,value in frame.f_locals.items():
				if value is o and not key in ignore_names:
					return key
			estimatedDepth += 1 if startRecent else -1
	except ValueError:
		return None


def getObjectByName(objName, estimatedDepth=None, startRecent=True):
	"""Grab an item from the Python stack by its name.

	If an estimatedDepth is provided, the search will start there,
	  scanning from that frame and go in the direction startRecent implies.
	  (If startRecent is True, it will scan from the estimatedDepth
	   towards the maximum stack depth, going up the call tree.)
	"""
	# if no shortcut is provided, start at the furthest point
	if estimatedDepth is None:
		estimatedDepth = 1 if startRecent else currentStackDepth()-1
	try:
		while True:
			frame = sys._getframe(estimatedDepth)
			if objName in frame.f_locals:
				return frame.f_locals[objName]
			estimatedDepth += 1 if startRecent else -1
	except ValueError:
		return None

# https://www.youtube.com/watch?v=vcFBwt1nu2U&lc=UgyEDNCFugZNIDEss214AaABAg
upvar = getObjectByName

class PythonFunctionArguments(object):
	"""Function introspection simplified."""
	_VARARGS = 4
	_VARKEYWORDS = 8

	def __init__(self, function):
		if getattr(function, 'im_func', None):
			function = function.im_func
		self.function = function

		if getattr(function, 'func_code', None):
			self.tablecode = function.func_code
			self._default_values = tuple(function.func_defaults or [])
		else:
			self.tablecode = function.__code__
			self._default_values = tuple(function.__defaults__ or [])

	def tuple(self):
		# just the core facts
		return self.function, self.nargs, self.args, self._default_values

	@property
	def name(self):
		return self.tablecode.co_name

	@property
	def num_args(self):
		return self.tablecode.co_argcount

	nargs = num_args

	@property
	def num_nondefault(self):
		return self.nargs - len(self._default_values)

	nnondefault = num_nondefault

	@property
	def args(self):
		return tuple(self.tablecode.co_varnames[:self.nargs])

	@property
	def defaults(self):
		return dict((self.tablecode.co_varnames[self.num_nondefault+dix],val)
					for dix,val in enumerate(self._default_values))

	@property
	def has_varargs(self):
		return bool(self.tablecode.co_flags & self._VARARGS)

	@property
	def varargs(self):
		if self.has_varargs:
			return self.tablecode.co_varnames[self.nargs]
		else:
			return None

	@property
	def has_varkwargs(self):
		return bool(self.tablecode.co_flags & self._VARKEYWORDS)

	@property
	def varkwargs(self):
		if self.has_varkwargs:
			return self.tablecode.co_varnames[self.nargs + self.has_varargs]
		else:
			return None


def getFunctionCallSigs(function, joinClause=' -OR- '):
	"""Explains what you can use when calling a function.
	The join clause doesn't make as much sense for Python functions,
	  but is very useful for overloaded Java calls.

	>>> getFunctionCallSigs(getFunctionCallSigs, joinClause=' <> ')
	"(function, joinClause=' -OR- ')"
	"""
	if getattr(function, 'im_func', None):
		function = function.im_func

	if 'argslist' in dir(function):
		callMethods = []
		for reflectedArgs in function.argslist:
			if reflectedArgs is None: continue
			if reflectedArgs:
				callMethods += ['(%s)' % ', '.join(['<%s>' % repr(arg)[7:-2]
													for arg in reflectedArgs.args])]
			else:
				callMethods += ['()']
		return joinClause.join(callMethods)

	pfa = PythonFunctionArguments(function)

	out = []
	for i in range(pfa.num_nondefault):
		out += [pfa.args[i]]
	for i in range(len(pfa.defaults)):
		out += ['%s=%r' % (pfa.args[pfa.nnondefault + i], pfa._default_values[i])]

	if pfa.has_varargs:
		out += ['*%s' % pfa.varargs]
	if pfa.has_varkwargs:
		out += ['**%s' % pfa.varkwargs]

	return '(%s)' % ', '.join(out)


def getReflectedField(self, field_name, method_class=None):
	"""Using reflection, we may need to tell the JVM to allow us to see the object."""

	# Typically, we will pull the field off the given object instance
	#   (traditionally named 'self' in Python)
	if method_class is None:
		try:
			field = self.class.getDeclaredField(field_name)
		except AttributeError:
			field = self.getDeclaredField(field_name)
	else:
		# But we may have situations where it is more straight-forward
		#   to get the method first, then pass self in
		#   (as all class methods are declared in Python)
		# If this the case, check if the class is just the name.
		#   (Java lets us get a class by its unique name reference)
		if isinstance(method_class, (unicode, str)):
			method_class = JavaClass.forName(method_class)
		field = method_class.getDeclaredField(field_name)

	# Java reflection respects class privacy by default.
	# But to be useful it needs to be able to inspect regardless.
	# Also, this code is in Python, so we already don't have a problem
	#   with respectfully-hidden-but-still-accessible private attributes.
	try:
		original_accesibility = field.isAccessible()
		field.setAccessible(True)
		# Note that this is very similar to Python's self.
		# An alternate way to write this is source.field in Python
		attribute = field.get(self)
	finally:
		# ... That all said, we'll still put this back out of politeness.
		field.setAccessible(original_accesibility)

	return attribute
