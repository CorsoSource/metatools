from __future__ import with_statement
import os, shutil, re

shared.tools.pretty.install()
#from shared.tools.pretty import p,pdir
from shared.tools.snapshot.utils import encode, getDesignerContext, hashmapToDict

from com.sepasoft.webservice.common.service.variables import WSType


def extract_restendpoint(resource_objects):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'
	
	rest_endpoint = resource_objects[0].getStorageObject()
	
	objects = {}
	
	config = {
		'format': rest_endpoint.getDataFormatType(),
		'encoding': rest_endpoint.getEncodingType(),
		'http': {
			'auth': rest_endpoint.getHTTPAuthType(),     # WHY YES, THAT _IS_ HTTP
			'method': rest_endpoint.getHttpMethodType(), # Why Yes, That _Is_ Http
			'ssl': rest_endpoint.isRedirectToSSL(),      # WHY YES, THAT _IS_ SSL
		},
		'name': rest_endpoint.getName(),
		'roles': [role for role in rest_endpoint.getRequiredRoles()],
		'userSource': rest_endpoint.getUserSource(),
		'path': rest_endpoint.getPath() or '',
	}
		
	objects.update(dict([encode(config)]))
	
	for method, script in hashmapToDict(rest_endpoint.getScripts()).items():
		if script:
			objects['.%s.py' % method] = script
	
	return objects


def resolve_rest_response_items(variables):
	
	vardefs = []
	
	for variable in variables:
		
		element = variable.getElement()
		
		vardef = {
			'name': variable.getName(),
			}
		
		element_type = element.getType()
		
		if element_type == WSType.Complex:
			if element.isArray():
				vardef['array'] = {
					'complex': resolve_rest_response_items(variable.getChildren()),
					}
			else:
				vardef['complex'] = resolve_rest_response_items(variable.getChildren())
		
		elif element_type == WSType.Array:
			if element.isComplexArray():
				vardef['array'] = {
					'complex': resolve_rest_response_items(variable.getChildren()[0].getChildren()),
					}
			else:
				vardef['array'] = element.getDataType(),
			
		elif element_type == WSType.Simple:
			vardef['datatype'] = element.getDataType()
			if vardef['datatype'] in ('Float4', 'Float8', 'DateTime'):
				vardef['format'] = element.getFormat()			
		
		else:
			raise NotImplementedError('var type %s' % element_type)
	
		vardefs.append(vardef)
		
	return vardefs	


def extract_global_restconfiguration(resource_objects):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'
	
	rest_config = resource_objects[0].getStorageObject()

	config = {
		'name': rest_config.getName(),	
		}
	
	definition = rest_config.getDefinition()
	
	options = definition.getOptions()
	
	config['options'] = {
		'url': options.getURL(),
		'method': options.getHttpMethodType(),
		'format': options.getDataFormatType(),
		'encoding': options.getEncodingType(),
		'querySpaceEscape': str(options.getQuerySpaceEscape()).rpartition('(')[2][:-1],
		'timeout': options.getTimeout(),
		'retries': options.getMaxRetries(),
		'bypassCertValidation': options.isBypassCertValidation(),
		'httpErrorReporting': options.isHTTPErrorReportingEnabled(),
		}
		
	if options.getHTTPAuthType():
		config['auth'] = {
			'type': options.getHTTPAuthType(),
			'user': options.getHTTPAuthUserName(),
#			'pass': options.getHTTPAuthPassword(), # maybe make this an option?
			}
	
	
	request_items = rest_config.getRequestItems()
	request_config = {
		'Request Header': [],
		'URL Resource Path': [],
		'URL Query String': [],
		}
		
	for variable in request_items.getVariable().getChildren():
		element = variable.getElement()
		
		vardef = {
			'name': variable.getName(),
			'datatype': element.getDataType(),
#			'type': element.getTypeName(),
			}
		
		if vardef['datatype'] in ('Float4', 'Float8', 'DateTime'):
			vardef['format'] = element.getFormat()
		
		if variable.isBound():
			vardef['binding'] = {
				'type': variable.getBindType(),
				'expression': variable.getExpression(),
				}
		else:
			vardef['value'] = variable.getValue()
		
		request_config[element.getTypeName()].append(vardef)
	
	config['request'] = request_config
	
	config['response'] = resolve_rest_response_items(rest_config.getResponseItems().getVariable().getChildren())
	
	return dict([
		encode(config)
		])


