import math
from itertools import permutations

class MetaEase(type):
    
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
               
                
        return super(MetaEase, cls).__init__(clsname, bases, attributes)
    
class Ease(object):
    """An easing object.
    Transliterated from 
    https://github.com/ai/easings.net/blob/master/src/easings/easingsFunctions.ts
    """
    __metaclass__ = MetaEase

    _algebraic = ('quad', 'cubic', 'quart', 'quint')
    _algos = _algebraic + ('sine', 'expo', 'circ', 'back', 'elastic')
    _directions = ('in', 'out', 'in_out')

    
    _c1 = 1.70158
    _c2 = _c1 * 1.525
    _c3 = _c1 + 1
    _c4 = (2 * math.pi) / 3
    _c5 = (2 * math.pi) / 4.5
    
    
    def __init__(self, lowerBound=0.0, upperBound=1.0, steps=None):
        self.bounds = slice(lowerBound, upperBound, steps)
    
    
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