"""
	Python port of the easings from the excellent resource https://github.com/ai/easings.net
	URL: https://easings.net

	Some minor additions and wrappers made for convenience.
"""


import math

try:
	from itertools import permutations
except ImportError:
	from shared.tools.compat import permutations

from shared.tools.enum import Enum

class DIRECTION(Enum):
	IN = 'in'
	OUT = 'out'
	IN_OUT = 'in_out'

class ALGORITHM(Enum):

	QUADRATIC = 'quad' # Quadratic - squared
	CUBIC = 'cubic'    # Cubic - x ^ third
	QUARTIC = 'quart'  # Quartic - x to the four
	QUINTIC = 'quint'  # Quintic - x's fifth power

	LINEAR = 'linear'
	SINE = 'sine'
	EXPONENT = 'expo'
	CIRCULAR = 'circ'
	BACK = 'back'
	ELASTIC = 'elastic'


__license__ = 'GPLv3'

# Modifications and additions by:
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


class MetaEaseFunctions(type):

	def __init__(cls, clsname, bases, attributes):

		for power, algo in enumerate(cls._algebraic):
			for direction in cls._directions:
				powerFunction = getattr(cls, '%s_power' % direction)
				def powerClosure(cls, x, p=power+2, pfun=powerFunction):
					return pfun(x,p)
				setattr(cls, '%s_%s' % (direction, algo), classmethod(powerClosure))

		for firstList,secondList in permutations([cls._directions,cls._algos]):
			for first in firstList:

				class EaseChain(object):
					pass

				for second in secondList:
					try:
						function = getattr(cls, '%s_%s' % (first, second))
					except AttributeError:
						function = getattr(cls, '%s_%s' % (second,first))

					@classmethod
					def closure(_, x, fun=function):
						return fun(x)

					setattr(EaseChain, second.upper(), closure)

				setattr(cls, first.upper(), EaseChain)

		return super(MetaEaseFunctions, cls).__init__(clsname, bases, attributes)



class EaseFunctions(object):
	"""An easing object.
	Transliterated from
	https://github.com/ai/easings.net/blob/master/src/easings/easingsFunctions.ts
	"""
	__metaclass__ = MetaEaseFunctions

	_algebraic = ('quad', 'cubic', 'quart', 'quint')
	_algos = _algebraic + ('linear', 'sine', 'expo', 'circ', 'back', 'elastic')
	_directions = ('in', 'out', 'in_out')


	_c1 = 1.70158
	_c2 = _c1 * 1.525
	_c3 = _c1 + 1
	_c4 = (2 * math.pi) / 3
	_c5 = (2 * math.pi) / 4.5


	@classmethod
	def in_linear(cls, x):
		return x

	@classmethod
	def out_linear(cls, x):
		return x

	@classmethod
	def in_out_linear(cls, x):
		return x


	@classmethod
	def in_power(cls, x, power):
		return math.pow(x, power)

	@classmethod
	def out_power(cls, x, power):
		return 1 - math.pow(1-x, power)

	@classmethod
	def in_out_power(cls, x, power):
		if x < 0.5:
			return 2*(power-1)*math.pow(x,power)
		else:
			return 1 - math.pow(-2*x + 2, power) / 2.0


	@classmethod
	def in_sine(cls, x):
		return 1 - math.cos((x*math.pi)/2.0)

	@classmethod
	def out_sine(cls, x):
		return math.sin((x*math.pi)/2.0)

	@classmethod
	def in_out_sine(cls, x):
		return -(math.cos(x*math.pi) - 1)/2.0


	@classmethod
	def in_expo(cls, x):
		if x == 0:
			return 0
		return math.pow(2, 10*x - 10)

	@classmethod
	def out_expo(cls, x):
		if x == 1:
			return 1
		return 1 - math.pow(2, -10*x)

	@classmethod
	def in_out_expo(cls, x):
		if x == 0:
			return 0
		if x == 1:
			return 1
		if x < 0.5:
			return math.pow(2, 20*x - 10)/2.0
		else:
			return (2 - math.pow(2, -20*x + 10))/2.0


	@classmethod
	def in_circ(cls, x):
		return 1 - math.sqrt(1 - math.pow(x, 2))

	@classmethod
	def out_circ(cls, x):
		return math.sqrt(1 - math.pow(x - 1, 2))

	@classmethod
	def in_out_circ(cls, x):
		if x < 0.5:
			return (1 - math.sqrt(1 - math.pow(2*x, 2)))/2.0
		else:
			return (math.sqrt(1 - math.pow(-2*x + 2, 2)) + 1)/2.0


	@classmethod
	def in_back(cls, x):
		return cls._c3*math.pow(x, 3) - cls._c1*math.pow(x, 2)

	@classmethod
	def out_back(cls, x):
		return 1 + cls._c3*math.pow(x-1, 3) + cls._c1*math.pow(x-1, 2)

	@classmethod
	def in_out_back(cls, x):
		if x < 0.5:
			return (math.pow(2*x, 2)*((cls._c2 + 1)*2*x - cls._c2))/2.0
		else:
			return (math.pow(2*x - 2, 2)*((cls._c2 + 1)*(x*2 - 2) + cls._c2) + 2)/2.0


	@classmethod
	def in_elastic(cls, x):
		if x == 0:
			return 0
		if x == 1:
			return 1
		return -math.pow(2, 10*x - 10) * math.sin((x*10 - 10.75) * cls._c4)

	@classmethod
	def out_elastic(cls, x):
		if x == 0:
			return 0
		if x == 1:
			return 1
		return math.pow(2, -10*x) * math.sin((x*10 - 0.75) * cls._c4) + 1


	@classmethod
	def in_out_elastic(cls, x):
		if x == 0:
			return 0
		if x == 1:
			return 1
		if x < 0.5:
			return -(math.pow(2, 20*x - 10) * math.sin((20*x - 11.125) * cls._c5))/2.0
		else:
			return (math.pow(2, -20*x + 10) * math.sin((20*x - 11.125) * cls._c5))/2.0 + 1


	@classmethod
	def in_bounce(cls, x):
		return 1 - cls.out_bounce(1-x)

	@classmethod
	def out_bounce(cls, x):
		n = 7.5625
		d = 2.75

		if x < (1.0/d):
			c = 0

		elif x < (2.0/d):
			x -= 1.5/d
			c = 0.75

		elif x < (2.5/d):
			x -= 2.25/d
			c = 0.9375

		else:
			x -= 2.625/d
			c = 0.984375

		return n1 * x * x + c

	@classmethod
	def in_out_bounce(cls, x):
		if x < 0.5:
			return (1 - cls.out_bounce(1 - 2*x))/2.0
		else:
			return (1 + cls.out_bounce(2*x - 1))/2.0