def resolve_soap_request_items(variables):
	
	vardefs = []
	
	for variable in variables:
		
		element = variable.getElement()
		
		vardef = {
			'name': variable.getName(),
			'nillable': element.getNillable(),
			}
		
		element_type = element.getType()
		
		if element.isMinOccursDefined():
			vardef['minOccurs'] = element.getMinOccurs()
		if element.isMaxOccursDefined():
			vardef['maxOccurs'] = element.getMaxOccurs()
		
		if element.hasRestriction():
			vardef['minLength'] = element.getMinLength()
			vardef['maxLength'] = element.getMaxLength()
		
		if element_type == WSType.Complex:
			if element.isArray():
				vardef['array'] = {
					'complex': resolve_soap_request_items(variable.getChildren()),
					}
			else:
				vardef['complex'] = resolve_soap_request_items(variable.getChildren())
		
		elif element_type == WSType.Array:
			if element.isComplexArray():
				vardef['array'] = {
					'complex': resolve_soap_request_items(variable.getChildren()[0].getChildren()),
					}
			else:
				vardef['array'] = element.getDataType(),
			
		elif element_type == WSType.Simple:
			vardef['datatype'] = element.getDataType()
			
			if vardef['datatype'] in ('Float4', 'Float8', 'DateTime'):
				vardef['format'] = element.getFormat()
				
				if element.getTypeName() == 'decimal':
					vardef['totalDigits'] = element.getTotalDigits()
					vardef['fractionDigits'] = element.getFractionDigits()
				
		else:
			raise NotImplementedError('var type %s' % element_type)
	
		vardefs.append(vardef)
		
	return vardefs	


def extract_global_soapconfiguration(resource_objects):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'
	
	soap_config = resource_objects[0].getStorageObject()

	configuration = {
		'name': soap_config.getName(),	
		}
	
	definition = soap_config.getDefinition()

	options = definition.getOptions()
	
	configuration['options'] = {
		'url': options.getURL(),
		'port': soap_config.getPortName(),
		'operation': soap_config.getOperationName(),
		'encoding': options.getEncodingType(),
		'timeout': options.getTimeout(),
		'bypassCertValidation': options.isBypassCertValidation(),
		'httpErrorReporting': options.isHTTPErrorReportingEnabled(),
		
		'namespace': definition.getTargetNamespace(),
		}
		
	if options.getHTTPAuthType():
		configuration['auth'] = {
			'type': options.getHTTPAuthType(),
			'user': options.getHTTPAuthUserName(),
#			'pass': options.getHTTPAuthPassword(), # maybe make this an option?
			}
	
	if options.isWSSEnabled():
		configuration['wsSecurity'] = {
				'user': options.getWSSUserName(),
#				'pass': options.getWSSPassword(),
				'type': options.getWSSPasswordType(),
				'ttl': options.getWSSTimeToLive(),
			}

	operation = soap_config.getOperation()
	
	configuration['action'] = operation.getSoapAction()
	
	body = operation.getBodyVariable()
	
	configuration['request'] = resolve_soap_request_items(body.getChildren())
	
	return dict([
		encode(configuration)
		])



# Ready for the dispatcher
EXTRACTORS = {
	  'soapconfiguration': extract_global_soapconfiguration,
	  'restconfiguration': extract_global_restconfiguration,
	       'restendpoint': extract_restendpoint,
	}





#context = getDesignerContext()
#	
#global_project = context.getGlobalProject().getProject()
#designer_project = context.getProject()
#
#global_resources = dict(
#	('%s/%s' % (resource.getResourceType(), global_project.getFolderPath(resource.getResourceId())) or '', resource)
#	for resource
#	in global_project.getResources()
#	)
#
#project_resources = dict(
#	('%s/%s' % (resource.getResourceType(), designer_project.getFolderPath(resource.getResourceId())) or '', resource)
#	for resource
#	in designer_project.getResources()
#	)
#
#
#
#
#deserializer = context.createDeserializer()
#
##resource = global_resources['restendpoint/REST Endpoints/lodestar/v1/materials/area/line-sequence/swap']
##resource = global_resources['restconfiguration/REST Configurations/TCI/getTCI']
##resource = global_resources['restconfiguration/REST Configurations/Some RESTful Config']
#resource = global_resources['soapconfiguration/SOAP Configurations/SAP/getBOH']
#
#
#data_context = deserializer.deserializeBinary(resource.getData())
#resource_objects = [obj for obj in data_context.getRootObjects()]
#
##ep = resource_objects[0].getStorageObject()
##rest_config = resource_objects[0].getStorageObject()
#soap = resource_objects[0].getStorageObject()
#
#
#options = soap.getDefinition().getOptions()
#
#
#operation = soap.getOperation()
#
#
#extract_global_soapconfiguration(resource_objects)
