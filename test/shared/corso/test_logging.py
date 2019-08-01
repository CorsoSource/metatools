import unittest, doctest

from shared.corso.logging import BaseLogger

doctest.run_docstring_examples(BaseLogger()._generateMessage,globals())
doctest.run_docstring_examples(BaseLogger()._formatString, globals(), optionflags=doctest.ELLIPSIS)
doctest.run_docstring_examples(BaseLogger()._bracketString, globals())