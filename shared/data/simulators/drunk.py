import random

class DrunkenWalk(object):
    """A random walker that can get progressively more or less random over time."""    
    
    _reasonable = dict(
        money=100.0,
        tolerance=3.0, # ABV div 3, soberiety gained per recoveryRate steps
        alcoholism=100,
        recoveryRate=1000.0
    )
    
    _maxBounce = 0.2
    _antiTopple = (0.0, 0.0) # (0.2,0.8)
            
    def __init__(self, initValue=0, inebriation=0.12, 
                 money=None, tolerance=None, alcoholism=None, recoveryRate=None,
                 handrails=(0,10.0), leaning=None, stride=None,
                 boozeMenu=[(10,0.12)]):
        """Perform a random walk. The more inebriated, the more the value wanders.
        
        If money is given, more booze will be bought and indebriation gets worse each step.
        Inebriation goes down each step depending on the tolerance.
        
        Alcoholism determines how many steps before another drink it purchased.
        """
        self.value = initValue
        self.inebriation = inebriation
        self.money = money or 0
        self.alcoholism = alcoholism or 0        
        self.tolerance = tolerance or 0
        self.recoveryRate = recoveryRate or 0
        if self.tolerance and not self.recoveryRate:
            self.recoveryRate = self._reasonable['recoveryRate']

        self.leaning = leaning or 0.5
        self.stride = stride or 2
        
        self.boozeMenu = boozeMenu
        self.steps = 0
        self.handrails = handrails
        
        
    def stumble(self):
        
        self.steps += 1
        
        if self.alcoholism and (self.steps % self.alcoholism == 0):
            self.drink()
        if self.tolerance:
            self.inebriation -= self.tolerance / self.recoveryRate
            self.inebriation = max((0, self.inebriation))
        
        self.leaning += (self.leaning * 0.1)
        if self._antiTopple:
            left,right = self._antiTopple
            if self.leaning > right:
                self.leaning = right
            elif self.leaning < left:
                self.leaning = left
        
        self.value += (random.random()-(self.leaning+0.5))*self.inebriation*self.stride
        
        if self.handrails:
            left,right = self.handrails
            if self.value < left:
                self.value = left
                self.leaning = 0.0 + abs(self.leaning/2)
            elif self.value > right:
                self.value = right
                self.leaning = 0.0 - abs(self.leaning/2)
        
        return self.value
    
            
    def traipse(self, steps=None):
        for step in range(steps or self.alcoholism):
            _ = self.stumble()
        return self.value
            
            
    def drink(self):
        if self.money:
            cost,abv = random.choice(abv for cost,abv in self.boozeMenu if cost <=self.money)
            self.money -= cost
            self.inebriation += abv/(self.tolerance)