"""
	System Monitoring - Know Thy Self
	
	These are scripts for getting a better idea of what your Ignition system is doing.
	
	Escapement-Histogram
	  Sometimes your sysetm doesn't seem to keep up in weird and confusing ways.
	The `clock_drift_monitor` spawns a thread that simply tracks how wrong
	the sleep() function works for different time slices. It samples and
	merges results to generate a cumulative  set of results, as well as a
	histogram of the actual times needed.
	  It's a statistical sampling approach. Use the data to get a better
	feel for how the system is working and how it's loaded.
	

"""
from shared.tools.thread import async

from datetime import timedelta


# times where the data gathering is both archived and reset
DEFAULT_BREAKPONTS = {
	'5 min':  timedelta(minutes=5),
	'1 hour': timedelta(hours=1),
	'1 day':  timedelta(days=1),	
}


DEFAULT_HISTOGRAM_CONFIG = {
	10:   slice(5,   30,    1),
	25:   slice(20,  70,    1),
	50:   slice(45,  95,    1),
	100:  slice(95,  145,   1),
	250:  slice(225, 475,   5),
	500:  slice(450, 950,  10),
	1000: slice(950, 1450, 10),
}


# in milliseconds since this is a Java mechanic
DEFAULT_WAIT_INTERVALS = [10, 25, 50, 100, 250, 500, 1000]


@async(name='Escapement-Histogram', ensureOnlyOne=reversed, startDelaySeconds=2.0,)
def clock_drift_monitor(dump_path=None, dump_pretty=False,
	sample_size       = 20,
	wait_times        = DEFAULT_WAIT_INTERVALS,
	cumulative_breaks = DEFAULT_BREAKPONTS,
	archive_limit     = 10,
	histogram_configs = DEFAULT_HISTOGRAM_CONFIG,
	):
	"""Launch a thread that profiles the clock drift and lag.
	
	This is a bit different from the built-in warning, in that it sets a variety
	of short(er) timespans and measures the error. Error is normal - no clock
	time is going to be exact with as many abstractions are stacked up. But
	it may not be _stable_ and _predictable_. This will show that fairly explicitly.
	
	Only one monitor thread may run at a time. Runs continuously until killed.
	
	Results are logged after each test. 
	Tests comprise of sample_size sets of wait_times. 
	Each test result is accumulated and merged into the previous.
	Breaks mark time intervals to archive accumulated results and reset accumulation to last test.
	
	Args:
		dump_path: (str) Filepath to where to dump results between each test.
		dump_pretty: (bool) Indent and inline histograms to make human browsing easier. Defaults to off.
		
		sample_size: (int) Number of times to repeat wait_times intervals per test.
		wait_times: (list of ms) List of intervals in milliseconds to sleep.
		cumulative_breaks: (dict of timedeltas) Intervals between archiving and resetting for next batch of tests.
		archive_limit : (int) number of cumulative batches of tests to save
		histogram_configs: (dict of slices) window to apply for histogram buckets to cover (I.e. a slice for start/stop/step)
	"""
	from shared.data.stats import describe, histogram, combine_descriptions
	from shared.tools.logging import Logger; logger = Logger('Drift Profiler')
	logger.debug('Clock drift profiler starting...')
	
	from datetime import timedelta, datetime
	from random import shuffle
	from java.lang.System import nanoTime
	from java.lang.Thread import sleep
	from copy import deepcopy
	
	if dump_path:
		from json import dumps
		import re
	
	from shared.tools.global import ExtraGlobal
	# cache life is about 10 tests (refreshes each test, though)
	result_cache_lifespan = 11 * (sample_size * sum(wait_times))
	
	# copy dicts to keep thread independent from defaults
	wait_times        = deepcopy(wait_times)
	cumulative_breaks = deepcopy(cumulative_breaks)
	histogram_configs = deepcopy(histogram_configs)
	
	# ensure histogram configs are as expected
	for delay in wait_times:
		try:
			hist_config = histogram_configs[delay]
			if isinstance(hist_config, slice):
				histogram_configs[delay] = {'start': hist_config.start, 'stop': hist_config.stop, 'step': hist_config.step}
		except KeyError:
			histogram_configs[delay] = {}

	# BEGIN!	
	thread_start = datetime.now()

	cumulative = {}
	prev_cumulative = {}
	for breakpoint_label in cumulative_breaks:
		cumulative[breakpoint_label] = dict((d,{}) for d in wait_times)
		cumulative[breakpoint_label]['iterations'] = 0
		cumulative[breakpoint_label]['tests'] = 0
		prev_cumulative[breakpoint_label] = []
	
	results = dict((delay, {}) for delay in wait_times)
	
	# for collective reference
	all_results = {
		'sample_size': sample_size,
		'histogram': histogram_configs,
		'start': thread_start.isoformat(' '),
		
		'results': results,
		'cumulative': cumulative,
		'prev_cumulative': prev_cumulative,
	}
	
	ExtraGlobal.stash(all_results, label='data', scope='Escapement-Histogram', lifespan=result_cache_lifespan)
	ExtraGlobal.stash(True, label='running', scope='Escapement-Histogram', lifespan=result_cache_lifespan)
		
	logger.info('Clock drift profiling started.')
	try: # capture thread interrupt and gracefully stop
		while ExtraGlobal.access(label='running', scope='Escapement-Histogram'):
			
			samples = dict((s,[]) for s in wait_times)
			
			for i in xrange(sample_size):
				
				for delay in wait_times:
					
					start = nanoTime()
					sleep(delay)
					end = nanoTime()
					
					# get the error in nanoseconds 
					# (avoid floating points for raw data)
					duration = (end - start)
					
					samples[delay].append(duration)
				
				# make sure the sampling is stochastic
				shuffle(wait_times)
		
			# for reporting, sort in place (and then use that in the next iteration)
			wait_times.sort()
			
			for delay, durations in samples.items():
