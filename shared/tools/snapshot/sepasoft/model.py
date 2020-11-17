from shared.tools.snapshot.utils import encode, getDesignerContext

from java.lang import Object
from com.sepasoft.production.common.model.storage import ConvertLog
CONVERTLOG_PLACEHOLDER = ConvertLog(Object())


MES_TYPES = set(['cell', 'cell_group', 'line', 'area', 'site', 'enterprise'])


def trace_equipment_path(item, resolved_model):
	
	parent = resolved_model.get(item['Parent Production Item UUID'], None)
	if parent:
		return trace_equipment_path(parent, resolved_model) + [item['Name']]
	else:
		return [item['Name']]


def resolve_model_item(resource_objects):

	storage_item = resource_objects[0]
	production_item = storage_item.convertToProductionItem('some string', CONVERTLOG_PLACEHOLDER)
	
	configuration = {
		'Name': production_item.getName(),
		'Type': production_item.getProductionType(),
		}
	
	if not production_item.getEnabled():
		configuration['enabled'] = False
	
	properties = production_item.getProperties()
	property_ids = properties.getPropertyIDs()
	for prop_name in property_ids.keySet():
		prop_id = property_ids[prop_name]
		prop_value = production_item.getPropertyValue(prop_id)
		if prop_value:
			configuration[prop_name] = prop_value
	
	for entries in production_item.getEntryProperties():
		entry_list = configuration[entries.getDisplayName()] = []
		
		entry_property_names = [eep.getPropertyName()
								for eep in entries.getEntryEditProperties()]
		
		for entry_key in entries.getEntries():
			entry = entries.getEntries()[entry_key]
			
			entry_list.append(dict(
				(eep, entry.getPropertyValue(eep))
				for eep in entry_property_names
				if not entry.getPropertyValue(eep) in (None, '')
				))
			
	return configuration
		
		

def extract_production_model(global_project, category='', context=None):
	if context is None:
		context = getDesignerContext()
	
	deserializer = context.createDeserializer()

	mes_resources = {}
	for resource in global_project.getResources():
		resource_type = resource.getResourceType()
		if not resource_type in MES_TYPES:
			continue
		
		data_context = deserializer.deserializeBinary(resource.getData())
		resource_objects = [obj for obj in data_context.getRootObjects()]
	
		model_item_config = resolve_model_item(resource_objects)
		model_item_config['Parent Production Item UUID'] = repr(resource.getParentUuid())
		mes_resources[model_item_config['Production Item UUID']] = model_item_config

	extracted_resources = {}
	for pmi_uuid, model_item_config in mes_resources.items():
		
		equipment_path = '/'.join(trace_equipment_path(model_item_config, mes_resources))
		dest_path = model_item_config['Equipment Path'] = equipment_path
		dest_path = 'production_model' + '/' + dest_path
		if category:
			dest_path = category + '/' + dest_path
		extracted_resources[dest_path] = dict([encode(model_item_config)])
		
	return extracted_resources
	
	
# Ready for the dispatcher
BULK_GLOBAL_EXTRACTORS = [extract_production_model]
