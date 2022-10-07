"""
	Profiling helper functions

	Timeit is built into Python, but its incantation is just a little unobvious.
	But there's a lot of win to be had just _testing_ what's faster.
	Jython is not CPython, and has rather different strengths and weaknesses.
	
	
	
	So when in doubt: test! See how long something really takes!
"""

__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


import timeit
import math
from textwrap import dedent
import tempfile
import profile, pstats
import sys, os



statement_time = lambda statement, setup, iterations: timeit.Timer(statement, setup).repeat(iterations)



def number_to_thousands_separated_string(number, sep=','):
	chunks = []
	numstr = str(int(number))
	chunk = ''
	for i,c in enumerate(numstr[::-1]):
		chunk += c
		if (i+1) % 3 == 0:
			chunks.append(chunk[::-1])
			chunk = ''
	if chunk:
		chunks.append(chunk[::-1])
	return sep.join(chunks[::-1])
	


def convert_to_human_readable(number, unit='s'):
	scale = 1
	vstr = str(number)
	if number   < 0.000001:
		vstr = '%0.3f' % round(number * 1000.0 * 1000.0 * 1000.0, 3)
		scale = 'n'
	elif number < 0.001:
		vstr = '%0.3f' % round(number * 1000.0 * 1000.0, 3)
		scale = 'u'
	elif number < 1.0:
		vstr = '%0.3f' % round(number * 1000.0, 3)
		scale = 'm'
	else:
		n,d = divmod(number, 1)
		if not n:
			vstr = '%0.3f' % round(number, 3)
		else:
			vstr = number_to_thousands_separated_string(n)
			vstr += '%0.3f' % round(d, 3)
		scale = ''
			
	return '%s %s%s' % (vstr, scale, unit)



def profile_script(python_script, context_globals=None, context_locals=None):
	profiler = profile.Profile()
	
	mutable_global_context = (context_globals or {}).copy()
	mutable_locals_context = (context_locals or {}).copy()
		
	profiler.runctx(
		python_script, 
		mutable_global_context, 
		mutable_locals_context,
	)
	
	return profiler, (mutable_global_context, mutable_locals_context)


def profile_call(function, *args, **kwargs):
	"""Calls the function"""
	profiler = profile.Profile()
	
	# do not use runctx with a compiled function - it will NPE
	# (no obvious reason, it breaks on `sys.setprofile(None)` which should be safe)
	results = profiler.runcall(function, *args, **kwargs)
		
	return profiler, results


def log_profile(profiler, results, log_target=None, sorting='tottime'):
	"""Log the results given a logging context. 
	When log_target is:
	  - None - prints to standard out
	  - includes path separators - dumps raw stats to disk
	  - is a normal string - prints to logger
	"""
	if log_target is None:
		# print the results
		profiler_stats = pstats.Stats(profiler)
		profiler_stats.sort_stats(sorting).print_stats()
	elif any(['/' in log_target, '\\' in log_target]):
		profiler_stats = pstats.Stats(profiler)
		profiler_stats.sort_stats(sorting).dump_stats(log_target)
	else:
		from StringIO import StringIO
		prof_stats_output = StringIO()
		profiler_stats = pstats.Stats(profiler, stream=prof_stats_output)
		profiler_stats.sort_stats(sorting).print_stats()
		prof_stats_output.seek(0)
		system.util.getLogger(log_target).info(prof_stats_output.read())
		
	return results
	

def time_it(statement_to_time='pass', setup_statement='pass', iterations=100, setup_executions=3):
	"""Time the given statement iterations number of times. 
	If provided, a setup statement can be used to avoid timing setup. 
	The full test/setup will be repeated setup_executions times.
	"""
	results = {
		'setup repeated': setup_executions,
		'iterations per setup': iterations,
	}
	
	# bail on nothing to do =/
	if not all([setup_executions, iterations]):
		return results
		
	# create the timer
	timer = timeit.Timer(statement_to_time, setup_statement)
	
	# run the test(s)
	times = timer.repeat(setup_executions, iterations)
	
	# calculate some statistics
	values = times
	
	total = math.fsum(values)
	mu = total / len(values)
	results['round avg'] = mu
	results['statement avg'] = mu/iterations
	
	if setup_executions < 2:
		results['round std dev'] = None
	else:
		v = math.fsum(pow(x-mu,2) for x in values) / (len(values) - 1)
		sd = math.sqrt(v)
		results['round std dev'] = sd
		results['est statement std dev'] = sd/iterations
		
	return results



def print_time_it(statement_to_time='pass', setup_statement='pass', iterations=100, setup_executions=3, direct_print=True, include_source=False):
	
	results = time_it(statement_to_time, setup_statement, iterations, setup_executions)
	
	for key,value in results.items():
		if value is None:
			results[key] = ''
		elif key.endswith('std dev'):
			results[key] = ' (±%s)' % convert_to_human_readable(value)
		else:
			results[key] = convert_to_human_readable(value)

	
	report = dedent("""
		For %(iterations)d iterations across %(setup_executions)s setups:
		   %(statement avg)s%(est statement std dev)s per statement
		   %(round avg)s%(round std dev)s total per round
	""" % dict(results.items() + locals().items()))
	
	if include_source and isinstance(setup_statement, str):
#		if setup_statement.count('\n') > 5:
#			setup_statement = '\n'.join(setup_statement.splitlines()[:5] + ['...'])
		report += dedent("""
		Setup:
		%s
		""" % setup_statement)
	
	if include_source and isinstance(statement_to_time, str):
#		if statement_to_time.count('\n') > 3:
#			statement_to_time = '\n'.join(statement_to_time.splitlines()[:3] + ['...'])
		report += dedent("""
		Statement:
		%s
		""" % statement_to_time)
	
	if direct_print:
		print report
	else:
		return report
