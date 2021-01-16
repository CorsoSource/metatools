"""
	Timing helper functions

	These add the side effect of delay to for loops or exectution.

	Internally, the functions are millisecond-centric, but they maintain the
	  API usage of normal Python calls by being outwardly second-centric.
"""

try:
	from java.lang.System import currentTimeMillis as now
except ImportError:
	from time import time
	now = lambda: int(round(time() * 1000))

from time import sleep
from datetime import datetime, timedelta


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


def waitForConditionOrTimeout(rising_edge_function, us_timeout=100000, _us_check_rate=1000, err_msg="Function check failed to be truthy in time."):
	"""Spins the execution's wheels while we wait for a condition to become true."""
	_us_check_rate /= 1000000.0
	timeout = datetime.now() + timedelta(microseconds=us_timeout)
	while not rising_edge_function() and datetime.now() < timeout:
		sleep(_us_check_rate)
	
	if rising_edge_function():
		return
	else:
		raise TimeoutError(err_msg)
	
	
class AtLeastThisDelay(object):
	"""Force a with statement to take a minimum amount of time before
	returning execution to the thread.

	Time is in units of seconds. (Internally it is in milliseconds.)

	Test code to see how it works:
		with AtLeastThisDelay(1.0) as remainingTime:
			pass
		print 'done!' # will not print for one second
	"""
	def __init__(self, minClamp=0):
		self.delayMS = minClamp * 1000.0

	def __enter__(self):
		self.startTimeMS = now()
		self.endTimeMS = self.startTimeMS + self.delayMS
		return lambda : self.endTimeMS - now()

	def __exit__(self, exc_type, exc_val, exc_tb):
		timeRemainingMS = self.endTimeMS - now()
		if timeRemainingMS > 0:
			sleep(timeRemainingMS / 1000.0)


class EveryFixedBeat(object):
	"""Times a for loop to iterate on delay times.
	  Think of it like a metronome: long iterations can cause beats to be missed!

	Use in a for loop, making each loop iterate ON the step times given
	(up to the max time provided).

	If the loop takes too long, it will skip the missed window and wait until the next.
	
	Time is in units of seconds. (Internally it is in milliseconds.)
	
	If steps are provided _instead_ of step times, then the needed step times
	  will be calculated instead.
	
	for windowNumber,lastStepTime in EveryFixedDelay(1.0, 0.100):
		pass # iterates ten times
	for windowNumber,lastStepTime in EveryFixedDelay(1.0, numSteps=3):
		pass # iterates three times, about 333ms each
	"""
	def __init__(self, maxTime=0.0, stepTime=0.0, numSteps=0, initialIteration=True):

		maxTimeMS = maxTime * 1000.0
		stepTimeMS = stepTime * 1000.0

		if maxTimeMS and numSteps and not stepTimeMS:
			stepTimeMS = maxTimeMS / numSteps
		self.stepTimeMS = stepTimeMS
		self.maxTimeMS = maxTimeMS
		self.initialIteration = initialIteration

		self.startTimeMS = now()
		self.count = 0
		self.endTimeMS = self.startTimeMS + self.maxTimeMS
		self.lastStepTimeMS = self.startTimeMS
		
	def __iter__(self):
		if self.initialIteration:
			yield 0, 0
			
		while now() < self.endTimeMS:
			currentTimeMS = now() # keep it internally consistent, 
								# but yield at end will be ever so slightly off
			
			nextStepNumber = (currentTimeMS + self.stepTimeMS - self.startTimeMS) // self.stepTimeMS
			nextStepTime  = (nextStepNumber * self.stepTimeMS) + self.startTimeMS
			
			self.count = nextStepNumber
			
			if nextStepTime > self.endTimeMS:
				nextStepTime = self.endTimeMS
			
			# The extra +1ms here is to ensure we don't undershoot and loop too many times
			remainingWaitTime = nextStepTime - currentTimeMS + 1 
			
			if remainingWaitTime > 0:
				sleep( remainingWaitTime / 1000.0 )
			
			newCurrentTimeMS = now()
			lastStepDuration = (newCurrentTimeMS - self.lastStepTimeMS) / 1000.0
			self.lastStepTimeMS = newCurrentTimeMS
			
			
			yield self.count, lastStepDuration


