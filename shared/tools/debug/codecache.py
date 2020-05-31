from __future__ import with_statement

from shared.tools.meta import MetaSingleton
from shared.tools.debug.frame import find_root_object, normalize_filename

import system
import sys

from functools import wraps

# Attempt to make the code syntax highlightable
# Backported version of Pygments available at
#   https://github.com/CorsoSource/jython-2.5-backports
try:
	from pygments import highlight
	from pygments.lexers import PythonLexer
	from pygments.formatters import HtmlFormatter

	import re

	highlight_html_strip_pattern = re.compile(r"""
				((/\*|<!--).*?(\*/|-->)
			|	(<(meta|!)[^>]+?>)
			|	(<(title|h2)>.*?</(title|h2)>))
			""",re.X + re.S)
	linenumber_format_pattern = re.compile(r'(<div class="linenodiv".*?)(background-color: #)([a-f0-9]{6});')

	replace_linenumber_format = lambda html: linenumber_format_pattern.sub(r'\g<1>\g<2>000000; color:#ffffff; ', html)

	PYTHON_LEXER = PythonLexer(stripall=True, tabsize=4)

	def syntax_highlight(code, highlight_lines=[], start_line=1, style='monokai'):
		formatter = HtmlFormatter(
			linenos='table', 
			style=style,
			hl_lines=highlight_lines,
			linenostart=start_line,
			wrapcode=True,
			full=True,
			lineseparator='<br>',
			noclasses=True,
			)
					
		html = highlight(code, PYTHON_LEXER, formatter)

		html = highlight_html_strip_pattern.sub('', html)
		html = replace_linenumber_format(html)
		
		return html.strip()

# In case Pygments is not installed, passthru
except ImportError:

	def syntax_highlight(code, *args):
		return code


def cached(function):
	"""Decorator for classmethods that can cache their inputs."""
	@wraps(function)
	def check_cache_first(cls, *args):
		if not args in cls._cache:
			code = function(cls, *args)
			if code:
				cls._cache[args] = code
				return code
		else:
			return cls._cache[args]
		return None
	return check_cache_first


