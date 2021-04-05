# -*- coding: utf-8 -*-
import math, re
from types import FunctionType

from transitions import State, Machine

try:
	_ = property.setter
except AttributeError:
	from shared.tools.compat import property

try:
	from yaml import load as yaml_loader, FullLoader
except ImportError:
	from shared.tools.yaml.core import load as yaml_loader, FullLoader


from shared.data.simulators.mixins.support import MixinFunctionSupport


class WrappedSimulationFunction(object):
	
	def __init__(self, datasource, function, aliases=None, name_override=None):

		self._datasource = datasource
		self._function = function
				
		if aliases is None:
			self._aliases = {}
		else:
			self._aliases = aliases.copy()
		
		self._resolve()
		
		
	def _resolve(self, name_override=None):
		self._resolve_name(name_override)
		self._resolve_arguments()
		self._resolve_getters()

		
	# force a recalculation if these values are set
	@property
	def function(self):
		return self._function
	
	@function.setter
	def function(self, function):
		if not function == self._function:
			self._function = function
			self._resolve()
	
	
	@property
	def datasource(self):
		return self._datasource
	
	@datasource.setter
	def datasource(self, datasource):
		self._datasource = datasource
		self._resolve()
	
	
	@property
	def aliases(self):
		return self._aliases
	
	@aliases.setter
	def aliases(self, aliases=None):
		if not aliases == self._aliases:
			if aliases is None:
				self._aliases = {}
			else:
				self._aliases = aliases.copy()
			self._resolve()
			
	
	@property
	def arguments(self):
		return self._arguments
	
	def _resolve_arguments(self):
		self._arguments = self._datasource._resolve_arguments(self._function)
		
	
	@property
	def name(self):
		return self._name
	
	def _resolve_name(self, override=None):
		if override:
			self._name = override
		else:
			try: # function???
				self._name = self._function.func_name
			except AttributeError: # ok prolly a class then
				self._name = function_name = self._function.__class__.__name__    
	
	
	
	def current_value(self, variable):
		return self._datasource._variables[variable]
	
	@property
	def source_variables(self):
		return self._datasource._variables.keys()
	
	
	def _resolve_getters(self):
		getters = []
		for argix, argument in enumerate(self.arguments):
			if argument in self.aliases:
				argument = self.aliases[argument]
#             else:
#                 # by default, skip the self
#                 if argix == 0 and argument == 'self':
#                     continue
#             # currently only the Process interface is expected
#             assert argument in self.source_variables, 'Source class should expose current variable values.'
			
			# assume and hope for the best that the arguments left out have defaults
			if not argument in self.source_variables:
				continue
			getters.append(lambda self=self, argument=argument: self.current_value(argument) )
		
		self._getters = getters
		
		
	def __call__(self):
		"""Wraps the function call to ensure it gets the most recent values for the bound variables."""
		return self.function(*tuple(arg_func() for arg_func in self._getters))
		
	def __repr__(self):
		return '<Sim-λ %s>' % self.name
		

