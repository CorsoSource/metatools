"""
	This is primarily a mixin to make keeping track of some utility functions easier
"""


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


def strip_angle_brackets(internal_name):
	if internal_name.startswith('<') and internal_name.endswith('>'):
		return internal_name[1:-1]
	else:
		return internal_name


def normalize_filename(filename):
	return strip_angle_brackets(filename)


def iter_frames(frame):
	while frame:
		yield frame
		frame = frame.f_back


def iter_frames_root(frame):
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
	for frame in iter_frames_root(frame):
		if obj_name in frame.f_locals:
			return frame.f_locals[obj_name]
	return None

