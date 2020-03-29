import unittest, doctest

from shared.tools.logging import BaseLogger

doctest.run_docstring_examples(BaseLogger()._generateMessage,globals())
doctest.run_docstring_examples(BaseLogger()._formatString, globals(), optionflags=doctest.ELLIPSIS)
doctest.run_docstring_examples(BaseLogger()._bracketString, globals())