

def strip_angle_brackets(internal_name):
	if internal_name.startswith('<') and internal_name.endswith('>'):
		return internal_name[1:-1]
	else:
		return internal_name


def getEventSourceCode(component, event_name):
	event_name = strip_angle_brackets(event_name)

	ic = None
	ic_comp = component
	while not ic and ic_comp:
		try:
			ic = getattr(ic_comp, 'getInteractionController')()
		except:
			ic_comp = ic_comp.parent

	assert ic_comp, "Interaction controller not found - backtrace failed."
	
	for adapter in ic.getAllAdaptersForTarget(component):
		if adapter.getMethodDescriptor().getName() == event_name:
			return adapter.getJythonCode()
	else:
		return None


def getModuleCode(filename):
	filename = strip_angle_brackets(filename)

	if filename.startswith('module:'):
		filename = filename.partition(':')[2]
		
	try:
		return sys.modules[filename].code
	except:
		return None