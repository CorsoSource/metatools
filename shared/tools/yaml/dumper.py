# PyYAML library
__license__ = 'MIT'
__author__ = 'Kirill Simonov'
__copyright__ = """
	Copyright (c) 2017-2020 Ingy döt Net
	Copyright (c) 2006-2016 Kirill Simonov
	"""

# For changes regarding this port for Ignition usage, please contact:
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


__all__ = ['BaseDumper', 'SafeDumper', 'Dumper']

from shared.tools.yaml.emitter import *
from shared.tools.yaml.serializer import *
from shared.tools.yaml.representer import *
from shared.tools.yaml.resolver import *

class BaseDumper(Emitter, Serializer, BaseRepresenter, BaseResolver):

	def __init__(self, stream,
			default_style=None, default_flow_style=False,
			canonical=None, indent=None, width=None,
			allow_unicode=None, line_break=None,
			encoding=None, explicit_start=None, explicit_end=None,
			version=None, tags=None, sort_keys=True):
		Emitter.__init__(self, stream, canonical=canonical,
				indent=indent, width=width,
				allow_unicode=allow_unicode, line_break=line_break)
		Serializer.__init__(self, encoding=encoding,
				explicit_start=explicit_start, explicit_end=explicit_end,
				version=version, tags=tags)
		Representer.__init__(self, default_style=default_style,
				default_flow_style=default_flow_style, sort_keys=sort_keys)
		Resolver.__init__(self)

class SafeDumper(Emitter, Serializer, SafeRepresenter, Resolver):

	def __init__(self, stream,
			default_style=None, default_flow_style=False,
			canonical=None, indent=None, width=None,
			allow_unicode=None, line_break=None,
			encoding=None, explicit_start=None, explicit_end=None,
			version=None, tags=None, sort_keys=True):
		Emitter.__init__(self, stream, canonical=canonical,
				indent=indent, width=width,
				allow_unicode=allow_unicode, line_break=line_break)
		Serializer.__init__(self, encoding=encoding,
				explicit_start=explicit_start, explicit_end=explicit_end,
				version=version, tags=tags)
		SafeRepresenter.__init__(self, default_style=default_style,
				default_flow_style=default_flow_style, sort_keys=sort_keys)
		Resolver.__init__(self)

class Dumper(Emitter, Serializer, Representer, Resolver):

	def __init__(self, stream,
			default_style=None, default_flow_style=False,
			canonical=None, indent=None, width=None,
			allow_unicode=None, line_break=None,
			encoding=None, explicit_start=None, explicit_end=None,
			version=None, tags=None, sort_keys=True):
		Emitter.__init__(self, stream, canonical=canonical,
				indent=indent, width=width,
				allow_unicode=allow_unicode, line_break=line_break)
		Serializer.__init__(self, encoding=encoding,
				explicit_start=explicit_start, explicit_end=explicit_end,
				version=version, tags=tags)
		Representer.__init__(self, default_style=default_style,
				default_flow_style=default_flow_style, sort_keys=sort_keys)
		Resolver.__init__(self)
