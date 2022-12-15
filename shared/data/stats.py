"""
	Commonly used statistical functions
	
	Based on the Python 3.8 offering, but with the addition 
	that each ignores None values like Excel.

"""
from collections import defaultdict
import math

class StatisticsError(ValueError): pass # Generic "this won't work" error for stats
class InsufficientData(StatisticsError): pass # Generic "need more numbers" error


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



def histogram(iterable, buckets=20):
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

	
	# snap to order of magnitude	
	oom = order_of_magnitude((maxx - minx) / buckets)
	
	minx = mag_floor(minx, oom)
	maxx = mag_ceil(maxx, oom)
	
	width = (maxx - minx) / buckets
	
	counts = [0] * buckets
	for v in values:
		v -= minx
		counts[int(v // width)] += 1
	
	return counts
	
	
	
def format_histogram(values, height=5, width=40):
	"""Returns a text-based simple histogram."""
	counts = histogram(values, width)
	
	height = float(height)
	
	maxc = max(counts)
	oom = order_of_magnitude(maxc / height)
	
	left_margin = len(str(maxc)) + 1
	margin_pad = '  '
	left = '%%%ds' % (left_margin,) + margin_pad
	marker = '+'
	
	top = maxc
	step = mag_ceil(maxc, oom) / height
	
	plot_lines = []
	for i in range(int(height))[:-1]:
		top -= step
		
		plot_lines.append( (left % (maxc if not i else '')) + ''.join(marker if c > top else ' ' for c in counts) )
	# floating point precision errors mean maxc is probably not 0
	# so we'll just fluff the last line here
	plot_lines.append( (left % 0) + ''.join(marker if c else ' ' for c in counts) )
	plot_lines.append( ('-' * left_margin + margin_pad) + '=' * width )
	plot_lines.append( (left % mag_floor(min(values),oom)) + ' ' * width + (str(mag_ceil(max(values), oom))) )
	
	return '\n'.join(plot_lines)



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