class EveryFixedDelay(object):
	"""Times a for loop so that each step takes at least a certain delay.

	Use in a for loop, making each loop take at least the step time given
	(up to the max time provided).
	
	Time is in units of seconds. (Internally it is in milliseconds.)

	If a particular iteration takes a long time that merely delays the next iteration.
	If the current time exceeds the max time, the loop simply exits.

	If steps are provided _instead_ of step times, then the needed step times
	  will be calculated instead.
	
	for iterNum,lastStepTime in EveryFixedDelay(1.0, 0.100):
		pass # iterates ten times
	for iterNum,lastStepTime in EveryFixedDelay(1.0, numSteps=3):
		pass # iterates three times, about 333ms each
	"""
	def __init__(self, maxTime=0.0, stepTime=0.0, numSteps=0, initialIteration=True):

		maxTimeMS = maxTime * 1000.0
		stepTimeMS = stepTime * 1000.0

		if maxTimeMS and numSteps and not stepTimeMS:
			stepTimeMS = maxTimeMS / (numSteps - initialIteration)
		self.stepTimeMS = stepTimeMS
		self.maxTimeMS = maxTimeMS
		self.initialIteration = initialIteration

		self.startTimeMS = now()
		self.count = -1
		self.endTimeMS = self.startTimeMS + self.maxTimeMS
		self.lastStepTimeMS = self.startTimeMS
		
	def __iter__(self):
		if self.initialIteration:
			self.count += 1
			yield 0, 0
			
		while now() < self.endTimeMS:
			currentTimeMS = now() # keep it internally consistent, 
								# but yield at end will be ever so slightly off
								
			if self.lastStepTimeMS + self.stepTimeMS > self.endTimeMS:
				remainingWaitTime = self.startTimeMS + self.maxTimeMS - currentTimeMS
			else:
				# The extra +1ms here is to ensure we don't undershoot and loop too many times
				remainingWaitTime = self.lastStepTimeMS + self.stepTimeMS - currentTimeMS + 1
				
			if remainingWaitTime > 0:
				sleep(remainingWaitTime / 1000.0)
			
			self.count += 1
			newCurrentTimeMS = now()
			lastStepDuration = (newCurrentTimeMS - self.lastStepTimeMS) / 1000.0
			self.lastStepTimeMS = newCurrentTimeMS
			yield self.count, lastStepDuration


#start = now()
#print 'start %d' % start
#
##for windowNumber,lastStepTime in EveryFixedRate(1.000, numSteps=3, initialIteration=True):
##for windowNumber,lastStepTime in EveryFixedRate(1.000, 0.300, initialIteration=False):
##for windowNumber,lastStepTime in EveryFixedRate(0, 0, initialIteration=False):
##for windowNumber,lastStepTime in EveryFixedRate(0, 0, initialIteration=True):
##for windowNumber,lastStepTime in EveryFixedDelay(0, 0, initialIteration=False):
##for windowNumber,lastStepTime in EveryFixedDelay(0, 0, initialIteration=True):
##	print '%3d  %5d   %d' % (windowNumber, lastStepTime, now() - start)
##	if windowNumber == 1:
##		sleep(0.4)
#
##for iterNum,lastStepTime in EveryFixedDelay(1.000, numSteps=3, initialIteration=True):
##for iterNum,lastStepTime in EveryFixedDelay(1.000, numSteps=3, initialIteration=False):
##for iterNum,lastStepTime in EveryFixedDelay(1.000, 0.250, initialIteration=True):
##for iterNum,lastStepTime in EveryFixedDelay(1.000, 0.300, initialIteration=True):
##for iterNum,lastStepTime in EveryFixedDelay(1.000, 0.300, initialIteration=False):
##	print '%3d  %5d   %d' % (iterNum, lastStepTime, now() - start)
##	if iterNum == 1:
##		sleep(0.4)
#end = now()
#print 'done  %d' % end
#print 'total %d' % (end - start)
