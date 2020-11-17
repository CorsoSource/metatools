"""
	Project resources
	
	Many configuration and scripting resources are extracted here.
"""
from shared.tools.snapshot.utils import encode, hashmapToDict


def extract_project_props(client_context):
	
	global_props = client_context.getGlobalProps()
	
	configuration = {
		'permissions': hashmapToDict(global_props.getPermissionEnabledMap()),
		'roles': {
			'client': dict((category, [role.strip() 
									   for role 
									   in role_string.split(',')
									   if role
									   ])
						   for category, role_string
						   in hashmapToDict(
								global_props.getRequiredClientRolesMap()
							).items()),
			'delete'  : [role.strip() for role in global_props.getRequiredDeleteRoles()],
			'publish' : [role.strip() for role in global_props.getRequiredPublishRoles()],
			'resource': [role.strip() for role in global_props.getRequiredResourceRoles()],
			'required': [role.strip() for role in global_props.getRequiredRoles()],
			'save'    : [role.strip() for role in global_props.getRequiredSaveRoles()],
			'view'    : [role.strip() for role in global_props.getRequiredViewRoles()],
			},
		'auditing': global_props.isAuditingEnabled(),
		'legacy': global_props.isLegacyProject(),
		'commitMessageMode': global_props.getCommitMessageMode().toString(), # enum
		'defaultSQLTagsProviderRate': global_props.getSqltagsClientPollRate(),
		}
	
	defaultable_attributes = set([
		'auditProfileName', 
		'authProfileName',
		'defaultDatasourceName', 
		'defaultSQLTagsProviderName',
		'publishMode',
		])
	
	for attribute in defaultable_attributes:
		try: # to get the Java getter first
			# it's slightly more reliable than the Jython auto-attribute, in general
			getter_name = 'get' + attribute[0].upper() + attribute[1:]
			value = getattr(global_props, getter_name)()
		except AttributeError:
			try: # the Jython attribute
				value = getattr(global_props, attribute)
			except AttributeError:
				value = None
		
		if value is None:
			continue
		
		configuration[attribute] = value	

	return dict([
		encode(configuration),
		])

def extract_gatewayevents(resource_objects):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'
	
	client_script_config = resource_objects[0]
	
	scripts = {}
	
	script = client_script_config.getStartupScript()
	if script:
		scripts['startup.py'] = script
	
	script = client_script_config.getShutdownScript()
	if script:
		scripts['shutdown.py'] = script

	timer_scripts = client_script_config.getTimerScripts()
	for timer_script in timer_scripts:
		suffix, serialized = encode({
			'enabled': timer_script.isEnabled(),
			'timing': 'delay' if timer_script.isFixedDelay() else 'rate',
			'period': timer_script.getDelay(),
			'threading': 'shared' if timer_script.isSharedThread() else 'dedicated',
			})
		scripts['timer/%s%s' % (timer_script.getName(), suffix)] = serialized
		scripts['timer/%s.py' % timer_script.getName()] = timer_scripts[timer_script]
	
	for tag_script in client_script_config.getTagChangeScripts():
		suffix, serialized = encode({
			'name': tag_script.getName(),
			'tags': [tag_path for tag_path in tag_script.getPaths()],
			'triggers': [t.toString() for t in tag_script.getChangeTypes()],
			'enabled': tag_script.isEnabled(),
			})
		scripts['tag-change/%s%s' % (tag_script.getName(), suffix)] = serialized
		scripts['tag-change/%s.py' % tag_script.getName()] = tag_script.getScript()
		
	message_scripts = client_script_config.getMessageHandlerScripts()
	for message_script in message_scripts:
		suffix, serialized = encode({
				'name': message_script.getName(),
				'threading': str(message_script.getThreadType()),
				'enabled': message_script.isEnabled(),
			})
		scripts['message/%s%s' % (message_script.getName(),suffix)] = serialized
		scripts['message/%s.py' % message_script.getName()] = message_scripts[message_script]
	
	return scripts

	
