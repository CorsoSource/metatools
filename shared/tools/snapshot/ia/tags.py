from __future__ import with_statement

#shared.tools.pretty.install()

import re
from textwrap import dedent
from functools import partial

from shared.tools.snapshot.utils import encode, stringify, getDesignerContext

#DEFAULT_TAG = system.tag.getTag('[Example]All Default Values').getTag()
from com.inductiveautomation.ignition.common.sqltags import TagDefinition
DEFAULT_TAG = TagDefinition()


TAG_PATH_PATTERN = re.compile("""
	^ 
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
	$
	""", re.I + re.X)


def getTag(provider, tag_path):
	tag = system.tag.getTag('[%s]%s' % (provider, tag_path))
	try:
		return tag.getTag()
	except AttributeError:
		return tag
		

provider = 'Example'


DIRECTLY_HANDLED_ATTRIBUTES = set([
	'parameters',
	'tagType', 'extended', 'inherited', 
	'fullPath', 'folderPath', 'alarms', 'tags',
	'PropertyOverrides', 'ExtendedProperties',
	'EventScripts', 'Name', 'TagType',
	'Value',
#	'DataType', 'TagType', 'Enabled', 
	'AccessRights', 'AlarmConfiguration',
])


from java.util import HashSet, HashMap
from com.inductiveautomation.ignition.common.config import BasicPropertySet, ExtendedPropertySet
from com.inductiveautomation.ignition.common.sqltags.model.udt import OverrideMap
from com.inductiveautomation.ignition.common.alarming.config import BasicAlarmConfiguration, ExtendedAlarmConfiguration
from com.inductiveautomation.ignition.common.sqltags import BasicTagPermissions
from com.inductiveautomation.ignition.common.sqltags.model.scripts import BasicTagEventScripts, ExtendedTagEventScripts
from com.inductiveautomation.ignition.common.sqltags import BasicTagValue


def resolve_hashSet(hashSet):
	return sorted([v for v in hashSet])


def resolve_hashMap(hashMap):
	return dict([
		(str(key), hashMap.get(key))
		for key in hashMap.keySet()
		])

		
def resolve_propertySet(basicPropertySet):
	resolved = {}
	for key in basicPropertySet.getProperties():
		resolved[str(key)] = basicPropertySet.get(key)
	return resolved

	
def resolve_propertySet_inherited(extendedPropertySet):
	resolved = {}
	directly_defined = extendedPropertySet.getLocal()
	if directly_defined:
		resolved['direct'] = resolve_propertySet(directly_defined)
	
	inherited_from_parent = extendedPropertySet.getParent()
	if inherited_from_parent:
		
		resolved_inherited = resolve_propertySet(inherited_from_parent)
	
		strictly_inherited = [key for key in resolved_inherited if not key in resolved['direct']]
		
		if strictly_inherited:
			resolved['inherited'] = dict((key,resolved_inherited[key]) for key in strictly_inherited)

	return resolved


# TAG SPECIFIC PROPERTIES

def resolve_alarms(alarm_states):
	alarms = {}
	for alarm in alarm_states.getDefinitions():
		
		alarm_def = {}
		for attribute, binding in resolve(alarm.getBoundProperties()).items():
			alarm_def[attribute] = binding.getStringRepresentation()

		alarm_def.update(resolve(alarm.getRawValueMap()))
		del alarm_def['name']
		alarms[alarm.getName()] = alarm_def
		
	return alarms

def resolve_alarms_inherited(alarm_states):
	raise NotImplementedError("Needs to filter on local!")
	
	resolved = resolve_alarms(alarm_states)
	return resolved
	
	
def resolve_events(event_scripts):
	scripts = {}
	
	for event in event_scripts.getDefinedEvents():
		if event_scripts.isOverridden(event):
			scripts[event] = dedent(event_scripts.get(event))

	return scripts
	
