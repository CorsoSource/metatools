"""
	Utilities for Ignition introspection.

	WARNING: These provide easy access to wildly powerful objects. Use caution!

	And have fun!

	The object retrieval functions reach backwards in the Python call stack. It's useful
	  to keep in mind that low number call stack frame numbers are closer to the most recent.
"""

import math,re, sys


__all__ = [] # This is meant to be empty. No `from corso.meta import *`!


GLOBAL_MESSAGE_PROJECT_NAME = None #'global'


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


def getObjectName(o, estimatedDepth=None, startRecent=True):
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
				if value is o:
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
	if 'im_func' in dir(function):
		callMethods = []
		for reflectedArgs in function.im_func.argslist:
			if reflectedArgs is None: continue
			if reflectedArgs:
				callMethods += ['(%s)' % ', '.join(['<%s>' % str(arg)[7:-2] 
													for arg in reflectedArgs.args])]
			else:
				callMethods += ['()']
		return joinClause.join(callMethods)
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