"""
	Convert strings safely into properly executable functions (not just compiled!)
"""

import __builtin__
import operator as op
import tokenize
from ast import literal_eval
from StringIO import StringIO

from shared.tools.enum import MetaEnum, Enum


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'

__all__ = ['Expression']

TOKENS = MetaEnum(
     'TOKENS', 
     (Enum,), 
     dict((attr,getattr(tokenize,attr)) 
          for attr 
          in dir(tokenize) 
          if    attr.upper() == attr 
            and isinstance(getattr(tokenize, attr),int)))


tokenTypeLookup = dict(
	(getattr(tokenize, tokenType), getattr(TOKENS, tokenType))
	for tokenType
	in dir(tokenize)
	if isinstance(getattr(tokenize, tokenType), int)
	   and tokenType.upper() == tokenType
)


def overload_concat_add(*args):
	if len(args) == 1:
		return op.pos(args[0])
	if all(hasattr(type(v),'__iter__') for v in (args)):
		return op.concat(*args)
	else:
		return op.add(*args)

def overload_neg_sub(*args):
	if len(args) == 1:
		return op.neg(args[0])
	else:
		return op.sub(*args)

def overload_mul_rep(*args):
	if hasattr(type(args[0]),'__iter__') and isinstance(args[1],int):
		return op.repeat(*args)
	else:
		return op.mul(*args)

def extend_iterable(left,right):
	if isinstance(left, tuple):
		return left + (right,)
	else:
		return (left,right)


one_argument_operators = {
	'not': op.not_, '!': op.not_,
}

two_argument_operators = {
	'+' : overload_concat_add,
	'in': op.contains,
	'/' : op.truediv, # see PEP 238
	'//': op.floordiv,
	'&' : op.and_, 'and': op.and_,
	'^' : op.xor,
	'~' : op.invert,
	'|' : op.or_, 'or': op.or_,
	'**': op.pow,
	'is': op.is_,
	#'is not': op.is_not,
	'<<': op.lshift,
	'%' : op.mod,
	'*' : overload_mul_rep, #op.mul,
	'-' : overload_neg_sub,
	'>>': op.rshift,
	'<' : op.lt,
	'<=': op.le,
	'==': op.eq,
	'!=': op.ne,
	'>=': op.ge,
	'>' : op.gt,
	',': extend_iterable,
#	'.': getattr,

	 # backwards because we're hacking a parenthetical replacement, and it's like '.'
	'__getitem__': lambda attr, obj: obj.__getitem__(attr),
}


precedence = {
	20: ['(',')','[',']'],
	0: [','],
	1:  ['lambda'],
	#2:  ['if else'],
	3:  ['or'],
	4:  ['and'],
	5:  ['!','not'],
	6:  ['in', 'is', '<', '<=', '>', '>=', '<>', '!=', '=='], # 'not in', 'is not', 
	7:  ['|'],
	8:  ['^'],
	9:  ['&'],
	10: ['<<','>>'],
	11: ['+','-'],
	12: ['*','/','//','%'],
	13: ['~'], # ['+','-'] # bitwise not, pos, neg
	14: ['**'],
#	18: ['.'],
	18: ['__getitem__']
	#15: [index, slices, x(call), x.attribute]
	#16: [(tuple), [list], {key: value},
}

precedenceLookup = dict(
	(token, key)
	for key,tokens in precedence.items()
	for token in tokens
)



def gather_tokens(expression):
	return (
		(tokenTypeLookup[tokenType], token)
		for tokenType, token, (srow,scol), (erow,ecol), line 
		in tokenize.generate_tokens(StringIO(expression).readline)
	)


