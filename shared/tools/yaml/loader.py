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


__all__ = ['BaseLoader', 'FullLoader', 'SafeLoader', 'Loader', 'UnsafeLoader']

from shared.tools.yaml.reader import *
from shared.tools.yaml.scanner import *
from shared.tools.yaml.parser import *
from shared.tools.yaml.composer import *
from shared.tools.yaml.constructor import *
from shared.tools.yaml.resolver import *

class BaseLoader(Reader, Scanner, Parser, Composer, BaseConstructor, BaseResolver):

	def __init__(self, stream):
		Reader.__init__(self, stream)
		Scanner.__init__(self)
		Parser.__init__(self)
		Composer.__init__(self)
		BaseConstructor.__init__(self)
		BaseResolver.__init__(self)

class FullLoader(Reader, Scanner, Parser, Composer, FullConstructor, Resolver):

	def __init__(self, stream):
		Reader.__init__(self, stream)
		Scanner.__init__(self)
		Parser.__init__(self)
		Composer.__init__(self)
		FullConstructor.__init__(self)
		Resolver.__init__(self)

class SafeLoader(Reader, Scanner, Parser, Composer, SafeConstructor, Resolver):

	def __init__(self, stream):
		Reader.__init__(self, stream)
		Scanner.__init__(self)
		Parser.__init__(self)
		Composer.__init__(self)
		SafeConstructor.__init__(self)
		Resolver.__init__(self)

class Loader(Reader, Scanner, Parser, Composer, Constructor, Resolver):

	def __init__(self, stream):
		Reader.__init__(self, stream)
		Scanner.__init__(self)
		Parser.__init__(self)
		Composer.__init__(self)
		Constructor.__init__(self)
		Resolver.__init__(self)

# UnsafeLoader is the same as Loader (which is and was always unsafe on
# untrusted input). Use of either Loader or UnsafeLoader should be rare, since
# FullLoad should be able to load almost all YAML safely. Loader is left intact
# to ensure backwards compatibility.
class UnsafeLoader(Reader, Scanner, Parser, Composer, Constructor, Resolver):

	def __init__(self, stream):
		Reader.__init__(self, stream)
		Scanner.__init__(self)
		Parser.__init__(self)
		Composer.__init__(self)
		Constructor.__init__(self)
		Resolver.__init__(self)
