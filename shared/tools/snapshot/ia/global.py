"""
	Global resources
	
	Ignition before 8 always has a sort-of meta project called global that all other
	  projects can use and reference.
"""

from shared.tools.snapshot.utils import encode, propsetToDict


def extract_global_script(resource_objects):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'

	script = resource_objects[0]
	
	return {
		'.py': script,
		}
		
	
def extract_alarmpipeline(resource_objects):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'
	
	configuration = propsetToDict(resource_objects[0], recurse=True)
		
	return dict([
		encode(configuration),
		])


# Ready for the dispatcher
EXTRACTORS = {
	'sr.script.shared': extract_global_script,
	  'alarm-pipeline': extract_alarmpipeline,
	}