"""
	Utilities for Ignition introspection.

	WARNING: These provide easy access to wildly powerful objects. Use caution!

	And have fun!
"""

import math,re, sys


__all__ = [] # This is meant to be empty. No `from corso.meta import *`!


def sentinel(iterable, stopValue):
	"""A helper to make it simpler to implement sentinel values more idomatically.
	I.e. `for i in iter((x for x in range(5)).next, 3):`
	becomes 
	"""
	return iter((x for x in iterable).next, stopValue)


def getDesignerContext(anchor=None):
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


def currentStackDepth():
	"""From https://stackoverflow.com/a/47956089"""
	size = 2
	while True:
		try:
			sys._getframe(size)
			size += 1
		except ValueError:
			return size - 1 # ignore this called frame


def getObjectByName(objName, estimatedDepth=None, mostDeep=False):
	"""Grab an item from the stack by its name."""
	if estimatedDepth: # give a potential shortcut
		frame = sys._getframe(estimatedDepth)
		if objName in frame.f_locals:
			return frame.f_locals[objName]
	
	estimatedDepth = currentStackDepth()-1 if mostDeep else 1
	try:
		while True:
			frame = sys._getframe(estimatedDepth)
			if objName in frame.f_locals:
				return frame.f_locals[objName]
			estimatedDepth += -1 if mostDeep else 1
	except ValueError:
		return None


def getObjectName(o, estimatedDepth=None, mostDeep=False):
	"""Get an item's name by finding its first reference in the stack."""
	if estimatedDepth: # give a potential shortcut
		frame = sys._getframe(estimatedDepth)
		
		for key,value in frame.f_locals.items():
			if value is o:
				return key
	
	estimatedDepth = currentStackDepth() if mostDeep else 1
	try:
		while True:
			frame = sys._getframe(estimatedDepth)
			for key,value in frame.f_locals.items():
				if value is o:
					return key
			estimatedDepth += -1 if mostDeep else 1
	except ValueError:
		return None


def getFunctionCallSigs(function, joinClause=' -OR- '):
	
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
	
		out = []
		for i in range(len(args) - len(defaults)):
			out += [args[i]]
		for i in reversed(range(len(defaults))):
			out += ['%s=%r' % (args[-i-1],defaults[-i])]
	
		return '(%s)' % ', '.join(out)