def resolve_events_inherited(event_scripts):
	raise NotImplementedError("Needs to filter on local!")
	
	resolved = resolve_events(alarm_states)
	return resolved
	

def resolve_permissions(permission_model):
	permissions = []
	
	access_map = permission_model.getAccessMap()
	for permission in access_map.keySet():
		permissions.append({
				'role': permission.getRole(),
				'zone': permission.getZone(),
				'allow': access_map.get(permission),
			})
	return permissions
	
	
def resolve_qualified_value(qualified_value):
	return qualified_value.value
			

DEFAULT_RESOLVER = stringify
RESOLVERS = {
		                   HashSet: resolve_hashSet,
		                   HashMap: resolve_hashMap,
		               OverrideMap: resolve_hashMap,
		               
		          BasicPropertySet: resolve_propertySet,
		       ExtendedPropertySet: resolve_propertySet_inherited,
		
		   BasicAlarmConfiguration: resolve_alarms,
		ExtendedAlarmConfiguration: resolve_alarms_inherited,
		
		      BasicTagEventScripts: resolve_events,
		   ExtendedTagEventScripts: resolve_events_inherited,
		
		       BasicTagPermissions: resolve_permissions,
		
		             BasicTagValue: resolve_qualified_value,
	}


def resolve(thing):
	return RESOLVERS.get(type(thing), DEFAULT_RESOLVER)(thing)
	

def resolve_overrides(udt, parent_udt_type):

	overrides = {}
	for member_id, override in resolve(udt.getPropertyOverrides()).items():		
		member = parent_udt_type.getMember(member_id)
		if not member:
			continue
		if not override.getProperties():
			continue
		
		member_path = './%s' % member.getQualifiedName()
		
		if not member_path in overrides:
			overrides[member_path] = {}
		resolved = resolve(override)
		
		# only keep overrides
		if 'direct' in resolved:
			resolved = resolved['direct']
			
		for key,value in resolved.items():
			if key == 'Name':
				continue # skip - always there
			overrides[member_path][key] = resolve(value)
			
	overrides = dict((member_path,properties)
					 for member_path,properties
					 in overrides.items()
					 if properties)
		
	return overrides	
		

def resolve_udt_def(udt_def, provider):
	
	configuration = {
		'Type': udt_def.getType(),
		'TypePath': '_types_/%s' % TAG_PATH_PATTERN.match(
						str(udt_def.getFullyQualifiedType())
						).groupdict()['path'],
		'BaseUDT': udt_def.getTypePathFor(udt_def),
		}
	
	local_tags = udt_def.getLocalMembers(False)
	inherited_tags = [m for m in udt_def.getMembers(False) if not m in local_tags]

	udt_parameters = resolve(udt_def.getExtendedProperties())
	if udt_parameters.get('direct', {}):
		configuration['Parameters'] = udt_parameters['direct']
	
	tags = {}
	for member in local_tags:
		member_path = './%s' % member.getQualifiedName()
		tag = member.getObject()
		
		if str(tag.getType()) == 'UDT_INST':
			member_details = resolve_udt_member(tag)
			if 'Parameters' in member_details and 'Parameters' in configuration:
				nonoverridden = {}
				for param, value in member_details['Parameters'].items():
					if param in udt_parameters.get('direct', {}):
						if udt_parameters['direct'][param] == value:
							continue
					if param in udt_parameters.get('inherited', {}):
						if udt_parameters['inherited'][param] == value:
							continue
					nonoverridden[param] = value
				if nonoverridden:
					member_details['Parameters'] = nonoverridden
				else:
					del member_details['Parameters']
		else:
			member_details = resolve_tag_member(tag)

		tags[member_path] = member_details

	tags.update(resolve_overrides(udt_def, udt_def))
	
	if tags:
		configuration['Tags'] = tags
	
	# deduplicate params, if appropriate
	if configuration['BaseUDT'] and configuration.get('Parameters', {}):
		tag_parts = TAG_PATH_PATTERN.match(str(udt_def.getFullyQualifiedType())).groupdict()
		parent_udt_path = '[%s]_types_/%s' % (tag_parts.get('provider', 'default'), configuration['BaseUDT'])
		
		parent_udt = system.tag.getTag(parent_udt_path)

		parent_parameters = resolve(parent_udt.getExtendedProperties())
		if parent_parameters:
			nonoverridden = {}
			for param, value in configuration['Parameters'].items():
				if param in parent_parameters.get('direct', {}):
					if parent_parameters['direct'][param] == value:
						continue
				if param in parent_parameters.get('inherited', {}):
					if parent_parameters['inherited'][param] == value:
						continue
				nonoverridden[param] = value
				
			if nonoverridden:
				configuration['Parameters'] = nonoverridden
			else:
				del configuration['Parameters']

	return configuration	


