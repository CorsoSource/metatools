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


def isJavaObject(o):
	"""Walk up the object inheritance heirarchy to determine if the object is Java-based"""
	cutoff = 10
	
	while cutoff:
		cutoff -= 1
		oType = type(o)

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
	elif getattr(function, 'func_code', None):
		nargs = function.func_code.co_argcount
		args = function.func_code.co_varnames[:nargs]
		defaults = function.func_defaults or []
	else:
		nargs = function.__code__.co_argcount
		args = function.__code__.co_varnames[:nargs]
		defaults = function.__defaults__ or []
	
	nnondefault = nargs - len(defaults)
		
	out = []
	for i in range(nnondefault):
		out += [args[i]]
	for i in range(len(defaults)):
		out += ['%s=%r' % (args[nnondefault + i],defaults[i])]

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