def convert_to_postfix(expression):
	opstack = []
	output = []

	raw_tokens = gather_tokens(expression.strip())

	# preprocess for lookups and patchwerks
	tokens = []
	for tokenType, token in raw_tokens:
		if tokenType == TOKENS.OP and token == '[':
			#tokens.append((TOKENS.OP, '.'))
			tokens.append((TOKENS.OP, '__getitem__'))
			tokens.append((TOKENS.OP, '('))
		elif tokenType == TOKENS.OP and token == ']':
			tokens.append((TOKENS.OP, ')'))
		
		elif tokenType == TOKENS.STRING:
			tokens.append((TOKENS.STRING, token[1:-1]))
		
		elif tokenType == TOKENS.ERRORTOKEN and token.strip() == '':
			pass
		
		# ensure the word-like tokens are correctly identified
		elif tokenType == TOKENS.NAME and token in one_argument_operators:
			tokens.append((TOKENS.OP, token))
		
		elif tokenType == TOKENS.NAME and token in two_argument_operators:
			tokens.append((TOKENS.OP, token))
		
		else:
			tokens.append((tokenType, token))

	# Handle the tokens gathered in order.
	# Assume that tokens are provided in INFIX notation
	for tokenTuple in tokens:
		tokenType, token = tokenTuple
		
		# Stop doing work once we get to the end.
		# Importantly: this works for just one line!
		if tokenType == tokenize.ENDMARKER: break
			
		if tokenType == tokenize.OP:
			# Closing a group is treated a bit specially, since it can partly drain the opstack
			if token == ')':
				
				# Drain the stack until we get to a closing parenthesis 
				#   or the calling function name 
				#   (names only appear on the stack when immediately followed by a parens) 
				while opstack and not (   (opstack[-1] == (tokenize.OP,'('))
									   or opstack[-1][0] == tokenize.NAME):
					output.append(opstack.pop())
				# If the parens was preceded by a call, now move that to the output
				if opstack and opstack[-1][0] == tokenize.NAME:

					output.append(opstack.pop())
					
					# Count the compounding
					dots = 0
					while opstack and opstack[-1][0] == tokenize.NAME:
						dots += 1
						output.append(opstack.pop())
					for i in range(dots):
						if opstack and opstack[-1][0] == tokenize.OP and opstack[-1][1] == '.':
							output.append(opstack.pop())
						else:
							raise AttributeError("Unexpected token: was expecting the '.' operator, but the stack is this instead\nopstack:%s\noutput:%s" % (
								str(opstack), str(output)))
						
				# ... otherwise it must just be the opening parens operator
				else:
					_ = opstack.pop()
					
			# Otherwise the token is just a part of the formula 
			else:
				# If we're starting a parenthetical group, check if there's a name right before it.
				#   If so, then assume it's a call, and add that to the stack instead of the '('
				if token == '(' and output and (output[-1][0] == tokenize.NAME or output[-1] == (tokenize.OP, '.')):
					if output[-1] == (tokenize.OP, '.'):
						opstack.append(output.pop())	
						opstack.append(output.pop())
						opstack.append((TOKENS.OP, '('))
					
					# Check if this is a compound attribute, if so pop an extra off
					elif opstack and opstack[-1][0] == tokenize.OP and opstack[-1][1] == '.':
						opstack.append(output.pop())
						if output and output[-1][0] == tokenize.NAME:
							opstack.append(output.pop())
						else:
							raise NotImplementedError('Attributes in expressions must be on named tokens')
					else:
						opstack.append(output.pop())
									
				elif token == '.':
					opstack.append(tokenTuple)
				
				# Otherwise it's a normal token that has to follow the rules of precedence
				else:
					# get the value of this token in relation to others
					tokenPrecedence = precedenceLookup[token]
					# ... and drain the opstack of things that should come first
					while (opstack 
						   and precedenceLookup.get(opstack[-1][1],-20) >= tokenPrecedence 
						   and not (opstack[-1][0] == tokenize.OP
									and opstack[-1][1] in ('(','[','{'))):
						opToken = opstack.pop()
						output.append(opToken)
					# ... and once we know this is the highest precedence operation, add it to the stack
					opstack.append(tokenTuple)

		# All non-operators get pushed to the stack.
		# These are normal things like numbers and names
		else:
			output.append(tokenTuple)
			
			# check if this gets resolved as an attribute (effectively very high precedence operator, next to () )
			if opstack and opstack[-1][1] == '.':
				output.append(opstack.pop())
			

		# print '=> %s\n   %-50s\n   %s\n' % (tokenTuple, '   OPS >> %r' % opstack, '<< OUT    %r' % output)

	while opstack:
		output.append(opstack.pop())
	
	return tuple(output)


def isCallable(obj):
	try:
		return bool(obj.__call__)
	except AttributeError:
		return False

		
whitelisted_modules = set((
	'shared',
	'math'
))


whitelisted_builtins = set((
	'max','min'
))


class REF_TYPE(Enum):
	CONSTANT = -2
	ARGUMENT = -4
	FUNCTION = -8
	EXTERNAL = -16


