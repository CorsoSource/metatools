from shared.data.simulators.mixins.support import MixinFunctionSupport
from shared.data.expression import Expression


class ExpressionMixin(MixinFunctionSupport):

	# Required overrides for mixin functions

	def _configure_default_(self, variable):
		return {}

	def _configure_function_(self, expression):
		return Expression(expression)

	# Additional overrides to intercept configuration

	def _resolve_variable_definition(self, variable_definition):
		if isinstance(variable_definition, (str, unicode)):
			return {
				'kind': 'Expression',
				'config': {
					'expression': variable_definition
				}
			}

		return super(ExpressionMixin, self)._resolve_variable_definition(variable_definition)


	def _resolve_arguments(self, some_callable):
		if isinstance(some_callable, Expression):
			return some_callable._fields
		return super(ExpressionMixin, self)._resolve_arguments(some_callable)


	def _initialize_conditional(self, conditional):
		if isinstance(conditional, (str, unicode)):
			return self._close_function(Expression(conditional))

		return super(ExpressionMixin, self)._initialize_conditional(conditional)