def resolve_udt_member(udt):
	
	configuration = {
		'UDT': udt.getFullyQualifiedType(), 
		}
	
	parameters = resolve(udt.getExtendedProperties())['direct']
	if parameters:
		configuration['Parameters'] = parameters
				

	local_tags = udt.getLocalMembers(False)
	inherited_tags = [m for m in udt.getMembers(False) if not m in local_tags]

	udt_parameters = resolve(udt.getExtendedProperties())
	if udt_parameters.get('direct', {}):
		configuration['Parameters'] = udt_parameters['direct']
		
	tags = {}
	
	for member in local_tags:
		member_path = './%s' % member.getQualifiedName()
		tag = member.getObject()
		
		if str(tag.getType()) == 'UDT_INST':
			member_details = resolve_udt_member(tag)
			if 'Parameters' in member_details and 'Parameters' in configuration:
				nonoverridden = {}
				for param, value in member_details['Parameters'].items():
					if param in udt_parameters.get('direct', {}):
						if udt_parameters['direct'][param] == value:
							continue
					if param in udt_parameters.get('inherited', {}):
						if udt_parameters['inherited'][param] == value:
							continue
					nonoverridden[param] = value
				if nonoverridden:
					member_details['Parameters'] = nonoverridden
				else:
					del member_details['Parameters']
		else:
			member_details = resolve_tag_member(tag)

		tags[member_path] = member_details

	tags.update(resolve_overrides(udt, udt))

	if tags:
		configuration['Tags'] = tags		
				
	return configuration
	
	
def resolve_tag_member(tag):
	
	configuration = {
		'DataType': tag.getDataType() if not str(tag.getType()) == 'Folder' else 'Folder',
		}
	
	event_scripts = tag.getEventScripts()
	if event_scripts:
		scripts = resolve(event_scripts)
				
		if scripts:
			configuration['Scripts'] = scripts
	
	alarm_states = tag.getAlarmStates()
	if alarm_states:
		alarms = resolve(alarm_states)
			
		if alarms:
			configuration['Alarms'] = alarms
	
	access_map = tag.getPermissionModel().getAccessMap()
	if access_map:
		configuration['Permissions'] = resolve(tag.getPermissionModel())
			
	return configuration
	

def resolve_udt(udt, provider):
	
	configuration = {
		'Type': 'UDT'
		}
		
	for prop in udt.getProperties():
		value = udt.get(prop)
		if value == DEFAULT_TAG.getOrDefault(prop):
			continue

		prop = str(prop)
		if prop in DIRECTLY_HANDLED_ATTRIBUTES:
			continue
			
		if prop == 'UDTParentType':
			configuration['UDT'] = '_types_/%s' % value
		else:
			configuration[prop] = resolve(value)
	
	parameters = resolve(udt.getExtendedProperties()).get('direct')
	if parameters:
		configuration['Parameters'] = parameters
	
	overrides = resolve_overrides(udt, getTag(provider, configuration['UDT']))
	if overrides:
		configuration['Tags'] = overrides	
	
	return configuration
	
	
