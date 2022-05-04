"""
	Mark functions as recordable / dry-run-able

	Putting the @Recordable decorator on a function allows you to
	use a function and record _how_ you used it, or also to interdict
	the function so it behaves as a stub.

	For example, if you have a function that performs work on disk,
	and you run the script and it seems to work - but you don't want to
	do it again - then you can simply use the context manager `LogMacro`
	and interdict that function. Run the script exactly as before, but now
	the function will _not_ be called, but you'll have all the arguments
	that go into it.

	There's an oddly limited number of situations where this is exceptionally
	helpful, but when you need a dry-run, this can help make that happen.
"""
from shared.tools.meta import PythonFunctionArguments

import os
import traceback
from collections import defaultdict
from functools import wraps
from java.lang import Thread
from weakref import WeakKeyDictionary



class MetaRecordable(type):

	record = WeakKeyDictionary()

	# interdiction only works per thread
	_interdiction_threads = WeakKeyDictionary()


	def __call__(cls, function):

		pfa = PythonFunctionArguments(function)
		function_argument_names = pfa.args

		@wraps(function)
		def wrapped_function(*args, **kwargs):

			interdict = False

			if cls.record:

				all_args = dict(zip(function_argument_names, args))
				all_args.update(kwargs)

				for entry in cls.record:
					try:
						cls.record[entry].append((function, all_args))
					except AttributeError:
						pass # recording set up wrong for this entry: should be a list!

					if cls._interdiction_threads.get(entry) is Thread.currentThread():
						interdict = True

			if not interdict:
				results = function(*args, **kwargs)
				return results

			return None

		return wrapped_function


	@classmethod
	def __getitem__(metacls, key):
		return metacls.record[key]


	@classmethod
	def register(metacls, key, default=None, interdict=False):
		if default is not None:
			assert isinstance(default, list)
			metacls.record[key] = default
		else:
			metacls.record[key] = []

		if interdict:
			metacls._interdiction_threads[key] = Thread.currentThread()

	@classmethod
	def unregister(metacls, key):
		for weakdict in (metacls.record, metacls._interdiction_threads):
			try:
				del weakdict[key]
			except KeyError:
				pass # mission already accomplished



class Recordable(object):
	__metaclass__ = MetaRecordable



class LogMacro(object):

	def __init__(self, interdict=True):
		self.interdict = interdict
		self.log = []

	def __enter__(self):
		Recordable.register(self, default=self.log, interdict=self.interdict)
		return self

	def __exit__(self, ex_type, ex_value, ex_traceback):
		Recordable.unregister(self)


#from shared.tools.pretty import p,pdir,install; install()
#from shared.tools.macro import Recordable, LogMacro
#
#
#@Recordable
#def foo(a, b, c=3, **kwargs):
#	print a,b,c, kwargs
#
#print 'by itself'
#foo(1,2)
#
#print 'recording macro and interdicting'
#with LogMacro() as lm:
#
#	foo(1,2)
#
#	foo(b=2, a=1, c=5, d=44)
#
#	p(lm.log)
#
#print 'And show that the record is cleared after the context manager closes'
#Recordable.record