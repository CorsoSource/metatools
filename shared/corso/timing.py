from java.lang.System import currentTimeMillis as now
from time import sleep


class AtLeastThisDelay(object):
	"""Force a with statement to take a minimum amount of time before
	returning execution to the thread.
	
	Test code to see how it works:
		with AtLeastThisDelay(1000) as remainingTime:
			pass
		print 'done!' # will not print for one second
	"""
	def __init__(self, minClampMS=0):
		self.delay = minClampMS
	def __enter__(self):
		self.startTime = now()
		self.endTime = self.startTime + self.delay
		return lambda : self.endTime - now()
	def __exit__(self, exc_type, exc_val, exc_tb):
		timeRemaining = self.endTime - now()
		if timeRemaining > 0:
			sleep(timeRemaining / 1000.0)


class EveryFixedRate(object):
	"""Use in a for loop, making each loop iterate on the step times given
	(up to the max time provided).
	
	If the loop takes too long, it will skip the missed window and wait until the next.
	
	If steps are provided _instead_ of step times, then the needed step times
	  will be calculated instead.
	
	for windowNumber,lastStepTimeMS in EveryFixedDelay(1000, 100):
		pass # iterates ten times
	for windowNumber,lastStepTimeMS in EveryFixedDelay(1000, numSteps=3):
		pass # iterates three times, about 333ms each
	"""
	def __init__(self, maxTimeMS=0.0, stepTimeMS=0.0, numSteps=0, initialIteration=True):
		if maxTimeMS and numSteps and not stepTimeMS:
			stepTimeMS = maxTimeMS / numSteps
		self.stepTime = stepTimeMS
		self.maxTime = maxTimeMS
		self.initialIteration = initialIteration

		self.startTime = now()
		self.count = 0
		self.endTime = self.startTime + self.maxTime
		self.lastStepTime = self.startTime
		
	def __iter__(self):
		if self.initialIteration:
			yield 0, 0
			
		while now() < self.endTime:
			currentTime = now() # keep it internally consistent, 
								# but yield at end will be ever so slightly off
			
			nextStepNumber = (currentTime + self.stepTime - self.startTime) // self.stepTime
			nextStepTime = (nextStepNumber * self.stepTime) + self.startTime
			
			self.count = nextStepNumber
			
			if nextStepTime > self.endTime:
				nextStepTime = self.endTime
			
			# The extra +1ms here is to ensure we don't undershoot and loop too many times
			remainingWaitTime = nextStepTime - currentTime + 1 
			
			if remainingWaitTime > 0:
				sleep( remainingWaitTime / 1000.0 )
			
			newCurrentTime = now()
			lastStepDuration = newCurrentTime - self.lastStepTime
			self.lastStepTime = newCurrentTime
			
			
			yield self.count, lastStepDuration


class EveryFixedDelay(object):
	"""Use in a for loop, making each loop take at least the step time given
	(up to the max time provided).
	
	If a particular iteration takes a long time that merely delays the next iteration.
	If the current time exceeds the max time, the loop simply exits.

	If steps are provided _instead_ of step times, then the needed step times
	  will be calculated instead.
	
	for iterNum,lastStepTimeMS in EveryFixedDelay(1000, 100):
		pass # iterates ten times
	for iterNum,lastStepTimeMS in EveryFixedDelay(1000, numSteps=3):
		pass # iterates three times, about 333ms each
	"""
	def __init__(self, maxTimeMS=0.0, stepTimeMS=0.0, numSteps=0, initialIteration=True):
		if maxTimeMS and numSteps and not stepTimeMS:
			stepTimeMS = maxTimeMS / (numSteps - initialIteration)
		self.stepTime = stepTimeMS
		self.maxTime = maxTimeMS
		self.initialIteration = initialIteration

		self.startTime = now()
		self.count = -1
		self.endTime = self.startTime + self.maxTime
		self.lastStepTime = self.startTime
		
	def __iter__(self):
		if self.initialIteration:
			self.count += 1
			yield 0, 0
			
		while now() < self.endTime:
			currentTime = now() # keep it internally consistent, 
								# but yield at end will be ever so slightly off
								
			if self.lastStepTime + self.stepTime > self.endTime:
				remainingWaitTime = self.startTime + self.maxTime - currentTime
			else:
				# The extra +1ms here is to ensure we don't undershoot and loop too many times
				remainingWaitTime = self.lastStepTime + self.stepTime - currentTime + 1
				
			if remainingWaitTime > 0:
				sleep(remainingWaitTime / 1000.0)
			
			self.count += 1
			newCurrentTime = now()
			lastStepDuration = newCurrentTime - self.lastStepTime
			self.lastStepTime = newCurrentTime
			yield self.count, lastStepDuration


#start = now()
#print 'start %d' % start
#
##for windowNumber,lastStepTime in EveryFixedRate(1000, numSteps=3, initialIteration=True):
##for windowNumber,lastStepTime in EveryFixedRate(1000, 300, initialIteration=False):
##for windowNumber,lastStepTime in EveryFixedRate(0, 0, initialIteration=False):
##for windowNumber,lastStepTime in EveryFixedRate(0, 0, initialIteration=True):
##for windowNumber,lastStepTime in EveryFixedDelay(0, 0, initialIteration=False):
##for windowNumber,lastStepTime in EveryFixedDelay(0, 0, initialIteration=True):
##	print '%3d  %5d   %d' % (windowNumber, lastStepTime, now() - start)
##	if windowNumber == 1:
##		sleep(0.4)
#
##for iterNum,lastStepTime in EveryFixedDelay(1000, numSteps=3, initialIteration=True):
##for iterNum,lastStepTime in EveryFixedDelay(1000, numSteps=3, initialIteration=False):
##for iterNum,lastStepTime in EveryFixedDelay(1000, 250, initialIteration=True):
##for iterNum,lastStepTime in EveryFixedDelay(1000, 300, initialIteration=True):
##for iterNum,lastStepTime in EveryFixedDelay(1000, 300, initialIteration=False):
##	print '%3d  %5d   %d' % (iterNum, lastStepTime, now() - start)
##	if iterNum == 1:
##		sleep(0.4)
#end = now()
#print 'done  %d' % end
#print 'total %d' % (end - start)
