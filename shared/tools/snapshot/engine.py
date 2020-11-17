"""
	Snapshot versioning of Ignition resources
	
	Take stuff in Ignition and put it to disk using words. 
	Then let other programs read those words and tell you what's different!
	
	This is a one-way utility: it dumps TO disk, FROM Ignition.
	  It could go the other way too in _some_ circumstances, but that's not the goal.
	The goal here is to make it possible to comprehensively and confidently know
	  what is different between two projects (or one project's differences over time).
	  And with enough cleverness, you can inspect history and compare many projects!
"""

from __future__ import with_statement
import os, shutil, re

from shared.tools.snapshot.utils import getDesignerContext


# Load in extractors
RESOURCE_EXTRACTORS = {
	'__folder': None,
	}

BULK_GLOBAL_EXTRACTORS = []
BULK_PROJECT_EXTRACTORS = []

_EXTRACTORS = [
	'shared.tools.snapshot.ia.global',
	'shared.tools.snapshot.ia.project',
	# 'shared.tools.snapshot.ia.reporting',
	'shared.tools.snapshot.ia.tags',
	'shared.tools.snapshot.ia.vision',
	'shared.tools.snapshot.ia.webdev',
	'shared.tools.snapshot.sepasoft.webservices',
	'shared.tools.snapshot.sepasoft.model',
	]

_HOTLOADING_SCOPE = 'bootstrap.'

for module_path in _EXTRACTORS:
	try:
		assert module_path.startswith(_HOTLOADING_SCOPE), "Extractors are expected to be hot loaded from the `%s` scripts." % _HOTLOADING_SCOPE
		module = reduce(getattr, module_path.split('.')[1:], shared)

		RESOURCE_EXTRACTORS.update(getattr(module, 'EXTRACTORS', {}))
		BULK_GLOBAL_EXTRACTORS += getattr(module, 'BULK_GLOBAL_EXTRACTORS', [])
		BULK_PROJECT_EXTRACTORS += getattr(module, 'BULK_PROJECT_EXTRACTORS', [])
	except:
		pass

	
def nop_dict(*args, **kwargs):
	return {}


def extract_resources(resources, category='', context=None):
	"""Extract resource data. Category prepends to each resource's path"""
	if context is None:
		context = getDesignerContext()
	
	deserializer = context.createDeserializer()
	
	extracted_data = {}
	
	for res_path, resource in resources.items():
		res_type = resource.getResourceType()
		extractor = RESOURCE_EXTRACTORS.get(res_type, None)
		
		if not extractor:
			#print 'No extractor for %s' % res_type
			continue
		
		try:
			data_context = deserializer.deserializeBinary(resource.getData())
		except SerializationException, error:
			print 'Resource did not deserialize: %s\n%r (type: %s)' % (res_path, resource, res_type)
			print '    Err: %r' % error
			
		resource_objects = [obj for obj in data_context.getRootObjects()]
		
		dest_path, _, _ = res_path.rpartition('/')
		
		try:
			res_name = resource.getName()
			if res_name:
				dest_path += '/' + res_name
		except:
			pass

		if category:
			dest_path = category + '/' + dest_path
		
		# Gather any extra bits of context if the extractor needs it
		# (Skip the first, since it will always be resource_objects)
		keyword_arguments = {}
		num_extra_args = extractor.func_code.co_argcount-1
		if num_extra_args:
			for kwarg in extractor.func_code.co_varnames[1:][:num_extra_args]:
				keyword_arguments[kwarg] = locals()[kwarg]
		extracted_data[dest_path] = extractor(resource_objects, **keyword_arguments)
			
	return extracted_data


def dump_extracted_resources(destination_folder, extracted_data, purge_first=False):
	"""
	Dump the contents of the given extracted data into the destination folder.
	If purge_first is set True, then the destination will be deleted before dumping.
	"""
	if purge_first and os.path.exists(destination_folder):
		for subdir in os.listdir(destination_folder):
			if subdir.startswith('.'):
				continue
			
			try:
				shutil.rmtree(destination_folder + '/' + subdir)
			except OSError:
				print 'Destination folder not completely purged - check for open files!'
			
	for resource_path, resource_details in extracted_data.items():
		resource_path, _, name = resource_path.rpartition('/')
		
		destination = '%s/%s' % (destination_folder, resource_path)
				
		for suffix, data in resource_details.items():
			
			if suffix.startswith('.'):
				filepath = '%s/%s%s' % (destination, name, suffix)
			else:
				filepath = '%s/%s' % (destination, suffix)

			if data is None:
				print 'No data! %s' % filepath
				continue


			if not os.path.exists(filepath.rpartition('/')[0]):
				os.makedirs(filepath.rpartition('/')[0])
			
			with open(filepath, 'wb') as f:
				f.write(data)
				

def coredump(destination_folder):
	#destination_folder = 'C:/Workspace/temp/extraction-2'

	context = getDesignerContext()
		
	global_project = context.getGlobalProject().getProject()
	designer_project = context.getProject()

	global_resources = dict(
		('%s/%s' % (resource.getResourceType(), global_project.getFolderPath(resource.getResourceId())) or '', resource)
		for resource
		in global_project.getResources()
		)
	
	project_resources = dict(
		('%s/%s' % (resource.getResourceType(), designer_project.getFolderPath(resource.getResourceId())) or '', resource)
		for resource
		in designer_project.getResources()
		)
	
	extracted_resources = {}
	
	extracted_resources['project/properties'] = RESOURCE_EXTRACTORS['project/properties'](context)
	
	extracted_resources.update(extract_resources(global_resources, 'global'))
	extracted_resources.update(extract_resources(project_resources, 'project'))
	
	for bulk_extractor in BULK_GLOBAL_EXTRACTORS:
		extracted_resources.update(bulk_extractor(global_project))

	for bulk_extractor in BULK_PROJECT_EXTRACTORS:
		extracted_resources.update(bulk_extractor(designer_project))
		
	dump_extracted_resources(destination_folder, extracted_resources, purge_first=True)
	
