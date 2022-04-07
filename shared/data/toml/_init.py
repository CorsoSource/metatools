"""Python module which parses and emits TOML.

Released under the MIT license.

For normal Ignition 8 support, just use

from shared.data.toml._init import *
"""

from shared.data.toml.decoder import load, loads, TomlDecoder
from shared.data.toml.encoder import dump, dumps, TomlEncoder

from shared.data.toml.decoder import TomlDecodeError, TomlPreserveCommentDecoder
from shared.data.toml.encoder import TomlArraySeparatorEncoder, TomlPreserveInlineDictEncoder, TomlNumpyEncoder, TomlPreserveCommentEncoder, TomlPathlibEncoder

__version__ = "0.10.2"
_spec_ = "0.5.0"
