import re
from java.util import Date

from shared.tools.enum import Enum

class TAG_OVERWRITE_POLICY(Enum):
	ABORT = 'a'
	OVERWRITE = 'o'
	IGNORE = 'i'
	MERGE = 'm'
	
	
def mask_dict(default, overrides, **kwarg_overrides):
	return dict((key,kwarg_overrides.get(key,
					 overrides.get(key, 
					 default.get(key, KeyError))))
				for key 
				in set(kwarg_overrides.keys() 
				     + overrides.keys() 
				     + default.keys()) )


class TagsMixin(object):

	_TAG_TYPE_MAP = {
		str: 'String',
		int: 'Int4',
		float: 'Float8',
		bool: 'Boolean',
		Date: 'DateTime',
		}

	#https://regex101.com/r/ogqErX/4
	_TAG_PATTERN = re.compile(r"""
		^ (?P<fullpath>
		  # If a tag provider is given, match that first
		  (\[(?P<provider>[a-z0-9_\- ]+)\])?
		  # Capture the full path as well
		  (?P<path>
		  # Everything after the provider is a parent path
		  # After the parent path, no forward slashes can be
		  #   matched, so the negative lookahead assures that.
		  ((?P<parent>.*?)[/\\])?(?![/\\])
		  # The tag name won't have a forward slash, and if
		  #   missing we'll check that it's a folder
		  (?P<name>[a-z0-9_\- ]+)?)
		) $
		""", re.X + re.I)


	def __init__(self, tags=None, **configuration):
		
		assert 'folder' in tags, 'Tag folder for variables needed in config'
		
		self._tag_definitions = mask_dict({
				 'collision policy': TAG_OVERWRITE_POLICY.OVERWRITE,
				 'resume': True, # instead of clearing out, load back in, if possible
			}, tags or {})
				
		super(TagsMixin, self).__init__(**configuration)

		self._initialize_tags()
	
	
	def _initialize_tags(self):
		
		def override_tag_config(tag_name, configuration=self._tag_definitions['configuration']):
			return mask_dict(
				configuration.get('_default', {}),
				configuration.get(tag_name, {})			
				)
				
		def check_init_value(self, variable_name, default):
			if self._tag_definitions['resume']:
				if system.tag.exists(self._tag_definitions['folder'] + '/' + variable_name):
					value = system.tag.read(self._tag_definitions['folder'] + '/' + variable_name).value
					self._variable[variable_name] = value
					return value
			return default
			
		root_parts = {
				'provider': 'default',
				'parent': ''
			}
		
		root_parts.update(
			dict((k,v) 
			     for k,v 
			     in self._TAG_PATTERN.match(self._tag_definitions['folder']).groupdict().items() 
			     if v))
		
		tag_definitions = {
				'tagType': 'Folder',
				'name': root_parts['name'],
				'tags': [],
			}		

		if self._raw_definition:
			tag_definitions['tags'].append(mask_dict({
					'name':     '_definition_',
					'tagType':  'AtomicTag',
					'valueSource':  'memory',
					'dataType': 'String',
					'value':    self._raw_definition,
				}, override_tag_config('_definition_')))
		
		# treat state as a special case
		if self._tag_definitions['resume']:
			if system.tag.exists(self._tag_definitions['folder'] + '/' + 'state'):
				self.state = system.tag.read(self._tag_definitions['folder'] + '/' + 'state').value
				
		tag_definitions['tags'].append(mask_dict({
					'name':     'state',
					'tagType':  'AtomicTag',
					'valueSource':  'memory',
					'dataType': 'String',
					'value':    self.state,
				}, override_tag_config('state')))
		
		for variable, value in self._variables.items():
			if self._tag_definitions['resume']:
				if system.tag.exists(self._tag_definitions['folder'] + '/' + variable):
					value = self._variables[variable] = system.tag.read(self._tag_definitions['folder'] + '/' + variable).value
			
			tag_definitions['tags'].append(mask_dict({
					'name':     variable,
					'tagType':  'AtomicTag',
					'valueSource':  'memory',
					'dataType': self._TAG_TYPE_MAP[type(value)],
					'value':    value,
				}, override_tag_config(variable)))
		
		system.tag.configure(
			basePath = '[%(provider)s]%(parent)s' % root_parts, 
			tags = tag_definitions, 
			collisionPolicy = self._tag_definitions['collision policy'])

		# fully qualified path to folder
		self._tag_folder = '[%(provider)s]%(parent)s/%(name)s' % root_parts

	
	def step(self):
		super(TagsMixin, self).step()
		
		tag_paths = ['%s/%s' % (self._tag_folder, variable) for variable in sorted(self._variables)]
		values = [value for _,value in sorted(self._variables.items())]
		
		tag_paths.append('%s/state' % self._tag_folder)
		values.append(self.state)
		
		system.tag.writeAll(tag_paths, values)