class Easing(object):
	__slots__ = ('function',
				 'start', 'finish',
				 'time_start', 'time_end', 'steps')

	def __init__(self,
				 ease_type=ALGORITHM.LINEAR,
				 direction=DIRECTION.IN,
				 start=0.0,
				 finish=1.0,
				 steps=None,
				 time_start=0.0,
				 time_end=None,
				 duration=None,
				 ):
		"""
		Ease from start to finish.

		If steps are an integer, it's assumed to iterate that many times.
		If steps are a float, it's assumed the steps run until time_end.
		If the steps are undefined, it's assumed the param is in relation
		  to time_start and time_end.

		Remember the fencepost problem: steps are the fence, not the posts.
		  You start at the beginning - the first step is the first increment.
		  Thus for steps=10, the iterable will yield 11 times!
		"""

		self.function = getattr(EaseFunctions, '%s_%s' % (direction, ease_type))

		self.start = start * 1.0
		self.finish = finish * 1.0

		if duration and not time_end:
			time_end = time_start + duration

		assert time_start < time_end, "Time must flow forward (though scale may not)"
		self.time_start = time_start * 1.0
		self.time_end = time_end * 1.0
		self.steps = steps or None

	@property
	def step_by_count(self):
		return self.steps and isinstance(self.steps, (int, long))
	@property
	def step_by_increment(self):
		return self.steps and isinstance(self.steps, (float,))

	@property
	def span(self):
		return self.finish - self.start

	@property
	def time_span(self):
		return self.time_end - self.time_start

	@property
	def time_bounds(self):
		return slice(self.time_start, self.time_end, self.steps)


	def normalize_time(self, t):
		if self.steps:
			if self.step_by_count:
				if t <= 0:
					return 0.0
				elif t >= self.steps:
					return 1.0
				else:
					return (t * 1.0) / self.steps
			elif self.step_by_increment:
				total_inc = (t * 1.0) * self.steps
				if total_inc <= 0:
					return 0.0
				elif total_inc >= self.time_span:
					return 1.0
				else:
					return (total_inc / self.time_span)
		else:
			if t <= self.time_start:
				return 0.0
			elif t >= self.time_end:
				return 1.0
		return (t - self.time_start) / self.time_span

	def interpolate_scale(self, fraction):
		return self.start + (fraction * (self.span))


	@property
	def scale_bounds(self):
		return slice(self.start, self.finish)

	def __call__(self, t):
		t_norm = self.normalize_time(t)
		y_norm = self.function(t_norm)
		return self.interpolate_scale(y_norm)

	def __iter__(self):
		assert self.steps, "Cannot iterate without a steps defined."
		if self.step_by_count:
			for i in range(self.steps):
				yield i, self(i)
			else:
				yield self.steps, self.finish
		elif self.step_by_increment:
			for t in range(int(self.time_span/self.steps)):
				yield (t * self.steps) + self.time_start, self(t)
			else:
				if (t * self.steps) + self.time_start < self.time_end:
					yield self.time_end, self.finish

