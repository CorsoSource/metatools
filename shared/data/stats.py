"""
	Commonly used statistical functions
	
	Based on the Python 3.8 offering, but with the addition 
	that each ignores None values like Excel.

"""
from collections import defaultdict
import math

class StatisticsError(ValueError): pass # Generic "this won't work" error for stats
class InsufficientData(StatisticsError): pass # Generic "need more numbers" error



def magnitude(x):
	"""https://stackoverflow.com/a/16839304"""
	return int(math.floor(math.log10(x)))


def order_of_magnitude(x):
	"""Returns the base-10 order of magnitude for a value. 
	So 12.3 is 10, 0.03 is 0.01
	"""
	return 10**magnitude(x)


def mag_floor(x, oom):
	"""Returns the floor of x snapping to the given order of magnitude. 
	So 12.345 given 0.01 is 12.34, -5.67 at 0.1 is -5.7 
	"""
	return x // oom * oom


def mag_ceil(x, oom):
	"""Returns the ceiling of x snapping to the given order of magnitude. 
	So 12.345 at 0.1 is 12.4, -5.67 at 0.1 is -5.6"""
	q,r = divmod(x, oom)
	q *= oom
	if r:
		q+=oom
	return q


def round_sigfigs(x, n=None):
	"""Round x to n digits significant figures. Defaults to x (no sigfigs)."""
	if n is None:
		return x
	assert n >= 1
	oom = 10**(magnitude(x)-(n-1))
	q,r = divmod(x, oom)
	q *= oom
	if r/oom > 0.5:
		q += oom
	return q



def prime_on_first(iterator):
	x = None
	try:
		while x is None:
			x = next(iterator)
	except StopIteration:
		# return None
		raise InsufficientData
	return x


def least(iterable):
	"""Scans over iterable and returns the smallest non-None value"""
	iterator = iter(iterable)
	minx = prime_on_first(iterator)
	
	for x in iterator:
		if x is None:
			continue
		if x < minx:
			minx = x
	return minx


def most(iterable):
	"""Scans over the iterable and returns the largest non-None value"""
	iterator = iter(iterable)
	maxx = prime_on_first(iterator)
		
	for x in iterator:
		if x is None:
			continue
		if x > maxx:
			maxx = x
	return maxx


def summation(iterable):
	"""Scans over the iterable and returns the total, sans None values"""
	iterator = iter(iterable)
	x = prime_on_first(iterator)

	values = [x]
	values.extend(x for x in iterator if x is not None)

	return sum(values)


def mean(iterable):
	"""Scans over the iterable and returns the average, ignoring None values"""
	iterator = iter(iterable)
	x = prime_on_first(iterator)

	values = [x]
	values.extend(x for x in iterator if x is not None)

	# mean or average
	return math.fsum(values) / len(values)


def geometric_mean(iterable):
	"""Scans over the iterable and returns the log-average result of non-None values.
	No effort was expended to make this precise.
	"""
	iterator = iter(iterable)
	x = prime_on_first(iterator)

	values = [x]
	values.extend(x for x in iterator if x is not None)

	negative_values = 0
	sum_logs = 0
	for x in values:
		if x < 0:
			negative_values += 1
			sum_logs += math.log(-x)
		else:
			sum_logs += math.log(x)

	# ((-1)^m)^(1/n)
	negative_correction_compensation = math.pow(math.pow(-1,negative_values),1.0/len(values))

	return negative_correction_compensation * math.exp((1.0/len(values))*sum_logs)


def harmonic_mean(iterable):
	"""Scans over the iterable and returns the reciprocal of the mean of the recipricals of non-None values
	If a value is 0, the result is zero
	"""
	iterator = iter(iterable)
	x = prime_on_first(iterator)

	if x == 0:
		return 0.0

	values = [x]
	values.extend(x for x in iterator if x is not None)

	sum_recip = 0.0
	for x in values:
		if x is None:
			continue
		if x == 0:
			return 0.0
		sum_recip += 1.0/x

	return len(values) / sum_recip


def variance(iterable):
	"""Scans over the iterable and returns the variance, ignoring None values"""
	iterator = iter(iterable)
	x = prime_on_first(iterator)

	values = [x]
	values.extend(x for x in iterator if x is not None)

	if len(values) < 2:
		raise InsufficientData("Variance is calculated with N-1 DoF")

	# mean or average
	mu = math.fsum(values) / len(values)

	# variance
	return math.fsum(pow(x-mu,2) for x in values) / (len(values)-1)


def standard_deviation(iterable):
	"""Scans over the iterable and returns the standard deviation"""
	return math.sqrt(variance(iterable))

stdev = standard_deviation


def median(iterable):
	"""Returns the value in the middle of the iterable (after filtering out None)"""
	iterator = iter(iterable)
	x = prime_on_first(iterator)

	values = [x]
	values.extend(x for x in iterator if x is not None)
	
	values.sort()

	if len(values) % 2 == 0:
		return (values[len(values)/2-1] + values[len(values)/2]) / 2.0
	else:
		return values[(len(values)-1)/2]


