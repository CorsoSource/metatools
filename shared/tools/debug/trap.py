from shared.data.expression import Expression, convert_to_postfix


class Trap(object):
	
	__slots__ = ('left', 'right')
	
	def __init__(self, left_expression, right_expression):
		self.left = Expression(left_expression)
		self.right = Expression(right_expression)
		
		
	def check(self, context):
		try:
			return (self.left(*(getattr(context, field, context[field]) 
								for field 
								in self.left._fields) ) 
					== 
					self.right(*(getattr(context, field, context[field]) 
								 for field 
					 			 in self.right._fields) ) )
		except:
			return False