#				target_delay_ns = delay * 1000000
#				errors = [
#					(duration_ns -target_delay_ns)/1000000.0 
#					for duration_ns in durations
#				]
#				results[delay] = describe(errors)
				
				durations = [d/1000000.0 for d in durations]
				
				results[delay] = describe(durations)
				
				hist_config, hist_counts = histogram(durations, **histogram_configs[delay])
				results[delay]['histogram'] = {
					'counts': hist_counts,
					'outliers': len([x for x in durations if x > hist_config.stop])
				}
			
			now = datetime.now()
			
			# log the results
			logger.trace(u'Sample results (%d): %s' % (
				sample_size, ' * '.join(
					(u'%dms: ' % delay) + (
					 u'%(mean)0.1fms ±%(standard deviation)0.3fms (%(max)0.0fms max)' % results[delay]
					) for delay in wait_times
				)
			))
			
			# check for archiving
			for breakpoint_label, interval in cumulative_breaks.items():		
				# wait until we're past the breakpoint before saving
				if now > thread_start + interval*(cumulative[breakpoint_label]['iterations']+1):
					# archive the test
					prev_cumulative[breakpoint_label].append(deepcopy(cumulative[breakpoint_label]))
					prev_cumulative[breakpoint_label][-1]['finished'] = now.isoformat(' ')
					# ensure archive limit isn't exceeded
					prev_cumulative[breakpoint_label] = prev_cumulative[breakpoint_label][-archive_limit:]
					
					# log the results
					logger.debug(u'Breakpoint %r results: %s' % (
						breakpoint_label, ' * '.join(
							(u'%dms: ' % delay) + (
							 u'%(mean)0.1fms ±%(standard deviation)0.3fms (%(n)dpts, %(max)0.0fms max)' % (
							 	prev_cumulative[breakpoint_label][-1][delay])
							) for delay in wait_times
						)
					))
					
					# reset accumulation buffer
					cumulative[breakpoint_label]['iterations'] += 1
					cumulative[breakpoint_label]['tests'] = 1 # reset
					
					# reset onto a new, fresh dataset
					cumulative[breakpoint_label].update(results)
				else:
					for delay in wait_times:
						cumu_results = cumulative[breakpoint_label][delay]
						last_results = results[delay]
						try:
							new_cumulative_results = combine_descriptions(cumu_results, last_results)
							new_cumulative_results['histogram'] = {
								'counts': [
										x+r for x,r 
										in zip(cumu_results['histogram']['counts'], 
											   last_results['histogram']['counts'])
									],
								'outliers': (cumu_results['histogram']['outliers'] + 
											 last_results['histogram']['outliers'])
							}
						except KeyError: # first time
							new_cumulative_results = deepcopy(last_results)
						
						cumu_results.update(new_cumulative_results)
						
					cumulative[breakpoint_label]['tests'] += 1
			
			# check for saving
			if dump_path:            
				with open(dump_path, 'w') as f:
					out_dump = dumps(all_results, indent=2 if dump_pretty else None)
					if dump_pretty:
						# inline the dang histogram lists.
						out_dump = re.sub(r'(\"counts\": \[)([^]]*)(\])', 
										  lambda m: m.group(1) + 
										            m.group(2).replace('\n', '').replace(' ', '') + 
										            m.group(3), 
										  out_dump, count=400, flags=re.S) # high count so it grinds through archives
					f.write(out_dump)
			
			# restash the results
			ExtraGlobal.stash(all_results, label='data', scope='Escapement-Histogram', lifespan=result_cache_lifespan)
	
	except KeyboardInterrupt:
		ExtraGlobal.stash(True, label='running', scope='Escapement-Histogram', lifespan=result_cache_lifespan)
			
	logger.info('Clock drift profiling stopped.')
	
#	p(results)

#monitor_thread = clock_drift_monitor(dump_path=r'C:\Workspace\temp\clock_drift_profiling.json')
