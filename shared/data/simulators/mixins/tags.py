import re
from java.util import Date



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


	def __init__(self, tag_path=None, **configuration):
		
		self._tag_folder = tag_path
		
		super(TagsMixin, self).__init__(**configuration)

		self._initialize_tags()
	
	
	def _initialize_tags(self):
		root_parts = {
				'provider': 'default',
				'parent': ''
			}
			
		if system.tag.exists(self._tag_folder):
			system.tag.removeTag(self._tag_folder)

		root_parts.update(
			dict((k,v) 
			     for k,v 
			     in self._TAG_PATTERN.match(self._tag_folder).groupdict().items() 
			     if v))
				
		system.tag.addTag(
				parentPath='[%(provider)s]%(parent)s' % root_parts,
				name=root_parts['name'],
				tagType='Folder',
			)
		
		self._tag_folder = '[%(provider)s]%(parent)s/%(name)s' % root_parts

		if self._raw_definition:
			system.tag.addTag(
					parentPath=self._tag_folder,
					name='_definition_',
					tagType='MEMORY',
					dataType='String',
					value=self._raw_definition,
				)
		

		system.tag.addTag(
				parentPath=self._tag_folder,
				name='state',
				tagType='MEMORY',
				dataType='String',
				value=self.state,
			)
	
		for variable, value in self._variables.items():
			system.tag.addTag(
				parentPath=self._tag_folder,
				name=variable,
				tagType='MEMORY',
				dataType=self._TAG_TYPE_MAP[type(value)],
				value=value,
			)
	
	
	def step(self):
		super(TagsMixin, self).step()
		
		tag_paths = ['%s/%s' % (self._tag_folder, variable) for variable in sorted(self._variables)]
		values = [value for _,value in sorted(self._variables.items())]
		
		tag_paths.append('%s/state' % self._tag_folder)
		values.append(self.state)
		
		system.tag.writeAll(tag_paths, values)
