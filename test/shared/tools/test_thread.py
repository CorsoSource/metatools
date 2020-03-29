import unittest, doctest


from shared.coros.thread import async


doctest.run_docstring_examples(async, globals(), optionflags=doctest.ELLIPSIS)