"""
	A few simple quick wrappers for commonly asked network questions
"""

import socket
import telnetlib


LOCALHOST_HOSTNAME = ''
LOCALHOST_IP = '127.0.0.1'
LOCALHOST_DNS = 'localhost'


def default_hostname():
  """Returns the default hostname for the JVM's host."""
	try:
		return socket.gethostname()
	except: 
		return LOCALHOST_HOSTNAME


def default_ip():
  """Returns the default IP address of the JVM's host."""
	try:
		return socket.gethostbyname(
			socket.gethostname()
		)
	except:
		return LOCALHOST_IP


def default_dns_name():
  """Returns the/a default network name of the JVM's host."""
	try:
		return socket.gethostbyaddr(
			socket.gethostbyname(
				default_hostname()
			)
		)[0]
	except:
		return LOCALHOST_DNS


def gateway_name():
  """Returns the gateway's configured name"""
	return str(system.tag.read('[System]Gateway/SystemName').value)


def is_reachable(hostname, port):
	return bool(poke(hostname, port))


def poke(hostname, port, timeout=1.0, from_hostname='', from_port=0):
  """From THIS JVM check if the hostname:port is reachable.
  
  Fairly naive "throw a 'GET /' at it approach, but even an error helps.
  
  If returns True, the connection can _potentially_ be established. 
  If it returns False, the connection _probably_ doesn't work.
  
  Note that firewalls, routing, and all manner of odd edge cases can 
  make this confusing to interpret; this function merely tries "can TCP work *AT ALL*?"
  """
	try:
		sock = socket.create_connection(
			address=(hostname, port), 
			timeout=timeout,
			source_address=(from_hostname, from_port)
		)
		_ = sock.send('GET /')
	except:
		return None
	finally:
		try:
			sock.shutdown(socket.SHUT_RDWR)
			sock.close()
		except:
			pass
	return True


def poke_from_gateway(hostname, ports=tuple(), timeout=1.0,
		source_tag_provider='default', 
		poke_module='shared.tools.net', ):
	"""Ask what the gateway can see. We do this by forcing gateway JVM context via tag script.
	
	Returns a dict of ports and True/False for each poke.
	"""
	
	assert isinstance(hostname, str), 'hostname is a string, like "127.0.0.1" or "localhost"'
	
	random_test_id = str(uuid.uuid4())	

	if isinstance(ports, int):
		ports = (ports,)
	elif isinstance(ports, str):
		if ',' in ports:
			ports = tuple(int(port.strip()) for port in ports)
		else:
			ports = (int(ports.strip()),)
			
	assert all(isinstance(port, int) for port in ports), 'Ports must be numeric, like 80 or "80, 443"'
	
	added_folders = []
	
	tag_provider = '[%s]' % (source_tag_provider,)
	temp_tag_folder = 'TEMP/port-tests/%s' % (random_test_id,)
	base_folders = []
	base_path_parts = []
	for name in temp_tag_folder.split('/'):
		target_base_path = tag_provider + '/'.join(base_path_parts)
		target_folder_path = tag_provider + '/'.join(base_path_parts + [name])
		if not system.tag.exists(target_folder_path):
			system.tag.configure(target_base_path, [{'tagType': 'Folder', 'name': name}])
			added_folders.append(target_folder_path)
			
		base_path_parts.append(name)
	
	temp_tag_folder = tag_provider + '/'.join(base_path_parts)
	
	tag_configs = []
	tag_paths = []
	for port in ports:
		tag_name = 'port-%d' % (port,)
		tag_path ='%s/%s' % (temp_tag_folder, tag_name)
		tag_paths.append(tag_path)
		
		tag_config = {
			'dataType': 'Boolean',
			'name': tag_name,
#			'path': tag_path,
			'tagType': 'AtomicTag',
			'valueSource': 'memory',
			'eventScripts': [{
					'eventid': 'valueChanged',
					'script': """
	from %(poke_module)s import poke
	
	result = poke(%(hostname)r, %(port)r, %(timeout)r)
	
	system.tag.writeBlocking([tagPath], [result])
	""" % locals(),
			}],		
		}
		
		tag_configs.append(tag_config)
	
	print repr(tag_config)
	
	system.tag.configure(temp_tag_folder, tag_configs)

	sleep(timeout + 0.5)
	
	results = [tvq.value for tvq in system.tag.readAll(tag_paths)]
	
	# clean up mess
	for folder_path in reversed(sorted(added_folders)):
		system.tag.deleteTags([folder_path])
	
	return dict(
		(port, result)
		for port, result
		in zip(ports, results)
	)

#poke_from_gateway('127.0.0.1', [80, 443, 8088, 8089, 8043, 8060])