def resolve_tag(tag, provider):
	
	configuration = {
		'DataType': tag.getDataType() if not str(tag.getType()) == 'Folder' else 'Folder',
		#'name': tag.getName(),
		}
		
	if tag.getType() <> DEFAULT_TAG.getType():
		configuration['Type'] = str(tag.getType())
	
	for prop in tag.getProperties():
		value = tag.get(prop)

		if value == DEFAULT_TAG.getOrDefault(prop):
			continue
		
		prop = str(prop)
		if prop in DIRECTLY_HANDLED_ATTRIBUTES:
			continue
			
		if prop == 'UDTParentType':
			configuration['UDT'] = '_types_/%s' % value
		else:
			configuration[prop] = resolve(value)
	
	event_scripts = tag.getEventScripts()
	if event_scripts:
		scripts = resolve(event_scripts)
				
		if scripts:
			configuration['Scripts'] = scripts
	
	alarm_states = tag.getAlarmStates()
	if alarm_states:
		alarms = resolve(alarm_states)
			
		if alarms:
			configuration['Alarms'] = alarms
	
	access_map = tag.getPermissionModel().getAccessMap()
	if access_map:
		configuration['Permissions'] = resolve(tag.getPermissionModel())

	return configuration


def recurse_tags(root_path):

	provider = TAG_PATH_PATTERN.match(root_path).groupdict().get('provider', 'default')

	extracted_tags = {}
	
	for browsed_tag in system.tag.browseTags(root_path, recursive=False):
		tag_path = browsed_tag.getFullPath()
		tag_parts = TAG_PATH_PATTERN.match(tag_path).groupdict()
		
		if browsed_tag.isFolder():
			extracted_tags[tag_parts['path']] = {'DataType': 'Folder'}
			extracted_tags.update(recurse_tags(tag_path))
			continue
		
		tag = getTag(provider, tag_parts['path'])
		
		if str(tag.getType()) == 'UDT_DEF':
			extracted_tags[tag_parts['path']] = resolve_udt_def(tag, provider)
		elif str(tag.getType()) == 'UDT_INST':
			extracted_tags[tag_parts['path']] = resolve_udt(tag, provider)
		else:
			extracted_tags[tag_parts['path']] = resolve_tag(tag, provider)
	
	return extracted_tags	


def extract_tags(provider='default'):
	extracted_tags = {}
		
	root_path = '[%s]_types_' % provider
	extracted_tags.update(recurse_tags(root_path))
	
	root_path = '[%s]' % provider
	extracted_tags.update(recurse_tags(root_path))
	
	return dict([
		encode(extracted_tags)
		])


# tag extraction
def bulk_extract_tags(global_project, category='', context=None):
	if context is None:
		context = getDesignerContext()
	
	deserializer = context.createDeserializer()

	extracted_resources = {}
	for provider_folder in system.tag.browseTags('[System]Gateway/Tags'):
		provider = provider_folder.name
		
		dest_path = 'tags/%s' % provider
		if category:
			dest_path = category + '/' + dest_path

		extracted_resources[dest_path] = extract_tags(provider)

	return extracted_resources

# Ready for the dispatcher
BULK_GLOBAL_EXTRACTORS = [bulk_extract_tags]

#	with open('C:/Workspace/scratchspace/example_tag_dump.yaml', 'w') as f:
#		f.write(encode(extracted_tags)[1])
	


#tag = getTagInProvider('Non-default values for everything')
#
#with open('C:/Workspace/temp/example_tag_utd_def.yaml', 'w') as f:
#	f.write(encode(resolve_tag(tag))[1])



### TESTING
#
#udt = system.tag.getTag('[Example]UDTs/Some numbered UDT but with a value override').getTag()
#
##t = tags[0]
##m = t.getMembers(False)[3].getObject()
#
#tag = system.tag.getTag('[Example]_types_/Complex Example')
#member = tag.getMembers(False)[3].getObject()
#