class MetaCodeCache(type):
	"""The CodeCache is another kinda-like-a-module classes. 
	Because it's Jython (and Ignition), it's useful to encapsulate state
	  inside a class instead of module. The module mechanics are just a bit
	  difficult to reason on, given how state is shared between threads,
	  so this pattern helps a bit.

	Plus it cuts down on so many @classmethod calls and makes it easier to
	  make this a singleton. CodeCache is meant to be serve the same purpose
	  as linecache, and so a little bit of magic isn't too bad, I think.
	"""


	# cache keys are based on what the _code_* functions need.
	_cache = {}

	_default_sys_context = sys

	TAB_STOP = 4


	def __getitem__(cls, location):
		if isinstance(location, slice):
			return cls._dispatch_frame(location.start, sys_context=location.stop)
		return cls._dispatch_frame(location)


	def get_line(cls, frame, sys_context=None):
		"""Retrieve the line of code at the frame location."""
		code = cls._dispatch_frame(frame)

		if not code: 
			return ''
		
		return code.splitlines()[frame.f_lineno]
		

	def get_lines(cls, frame, radius=5, sys_context=None):
		"""Retreive the lines of code at the frame location.

		If radius is 0, return all the code in that frame's file.
		Otherwise, return radius lines before and after the frame's
		  active line, clamping to the start/end of the code block.
		"""
		code_lines, start_line = cls.get_lines_with_start(frame, radius, sys_context)
		return code_lines


	def get_lines_with_start(cls, frame, radius=5, sys_context=None):
		"""Retreive the lines of code at the frame location as a tuple of code and the starting line.
		(Use this in case the radius blocks to a different initial offset)
	
		If radius is 0, return all the code in that frame's file.
		Otherwise, return radius lines before and after the frame's
		  active line, clamping to the start/end of the code block.
		"""
		code = cls._dispatch_frame(frame)
	
		if not code: 
			return []
		else:
			code_lines = code.splitlines()
	
		if not radius:
			return code_lines, 1
		else:
			block_slice = cls._calc_block_ends(frame.f_lineno, len(code_lines), radius)
			return code_lines[block_slice], block_slice.start		


	@staticmethod
	def _calc_block_ends(line_number, list_length, radius):
		"""Calculate ends assuming a full block is preferred at ends"""
		start = line_number - radius
		end = line_number + radius + 1
	
		# Realign if over/undershot
		if start < 0:
			end -= start
			start = 0
		if end >= list_length:
			start -= end - list_length
			end = list_length
			
		# Clamp to limits
		if start < 0:
			start = 0
		if end >= list_length:
			end = list_length
		
		return slice(start, end)

	
	def _render_tabstops(cls, code_lines):
		"""Replace tab characters with spaces to align to tab stops."""
		rendered_lines = []
		
		for line in code_lines:
			rendered = ''
			while '\t' in line:
				pre, tab, line = line.partition('\t')
				rendered += pre
				rendered += ' '*(cls.TAB_STOP - (len(rendered) % cls.TAB_STOP))
			rendered += line
			rendered_lines.append(rendered)
		return rendered_lines
		

	def _dispatch_frame(cls, frame, sys_context=None):
		"""Resolve and make sense of the location given. 

		It may be "module:shared.tools.debug.codecache" or perhaps 
		  a vague "event:actionPerformed". This function will make sense of this
		  in the Ignition environment, backtracing as needed.

		Note that this caches after resolving objects. This is because name references
		  may be ambiguous or change as the stack mutates.
		"""
		location = normalize_filename(frame.f_code.co_filename)

		if ':' in location:
			script_type, _, identifier = location.partition(':')

			if script_type == 'module':
				return cls._code_module(identifier, sys_context)

			elif script_type == 'event':
				component = find_root_object('event', frame).source
				return cls._code_event(component, identifier)

			elif script_type == 'tagevent':
				tag_path = find_root_object('tagPath', frame)
				tag_event = 'ASDFASDF'
				raise NotImplementedError('Tag file path needs to be final parsed for the event')
				return cls._code_tag_event(tag_path, tag_event)

			elif script_type == 'WebDev':
				return cls._code_webdev(location)
		
		return None


	@cached
	def _code_file(cls, filepath):
		with open(filepath, 'r') as f:
			return f.read()


	@cached
	def _code_event(cls, component, event_name):

		ic = None
		ic_comp = component
		while not ic and ic_comp:
			try:
				ic = getattr(ic_comp, 'getInteractionController')()
			except:
				ic_comp = ic_comp.parent

		assert ic_comp, "Interaction controller not found - backtrace failed."
		
		for adapter in ic.getAllAdaptersForTarget(component):
			if adapter.getMethodDescriptor().getName() == event_name:
				return adapter.getJythonCode()
		else:
			return None


	@cached
	def _code_module(cls, filename, sys_context=None):
	
		if sys_context is None:
			sys_context = cls._default_sys_context
		
		try:
			module = sys_context.modules[filename]
		except KeyError:
			# The Ignition environment puts the project library stuff in context
			#   so they're not _really_ modules - sometimes the full chain
			#   is not in sys.modules. Thus we'll get the root and pull from there.
			module_chain = filename.split('.')
			module = sys_context.modules[module_chain[0]]			
			for submodule_name in module_chain[1:]:
				module = getattr(module, submodule_name)
			
			# NOTE: the following reduce statement DOES NOT WORK.
			#   It's super inside baseball why, but the basic answer is that
			#   Jython effectively has a GIL for import statements, and Ignition
			#   sorta does the import mechanics during the getattr of it's 
			#   pseudo-modules. They don't quite block, but they're not done
			#   loading in, either. So we have to do a loop to let each
			#   getattr statement take as long as the mechanics need.
			# module = reduce(getattr, module_chain[1:], module)
			
		filepath = getattr(module, '__file__', None)
		if filepath:
			with open(filepath, 'r') as f:
				return f.read()

		code = getattr(module, 'code', None)
		if not code:
			code = getattr(module, 'code', None) # try in case load failed the first time and import mechanics lagged

		if code:
			return code
		
		return None


	@cached
	def _code_tag_event(cls, tag, event_name):
		if isinstance(tag, (str, unicode)):
			tag = system.tag.getTag(tag)
		return tag.getEventScripts().get(event_name)


	@cached
	def _code_webdev(cls, resource_path):
		"""Example frame.f_code.co_filename: 'WebDev: <Debugger/python:doGet>'"""
		raise NotImplimentedError("Need to explore context more to get source.")



class CodeCache(MetaSingleton):
	"""Similar to the linecache module in purpose, but makes sense of the Ignition environment.
	
	It caches the results for faster lookup.

	For example, the `frame.f_code.co_filename` may be `<event:actionPerformed>`.
	  This isn't enough information, so we need to backtrace to get the event object.
	  Though the project may have many of these, the `event` object nearest in the 
	  call stack is certainly the one of interest. It's `event.source` is what fired
	  it, and if we go up the `.parent` tree enough, we'll find the interaction
	  controller that has the adapters that has the source code in them.

	  That's a bit involved, hence the caching.
	"""
	__metaclass__ = MetaCodeCache



def trace_entry_line(frame, indent='  '):
	out = '%s(%d)' % (frame.f_code.co_filename, frame.f_lineno)

	out += frame.f_code.co_name or '<lambda>'

	out += repr(frame.f_locals.get('__args__'), tuple())

	return_value = frame.f_locals.get('__return__', None)
	if return_value:
		out += '->' + repr(return_value)

	line = CodeCache.get_line(frame)
	if line:
		out += ': ' + line.strip()
	return out