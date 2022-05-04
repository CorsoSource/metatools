"""
	Mixin function template and support for Process simulation
"""


class MetaFunctionMixin(type):

	_meta_config_methods = ('_configure_default_',
							'_configure_function_',
						   )

	def __new__(cls, clsname, bases, attributes):

		if any((
			clsname == 'MixinFunctionSupport',
			not clsname.endswith('Mixin'),
		)):
			return super(MetaFunctionMixin, cls).__new__(cls, clsname, bases, attributes)

		support_name = clsname[:-len('Mixin')] #  clsname.partition('_')[2]

		for method_name in cls._meta_config_methods:

			specialized_method_name = '%s%s' % (method_name, support_name)
			if method_name in attributes:
				method = attributes.pop(method_name)
			else:
				raise NotImplementedError('MixinFunctionSupport subclasses must at least cover the default config methods: %r' % cls._meta_config_methods)
			attributes[specialized_method_name] = method

		return super(MetaFunctionMixin, cls).__new__(cls, clsname, bases, attributes)


class MixinFunctionSupport(object):
	__metaclass__ = MetaFunctionMixin

	def _configure_default_(self, variable):
		# by default pass along enough info to come up with something useful
		return dict(variable=variable, value=self._DEFAULT_START_VALUE)

	def _configure_function_(self, **configuration):
		if 'hold' in configuration:
			def hold_value(self=self, variable=configuration['variable']):
				return self._variables[variable]
			return hold_value
		elif 'value' in configuration:
			def static_value(self=self, value=configuration['value']):
				return value
			return static_value
		elif 'function' in configuration:
			return configuration['function']
		raise NotImplementedError('Mixins should explicitly configure functions.')

	def _resolve_arguments(self, some_callable):
		return super(MixinFunctionSupport, self)._resolve_arguments(some_callable)

	def _resolve_variable_definition(self, variable_definition):
		return super(MixinFunctionSupport, self)._resolve_variable_definition(variable_definition)
