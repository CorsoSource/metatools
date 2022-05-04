"""
	Create traps for the tracer to monitor and trip into interdiction mode
"""

from shared.tools.expression import Expression, two_argument_operators


from functools import wraps


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


def fail_false(function):
	"""Decorates functions that on an exception simply return False"""
	@wraps(function)
	def false_on_error(*args, **kwargs):
		try:
			return function(*args, **kwargs)
		except:
			return False
	return false_on_error


def resolve_field(context, field):
	return getattr(context, field, context[field])



class BaseTrap(object):
	__slots__ = ('__weakref__',)

	def __init__(self):
		raise NotImplementedError("Subclass for specific methods of trapping.")
	def check(self, context):
		raise NotImplementedError("Subclass for specific methods of trapping.")


class WatchTrap(BaseTrap):
	"""Use a function to run against the scope. If it's value is expected, return True.

	Function will be provided values from context that map to the argument names of it.
	"""
	__slots__ = ('function', 'expectation')

	def __init__(self, function, expectation=True):
		self.function = function
		self.expectation = expectation

	@fail_false
	def check(self, context):
		fc = self.function.f_code
		return self.function(*(self.resolve_field(context, field)
							   for field in fc.co_varnames[:fc.co_argcount]
							 )) == self.expectation


class ExpressionTrap(BaseTrap):
	"""Execute a (custom) compiled statement against the context.

	Expressions should reference variables in context.
	"""

	__slots__ = ('left', 'comparator', 'right')

	def __init__(self, expression, comparator='==', expected_result='True'):
		self.left = Expression(self.expression)
		self.comparator = two_argument_operators[comparator]
		self.right = Expression(self.expected_result)


	@fail_false
	def check(self, context):
		return self.comparator(
				self.left(*(self.resolve_field(context, field)
							for field
							in self.left._fields) ) ,
				self.right(*(self.resolve_field(context, field)
							 for field
							 in self.right._fields) ) )



class ContextTrap(BaseTrap):
	"""Return true if a context matches the preset values."""
	__slots__ = ('context_values')

	def __init__(self, **context_values):
		self.context_values = context_values

	@fail_false
	def check(self, context):
		return all(self.resolve_field(context, field) == value
				   for field, value
				   in self.context_values.items())


class TransientTrap(BaseTrap):
	"""These traps should be deleted once tripped."""
	pass


class Step(TransientTrap):
	"""Trips on first check."""
	def __init__(self):
		pass

	def check(self, context):
		return True


class Next(TransientTrap):
	"""Trips on the next line (or return) in the current scope."""
	__slots__ = ('depth', 'filename', 'caller', 'line')

	def __init__(self, context):
		self.depth    = context.depth
		self.filename = context.filename
		self.caller   = context.caller

	def check(self, context):
		return all((
			context.depth    == self.depth,
			context.filename == self.filename,
			context.caller   == self.caller,
			))


class Until(TransientTrap):
	"""Trips on the next line greater than current (or return) in the current scope."""
	__slots__ = ('depth', 'filename', 'caller', 'line')

	def __init__(self, context):
		self.depth    = context.depth
		self.filename = context.filename
		self.caller   = context.caller
		self.line     = context.line

	def check(self, context):
		return all((
			context.depth    == self.depth,
			context.filename == self.filename,
			context.caller   == self.caller,
			context.line > self.line or context.event == 'return',
			))


class Return(TransientTrap):
	"""Trips when the function returns."""
	def __init__(self, context):
		self.depth    = context.depth
		self.filename = context.filename
		self.caller   = context.caller

	def check(self, context):
		return all((
			context.depth    == self.depth,
			context.filename == self.filename,
			context.caller   == self.caller,
			context.event    == 'return',
			))