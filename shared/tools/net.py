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