class Expression(object):
	
	__slots__ = ('_fields', '_eval_func',
				 '_arguments', '_constants', '_functions', '_externals'
				)
	
	def __init__(self, expression):
		if isinstance(expression, str):
			# convert the expression to something we can resolve reliably
			postfixStack = convert_to_postfix(expression)
			# ... and map it to the properties here
			self._resolve_function(postfixStack)
		else:
			self._resolve_function(expression)
		
	def _resolve_function(self, postfixStack):
		
		self._arguments = []
		self._constants = []
		self._functions = []
		self._externals = []
		opstack = []
	
		references = {
			REF_TYPE.FUNCTION: self._functions,
			REF_TYPE.ARGUMENT: self._arguments,
			REF_TYPE.CONSTANT: self._constants,
			REF_TYPE.EXTERNAL: self._externals,
		}
		
		reference_names = {
			REF_TYPE.FUNCTION: 'func',
			REF_TYPE.ARGUMENT: 'args',
			REF_TYPE.CONSTANT: 'const',
			REF_TYPE.EXTERNAL: 'ext',
		}
		
	
		for tokenType,token in postfixStack:

			if tokenType == tokenize.OP:

				if token == '.':
					#raise NotImplementedError('Better to preprocess and resolve first')
					
					# though not strictly necessary since the dot will work as a normal operator, 
					#   this will resolve down and optimize a bit
					(argType2,argIx2), (argType1,argIx1) = opstack.pop(), opstack.pop()
					
					if argType1 == REF_TYPE.FUNCTION and self._functions[argIx1] in self._externals and argType2 == REF_TYPE.ARGUMENT:
						
						attribute = self._arguments.pop(argIx2)
						
						external = getattr(self._functions[argIx1], attribute)
						self._externals.append(external)
						
						if isCallable(external):
							argType3,argIx3 = opstack.pop()
							argRef3 = references[argType3]
							
							if argType3 == REF_TYPE.FUNCTION:
								self._functions.append(lambda function=external, ar1=argRef3, aix1=argIx3: function(
													ar1[aix1]()
												) )
							else:
								self._functions.append(lambda function=external, ar1=argRef3, aix1=argIx3: function(
													ar1[aix1]
												) )

							opstack.append( (REF_TYPE.FUNCTION, len(self._functions) - 1) )
						else:
							self._constants.append(external)
							opstack.append( (REF_TYPE.CONSTANT, len(self._constants) - 1) )
						#self._externals.append(getattr(self._externals[argIx1], attribute))
						#opstack.append( (REF_TYPE.EXTERNAL, len(self._externals) - 1) )
					
					# This is something like a.b where a is an argument and b is some sort of attribute of that type.
					elif (argType1 == REF_TYPE.ARGUMENT or argType1 == REF_TYPE.FUNCTION) and argType2 == REF_TYPE.ARGUMENT:
						
						argRefs = references[argType1]
	
						attribute = self._arguments.pop(argIx2)
						
						# Treat as an attribute lookup on the first
						# Check if it needs calling before resolution, though
						if argType1 == REF_TYPE.ARGUMENT:
							self._functions.append(lambda self=self, argRefs=argRefs, aix1=argIx1, attribute=attribute: getattr(
													argRefs[aix1],
													attribute
												) )
						else: # argType1 == REF_TYPE.FUNCTION:
							self._functions.append(lambda self=self, argRefs=argRefs, aix1=argIx1, attribute=attribute: getattr(
													argRefs[aix1](),
													attribute
												) )

						opstack.append( (REF_TYPE.FUNCTION, len(self._functions) - 1) )
				
					else:
						raise AttributeError('Not sure what to do with this:\nArg 1: %r at %s as "%r"\nArg 2: %r at %s as "%r"' % (
													argType1,argIx1,references[argType1][argIx1],
													argType2,argIx2,references[argType2][argIx2],))
					
				
				elif token in two_argument_operators: 
					(argType2,argIx2), (argType1,argIx1) = opstack.pop(), opstack.pop()
					
					argRef1 = references[argType1]
					argRef2 = references[argType2]
					
					function = two_argument_operators[token]
					
					# Resolve the way we call the arguments in
					#   it needs a late binding, so it kind of has to be broken out like this 
					#   (I don't know how to do this without adding more indirection)
					if argType1 == REF_TYPE.FUNCTION:
						if argType2 == REF_TYPE.FUNCTION:
							self._functions.append(lambda self=self, function=function, ar1=argRef1, aix1=argIx1, ar2=argRef2, aix2=argIx2: function(
												ar1[aix1](),
												ar2[aix2]()
											) )
						else:
							self._functions.append(lambda self=self, function=function, ar1=argRef1, aix1=argIx1, ar2=argRef2, aix2=argIx2: function(
												ar1[aix1](),
												ar2[aix2]
											) )
					else:
						if argType2 == REF_TYPE.FUNCTION:
							self._functions.append(lambda self=self, function=function, ar1=argRef1, aix1=argIx1, ar2=argRef2, aix2=argIx2: function(
												ar1[aix1],
												ar2[aix2]()
											) )
						else:
							self._functions.append(lambda self=self, function=function, ar1=argRef1, aix1=argIx1, ar2=argRef2, aix2=argIx2: function(
												ar1[aix1],
												ar2[aix2]
											) )
							
					opstack.append( (REF_TYPE.FUNCTION, len(self._functions) - 1) )

				if token in one_argument_operators:
				
					(argType1,argIx1)= opstack.pop()
					
					argRef1 = references[argType1]
					
					if argType1 == REF_TYPE.FUNCTION:
						self._functions.append(lambda self=self, function=function, ar1=argRef1, aix1=argIx1: function(
											ar1[aix1]()
										) )
					else:
						self._functions.append(lambda self=self, function=function, ar1=argRef1, aix1=argIx1: function(
											ar1[aix1]
										) )
						
					opstack.append( (REF_TYPE.FUNCTION, len(self._functions) - 1) )
					
			elif tokenType == tokenize.NAME:
				# Check if it's a variable or module we trust
				# as we encounter the '.' operator, whitelist
				if token in whitelisted_modules:
					# math.sin(x) --> ((1, 'math'), (1, 'sin'), (51, '.'), (1, 'x'))
					self._externals.append(__import__(token))
					self._functions.append(self._externals[-1])
					opstack.append( (REF_TYPE.FUNCTION, len(self._functions) - 1) )
					#opstack.append( (EXTERNAL, len(self._externals) - 1) )
				
				elif token in whitelisted_builtins:
					
					function = getattr(__builtin__,token)

					self._externals.append(function)
					#self._functions.append(self._externals[-1])
					#opstack.append( (FUNCTION, len(self._functions) - 1) )

					(argType1,argIx1)= opstack.pop()
					
					argRef1 = references[argType1]
					
					if argType1 == REF_TYPE.FUNCTION:
						self._functions.append(lambda self=self, function=function, ar1=argRef1, aix1=argIx1: function(
											ar1[aix1]()
										) )
					else:
						self._functions.append(lambda self=self, function=function, ar1=argRef1, aix1=argIx1: function(
											ar1[aix1]
										) )
						
					opstack.append( (REF_TYPE.FUNCTION, len(self._functions) - 1) )                    
					
				else:
					if not token in self._arguments:
						self._arguments.append(token)
						opstack.append( (REF_TYPE.ARGUMENT, len(self._arguments) - 1) )

			elif tokenType == tokenize.NUMBER:
				self._constants.append(literal_eval(token))
				opstack.append( (REF_TYPE.CONSTANT, len(self._constants) - 1) )

			elif tokenType == tokenize.STRING:
				self._constants.append(str(token))
				opstack.append( (REF_TYPE.CONSTANT, len(self._constants) - 1) )

			# print 'Token: %s, %s' % (tokenTypeLookup[tokenType], token)
			# print '  Opstack: ',['%s[%d]=%s' % (reference_names[t],ix,references[t][ix]) for t,ix in opstack]
			
		self._fields = tuple(self._arguments)
		self._arguments[:] = []
		
		opType,opIx = opstack.pop()
		if opType in (REF_TYPE.CONSTANT, REF_TYPE.ARGUMENT):
			self._eval_func = lambda: references[opType][opIx]
		else:
			self._eval_func = references[opType][opIx]


	def __call__(self, *args, **kwargs):
		if kwargs:
			self._arguments[:] = [kwargs.get(field) or args[i] for i,field  in enumerate(self._fields)]
		else:
			self._arguments[:] = args
		
		if len(self._arguments) < len(self._fields):
			raise TypeError('Expression takes exactly %d argument%s: %r (%d given)' % (
								len(self._fields), 's' if len(self._fields) > 1 else '', list(self._fields), len(self._arguments)))     
		return self._eval_func()    
