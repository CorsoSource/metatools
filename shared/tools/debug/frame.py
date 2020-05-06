"""
	This is primarily a mixin to make keeping track of some utility functions easier
"""

from shared.tools.debug.codecache import CodeCache


def strip_angle_brackets(internal_name):
	if internal_name.startswith('<') and internal_name.endswith('>'):
		return internal_name[1:-1]
	else:
		return internal_name


def iter_frames(frame):
	while frame:
		yield frame
		frame = frame.f_back


def iter_frame_root(frame):
	stack = list(iter_frames(frame))
	for frame in reversed(stack):
		yield frame


def find_object(obj_name, frame):
	"""Grab an item from the Python stack by its name, starting with the given frame."""
	# if no shortcut is provided, start at the furthest point
	for frame in iter_frames(frame):
		if obj_name in frame.f_locals:
			return frame.f_locals[obj_name]
	return None


def find_root_object(obj_name, frame):
	"""Grab an item from the Python stack by its name, starting with the given frame."""
	# if no shortcut is provided, start at the furthest point
	for frame in iter_frame_root(frame):
		if obj_name in frame.f_locals:
			return frame.f_locals[obj_name]
	return None


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