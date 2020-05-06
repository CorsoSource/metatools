"""
	Profiling helper functions

	Timeit is built into Python, but its incantation is just a little unobvious.
	But there's a lot of win to be had just _testing_ what's faster.
	Jython is not CPython, and has rather different strengths and weaknesses.
	  So when in doubt: test! See how long something really takes!

"""

import timeit


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'



statement_time = lambda statement, setup, iterations: timeit.Timer(statement, setup).repeat(iterations)