def quantiles(iterable, n=4):
	"""Returns the values to evenly divide the data into n spans, ignoring None values.
	This is modeled off the 'exclusive' method in Python 3.8's statistics module.
	"""
	if n < 1:
		raise StatisticsError('Quantiles return n-1 values as the fenceposts')

	qs = []
	values = [x for x in iterable if x is not None]
	
	if len(values) < n:
		raise StatisticsError('Data should be large enough to have at least one element in each quantile. Data: %r of %r buckets' % (len(values), n))
	
	values.sort()
	
	if len(values) == n:
		return values
			
	width = ((len(values)+1.0) / n) # width of bucket

	for q in range(n-1):
		cutpoint = width*(q + 1)
		frac = cutpoint % 1
		
		a = int(cutpoint // 1.0) - 1

		if frac:
			b = int(a + 1)
			qtile = values[a] + ((values[b] - values[a])*frac)
		else:
			qtile = values[a]
			
		qs.append(round(float(qtile), 6))
		
	return qs


def multimode(iterable, truncation_magnitude=None):
	"""Returns the set of the most common values (ignoring None)"""
	iterator = iter(iterable)
	x = prime_on_first(iterator)

	# count occurences
	counts = defaultdict(int)
	counts[x] += 1
	for x in iterator:
		if x is None:
			continue
		if truncation_magnitude:
			x -= x % truncation_magnitude
		counts[x] += 1

	# check again, keeping only the most
	most = 1
	modes = set()
	for x,n in counts.items():
		if n > most:
			most = n
			modes = set([x])
		elif n == most:
			modes.add(x)

	return modes


def mode(iterable, truncation_magnitude=None):
	"""Returns the most common value (or one of from the set of them, ignoring None)"""
	return next(iter(multimode(iterable, truncation_magnitude)))



def histogram(iterable, buckets=None, start=None, stop=None, step=None):
	"""Returns a list of counts for entries in iterable that fit in evenly spaced buckets."""
	
	iterator = iter(iterable)
	x = prime_on_first(iterator)
	
	minx = maxx = x
	
	values = [x]
	for x in iterator:
		if x is None:
			continue
		values.append(x)
		
		if x < minx:
			minx = x
		if x > maxx:
			maxx = x
			
	x_start = start or minx
	x_end = stop or maxx
		
	x_span = x_end - x_start
	
#	print x_start, x_end, x_span
			
	# resolve and snap to order of magnitude for unconstrained cases
	if buckets:
		oom = order_of_magnitude(x_span / buckets)
	elif step:
		oom = order_of_magnitude(step)
	else:
		oom = order_of_magnitude(10**round(math.log10(x_span))/10.0)
	
	# re-resolve unset things given the order of magnitude
	if not start:
		x_start = mag_floor(x_start, oom)
	if not stop:
		x_end = mag_ceil(x_end, oom)
		
	if not (step or buckets):
		x_step = oom
		x_buckets = int(math.ceil((x_end - x_start)/float(x_step)))
	# buckets win in a tie with step since 
	# evenly spaced buckets are better than consistent steps
	# (that's a hot take, but buckets define histogram length, which is kind of a contract)
	elif buckets: 
		x_buckets = int(math.ceil(buckets))
		x_step = ((x_end - x_start) / float(buckets))
	else: # step:
		x_step = step
		x_buckets = int(math.ceil((x_end - x_start) / float(step)))
	
	counts = [0] * x_buckets
	dropped = 0
	for v in values:
		v -= x_start
		try:
			counts[int(v // x_step)] += 1
		except:
			dropped += 1
	
#	p((slice(x_start, x_end, x_step), counts), nestedListLimit=None)
	return slice(x_start, x_end, x_step), counts


def format_histogram(values, height=5, buckets=None, start=None, stop=None, step=None):
	"""Returns a text-based simple histogram."""
	if height < 3:
		height = 3
	
	# config is a slice of the actual start, stop, and step of the histogram
	config, counts = histogram(values, buckets, start, stop, step)
	buckets = len(counts)
	
	# calculate plot verical lmits
	height = float(height)
	maxc = max(counts)
	oom = order_of_magnitude(maxc / height)

	top = maxc
	v_step = mag_ceil(maxc, oom) / height


	# calculate how the margin works (get the longest string that can show up there)
	left_margin = max(map(lambda x: len(str(x)), 
					  [maxc, config.start, round_sigfigs(v_step, 4)+1,])
					  ) + 1
	margin_pad = '  '
	left = '%%%ds' % (left_margin,) + margin_pad
	marker = '+'

	
	plot_lines = []
	for i in range(int(height))[:-1]:
		top -= v_step
		
		if i == 0:
			left_text = maxc
		elif i == int(height//2):
			left_text = (u'Δ' + str(round_sigfigs(v_step, 4)))
		else:
			left_text = ''
		
		plot_lines.append( (left % left_text) + ''.join(marker if c > top else ' ' for c in counts) )
	# floating point precision errors mean maxc is probably not 0
	# so we'll just fluff the last line here
	plot_lines.append( (left % 0) + ''.join(marker if c else ' ' for c in counts) )
	plot_lines.append( ('-' * left_margin + margin_pad) + '=' * buckets )
	plot_lines.append( (left % (config.start) + ((u'Δ%%-%ds' % (buckets-1)) % round_sigfigs(config.step, 5)) + str( config.stop )) )
	
	return '\n'.join(plot_lines)



def combine_stats(n1,mean1,variance1, n2,mean2,variance2):
	"""Merge two sample groups together.
	ref https://math.stackexchange.com/a/2971563
	"""
	new_n = n1 + n2
	new_mean = ((n1*mean1) + (n2*mean2))/(n1+n2)
	new_variance = (
		(   ( ((n1-1)*variance1) + ((n2-1)*variance2) )
		  / ( n1 + n2 - 1.0                           )
		) + (
		    ( (n1*n2)*pow(mean1-mean2,2) )
		  / ( (n1+n2)*(n1+n2-1.0)        )
		)
	)
	return new_n, new_mean, new_variance



def describe(iterable):
	"""Returns the basic statistics of the iterable (ignoring None values)"""
	iterator = iter(iterable)
	x = prime_on_first(iterator)

	values = [x]

	minx = x 
	maxx = x
	total = float(x)

	# pass one - basic stats
	for x in iterator:
		if x is None:
			continue

		values.append(x)
		total += x

		if x < minx:
			minx = x
		if x > maxx:
			maxx = x

	mu = total / len(values)
	if len(values) < 2:
		v = None
		sd = None
	else:
		v = math.fsum(pow(x-mu,2) for x in values) / (len(values) - 1)
		sd = math.sqrt(v)

	return {
		'n': len(values),
		'min': minx,
		'max': maxx,
		'sum': total,
		'mean': mu,
		'variance': v,
		'standard deviation': sd,
		'span': maxx - minx,
	}



def combine_descriptions(desc1, desc2):
	d3_n, d3_mean, d3_variance = combine_stats(
		desc1['n'],desc1['mean'],desc1['variance'],
		desc2['n'],desc2['mean'],desc2['variance'],
		)

	desc3 = {
		'n': d3_n,
		'min': min((desc1['min'], desc2['min'])),
		'max': max((desc1['max'], desc2['max'])),
		'sum': desc1['sum'] + desc2['sum'],
		'mean': d3_mean,
		'variance': d3_variance,
		'standard deviation': math.sqrt(d3_variance),
	}
	
	desc3['span']  = desc3['max'] - desc3['min']
	
	return desc3



NON_ROUNDING_DESCRIPTION_KEYS = set(['n','sum'])


def apply_rounding(x, sigfigs=None, round_digits=None, skip_keys=NON_ROUNDING_DESCRIPTION_KEYS):
	"""Applies a rounding/sigfig coersion to x. 
	If x is an iterable, it will be traversed and recursively applied as well.
	"""
	if isinstance(x, (int, float)):
		x = round_sigfigs(x, sigfigs)
		if round_digits:
			return round(x, round_digits)
		else:
			return x
	if isinstance(x, (list, tuple, set)):
		return type(x)(
			apply_rounding(v, sigfigs, round_digits)
			for v in x)
	if isinstance(x, dict):
		return dict(
			(k, x[k] 
			    if k in skip_keys 
			    else apply_rounding(x[k], sigfigs, round_digits) )
			for k in x
			)
	else: # assume some sort of other iterable
		return (apply_rounding(v, sigfigs, round_digits) for v in x)
	return apply_rounding(desc3, sigfigs, round_digits)


#
#data = [
#	4,3,1,2,2,None,None,2,1,1,3,3,5,None,6,1.5,3,4,3.33,1,2,2,1
#]
#filtered_data = [x for x in data if x is not None]
#
#print 'filtered:  ', filtered_data 
#print 'sorted:    ', sorted(filtered_data)
#print 'n:       %r' % len(filtered_data)
#print 'least:   %r' % least(data)
#print 'most:    %r' % most(data)
#print 'sum:     %r' % summation(data)
#print 'avg:     %r' % mean(data)
#print 'var:     %r' % variance(data)
#print 'stdev:   %r' % standard_deviation(data)
#print 'median:  %r' % median(data)
#print 'm-mode:  %r' % multimode(data)
#print 'mode:    %r' % mode(data)
#print 'quart:   %r' % quantiles(data)
#print 'dec:   %r' % quantiles(data, n=10)
#
#assert round(harmonic_mean([40, 60]),1) == 48.0
#assert round(harmonic_mean([2.5, 3, 10]),1) == 3.6
#assert round(geometric_mean([54, 24, 36]), 1) == 36.0