class Process(MixinFunctionSupport, Machine):
	"""
	The core of the simulation design. 
	
	Provide variables and their functions. Set the initial conditions. 
	
	"""

	_DEFAULT_START_VALUE = 0
	_DEFAULT_ESCAPEMENT_VARIABLE = 't'
	_TRANSITION_CHECK = 'check_state'
	
	def __init__(self, 
				 # Raw configuration
				 raw_definition=None,
				 # Simulation configuration
				 variables=None, start=None, alias=None, escapement=None,
				 # State machine configuration
				 states=None, transitions=None,
				 # Remaining state machine configuration pass through
				 **keyword_arguments):
		
		# For self reference and reloading
		self._raw_definition = raw_definition
		
		# For configuration
		self._aliases = alias or {}
		self._start_values = start or {}
		self._definitions = dict((variable, lambda: self._DEFAULT_START_VALUE) 
								 for variable in variables)
		
		# To be initialized
		self._variables = {}
		self._functions = {}
		
		self._escapement_definition = escapement
		self._initialize_escapement()
				
		self._initialize()

		# Machine setup/prep
		self._state_variable_definitions = states
		states = [state for state in states]
		
		self._initialize_transitions(transitions)
		
		keyword_arguments['states'] = states
		keyword_arguments['transitions'] = self._transition_definitions
		keyword_arguments['after_state_change'] = self._reconfigure_after_state_change
		keyword_arguments['auto_transitions'] = False
		super(Process, self).__init__(**keyword_arguments)
		
		# Initial state (first doesn't trigger after state change)
		self._reconfigure_after_state_change()
				
		
	def _initialize_escapement(self):
		"""
		Though not required, it is helpful to directly define how the
		clocks ticks forward in a simulation. Some might use an 
		integer increment, follow wall time, follow a fake clock that
		runs faster than normal, etc.
		"""
		if self._escapement_definition is None:
			self._escapement_variable = None
			self._escapement = None
			return # nothing to do - assume all functions are parametric
		kind = self._escapement_definition['kind']
		config = self._escapement_definition['config']
		
		self._escapement_variable = config.get('variable', self._DEFAULT_ESCAPEMENT_VARIABLE)
		
		self._definitions[self._escapement_variable] = self._escapement_definition
		
		if kind == 'increment':
			increment = config.get('increment', 1)
			def tick(self=self, increment=increment):
				self._variables[self._escapement_variable] += increment
			self._escapement = tick
			
		else:
			raise NotImplementedError, "Escapement not implemented yet - %s" % kind
		
		self._start_values[self._escapement_variable] = config.get('start', self._DEFAULT_START_VALUE)
		self._start_values['_t_step']  = 0
		self._start_values['_t_state'] = self._start_values[self._escapement_variable] # starts with a state, after all
		
		
	def _initialize(self):
		"""
		Initialize the variables to their starting values, if any.
		"""
		for variable in self._definitions:
			if not variable in self._start_values:
				self._start_values[variable] = self._DEFAULT_START_VALUE
				
		# prime varaible listing for reference during resolution
		self._variables = self._start_values.copy()
		
		self._variables['_n_states'] = 1
		self._variables['_n_steps'] = 0
		
		self._initialize_variables()
		
		
	def _initialize_variables(self):
		# maintain the status quo if no reconfiguration
		if not self._definitions:
			return
		
		for variable, definition in self._definitions.items():            
			# Do not mutate the variable that controls the stepping, if provided
			if variable == self._escapement_variable:
				continue

			definition = self._resolve_variable_definition(definition)
			
			if not definition or not isinstance(definition, dict):
				continue
				
			# specific variable definitions override more general ones
			if 'default' in definition:
				self._variables[variable] = self._start_values[variable] = definition['default']
							
			# update definition for variable's aliases for resolution process
			alias = self._aliases.copy()
			alias.update(definition.get('alias', {}))
			definition['alias'] = alias 

			self._functions[variable] = self._resolve_function(variable, definition)
	
	
	def _resolve_variable_definition(self, variable_definition):
		"""
		Generate a more complete variable definition. Exists mostly to be overridden.
		(For example, a variable may be string, but should be an Expression instead;
		 but why hassle with all the configuration keys when a string will do?)
		"""
 		if isinstance(variable_definition, dict) and 'kind' in variable_definition:
			return variable_definition
		elif isinstance(variable_definition, FunctionType):
			return dict(kind='', config=dict(function=variable_definition))
		elif variable_definition is None:
			return dict(kind='', config=dict(hold=None))
		else:
			return dict(kind='', config=dict(value=variable_definition))
			
			
	def _resolve_arguments(self, some_callable):
		"""
		Allow mixins to define how their arguments are resolved for the function closures.
		Returns a list or tuple of argument names that the callable expects.
		"""
		try: # function???
			return some_callable.func_code.co_varnames[:some_callable.func_code.co_argcount]
		except AttributeError: # maybe it's a callable class thing...
			try:
				return some_callable.__call__.func_code.co_varnames[:some_callable.__call__.func_code.co_argcount]    
			except AttributeError:
				return tuple() # if the buck gets passed up the chain all the way to here, well, /shrug
		#return super(FunctionMixin, self)._resolve_arguments(some_callable)
		
				
	def _resolve_function(self, variable, definition):
		"""
		Given a definition, generate a function for a variable to follow.
		"""
		assert isinstance(definition, dict), 'Variable function definition for "%s" should be a dictionary.' % variable
		assert set(('kind','config',)).intersection(set(definition.keys())), 'Variable definitions must at least describe what "kind" it is and the "config" for that kind.'

		kind = definition['kind']
		config = getattr(self, '_configure_default_%s' % kind)(variable)
		config.update(definition.get('config', {}))

		function = getattr(self, '_configure_function_%s' % kind)(**config)
		
		return self._close_function(function, definition.get('alias', {}))
	
	
	def _close_function(self, function, aliases=None):
		"""
		Create closures for each variable's function.
		This will ensure each step is resolved correctly.
		"""
		return WrappedSimulationFunction(self, function, aliases)
	

	def _initialize_transitions(self, transition_definitions):        
		transitions = []
		
		for source, destinations in transition_definitions.items():
			transition = {
				'source': source,
				'trigger': self._TRANSITION_CHECK,
			}
			
			if isinstance(destinations, (str,unicode)):
				transition['dest'] = destinations
			else:
				for dest, conditionals in destinations.items():
					transition['dest'] = dest
					
					for check, conditional in conditionals.items():
						if isinstance(conditional, (list,tuple,set)):
							transition[check] = [
								self._initialize_conditional(condition)
								for condition 
								in conditional]
						else:
							transition[check] = self._initialize_conditional(conditional)						
			
			transitions.append(transition)
		
		self._end_states = [state for state 
							in self._state_variable_definitions
							if not state in transition_definitions]
		
		if self._end_states:
			transitions.append({
				'source': self._end_states,
				'dest': '=',
				'trigger': 'check_state'
			})
		
		self._transition_definitions = transitions
	
	
	def _initialize_conditional(self, conditional):
		"""Conditions trigger on match"""
		if isinstance(conditional, dict):
			def check_values(self=self, values=conditional.copy()):
				return all(
						self._variables[variable] == value
						for variable, value
						in values.items()
					)
			return check_values
			
		raise NotImplementedError("No conditional resolver found for '%r'" % conditional)

	
	def _reconfigure_after_state_change(self, *args, **kwargs):
		self._variables['_n_states'] += 1
		self._variables['_n_steps'] = 0
		if self._escapement_variable:
			self._variables['_t_state'] = self._variables[self._escapement_variable]
		self._definitions = self._state_variable_definitions[self.state]
		self._initialize_variables()
		
		
	def step(self):
		"""
		Incrememnt the simulation variables by one iteration.
		Note: this always acts on the last step's values.
		"""
		self._variables['_n_steps'] += 1
		
		if self._escapement:
			t_prev = self._variables[self._escapement_variable]
			self._escapement()
			self._variables['_t_step'] = self._variables[self._escapement_variable] - t_prev
		
		new_values = {}
		
		for variable, function in self._functions.items():
			new_values[variable] = function()
			
		self._variables.update(new_values)
		
		self.check_state()
		
		
	def __repr__(self):
		max_state_len = max(len(s) for s in self.states.keys())
		format_string = '<Simulation: [%%%ds] {%%s}>' % max_state_len
		return format_string % (self.state, ', '.join(['%s: %s' % (k,v) for k,v 
													   in sorted(self._variables.items())
													   if not k.startswith('_')
													  ]))


def load_simulator(definition, mixins_package='shared.data.simulators.mixins'):
		
	configuration = yaml_loader(definition, FullLoader)
	configuration['raw_definition'] = definition
	
	mixins = []
	mixins += [
			getattr(__import__('%s.%s' % (mixins_package, mixin.lower()), 
							   fromlist=['%sMixin' % mixin]), 
					'%sMixin' % mixin)
			for mixin in configuration.pop('mixins')
		]
	
	mixins += [Process]
	
	return type('Simulator', tuple(mixins), {})(**configuration)
	