def extract_clientevents(resource_objects):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'
	
	client_script_config = resource_objects[0]
	
	scripts = {}
	
	script = client_script_config.getStartupScript()
	if script:
		scripts['startup.py'] = script
	
	script = client_script_config.getShutdownScript()
	if script:
		scripts['shutdown.py'] = script
	
	script = client_script_config.getShutdownAllowedScript()
	if script:
		scripts['shutdown-intercept.py'] = script

	key_schema_pattern = re.compile("(\[(?P<modifiers>.*)\] )?(?P<key>.*) \((?P<action>.*)\)")
	key_modifier_pattern = re.compile("(Button \d|\w+)")
	
	key_scripts = client_script_config.getKeyScripts()
	for kix, key_script in enumerate(key_scripts):
		key_config = key_schema_pattern.match(key_script.getDisplay()).groupdict()
		suffix, serialized = encode({
			'action': key_config['action'],
			'key': key_config['key'].replace("'", ''),
			'modifiers': key_modifier_pattern.findall(key_config['modifiers']) if key_config['modifiers'] else []
			})
		scripts['key/%s%s' % (key_script.getDisplay(), suffix)] = serialized
		scripts['key/%s.py' % key_script.getDisplay()] = key_scripts[key_script]
	
	timer_scripts = client_script_config.getTimerScripts()
	for timer_script in timer_scripts:
		suffix, serialized = encode({
			'enabled': timer_script.isEnabled(),
			'timing': 'delay' if timer_script.isFixedDelay() else 'rate',
			'period': timer_script.getDelay(),
			'threading': 'shared' if timer_script.isSharedThread() else 'dedicated',
			})
		scripts['timer/%s%s' % (timer_script.getName(), suffix)] = serialized
		scripts['timer/%s.py' % timer_script.getName()] = timer_scripts[timer_script]
	
	for tag_script in client_script_config.getTagChangeScripts():		
		suffix, serialized = encode({
			'name': tag_script.getName(),
			'tags': [tag_path for tag_path in tag_script.getPaths()],
			'triggers': [t.toString() for t in tag_script.getChangeTypes()],
			'enabled': tag_script.isEnabled(),
			})
		scripts['tag-change/%s%s' % (tag_script.getName(), suffix)] = serialized
		scripts['tag-change/%s.py' % tag_script.getName()] = tag_script.getScript()
	
	def traverse_menu(parent_path, menu_node, mutable_dict):
		for mix, child in enumerate(menu_node.getChildren() or []):			
			suffix, serialized = encode({
					'name': child.getName(),
					'icon': child.getIconPath(),
					'mnemonic': child.getMnemonic(),
					'description': child.getDescription(),
					'accelerator': child.getAccelerator(),
				})
			mutable_dict['%s/entry-%02d%s' % ('/'.join(parent_path), mix, suffix)] = serialized
			mutable_dict['%s/entry-%02d.py' % ('/'.join(parent_path), mix)] = child.getScript()

			traverse_menu(parent_path + [child.getName() or ('Submenu-%02d' % mix)], child, mutable_dict)
	
	menu_root = client_script_config.getMenuRoot()
	traverse_menu(['menu'], menu_root, scripts)
	
	message_scripts = client_script_config.getMessageHandlerScripts()
	for message_script in message_scripts:
		suffix, serialized = encode({
				'name': message_script.getName(),
				'threading': str(message_script.getThreadType()),
				'enabled': message_script.isEnabled(),
			})
		scripts['message/%s%s' % (message_script.getName(), suffix)] = serialized
		scripts['message/%s.py' % message_script.getName()] = message_scripts[message_script]
	
	return scripts


def extract_namedquery(resource_objects):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'
	
	named_query = resource_objects[0]
	
	info = {
		'query': named_query.getQuery(),
		'database': named_query.getDatabase() or '-default-',
		'parameters': dict(
			(param.getIdentifier(), {
				'sql_type'    : str(param.getSqlType()),
				'type'      : str(param.getType()),
				'identifier': str(param.getIdentifier()),
			}) 
			for param 
			in named_query.getParameters()
		),
		'type': named_query.getType(),
	}

	return dict([
		('.sql', format_sql(info['query'])),
		encode(info),
		])

		
def extract_project_script(resource_objects):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'
	
	script = resource_objects[0]
	
	return {
		'.py': script,
		}
	
	
# Ready for the dispatcher
EXTRACTORS = {
	  'sr.script.project': extract_project_script,
			'named-query': extract_namedquery,
   'client.event.scripts': extract_clientevents,
		  'event.scripts': extract_gatewayevents,
	 'project/properties': extract_project_props,
	}
