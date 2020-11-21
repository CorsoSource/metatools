from shared.tools.thread import async
from shared.tools.global import ExtraGlobal

import BaseHTTPServer
from cgi import escape
import urlparse
import urllib


class SimpleServer(BaseHTTPServer.HTTPServer):
	allow_reuse_address = True
	
	def handle_error(self, request, client_address):
		system.util.getLogger('Sidecar').error('Error with %r: %r to [%r]' %(self, request, client_address))
#		request.send_response(400)
#		request.send_header("Content-type", "text/html")
#		request.end_headers()
#		request.wfile.write('Error executing %(command)s for %(client_address)s' % request)
	

class SimpleREST(BaseHTTPServer.BaseHTTPRequestHandler):

	def respond_html(self, html):
		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.end_headers()
		self.wfile.write(html)
	
	@staticmethod
	def html_escape(some_string):
		return escape(some_string.decode('utf8'))
	
	def __getitem__(self, attribute):
		"""Make this dict-like to simplify things a bit."""
		try:
			return getattr(self, attribute)
		except AttributeError:
			raise KeyError('%s is not available for this handler')
	
	@property
	def fields(self):
		try:
			length  = int(self.headers.getheader('content-length'))
			field_data = self.rfile.read(length)
			return urlparse.parse_qs(field_data)
		except:
			return None
			
	@property
	def params(self):
		query_string = urlparse.urlsplit(self.path)[3]
		params = {}
		for entry in query_string.split('&'):
			key,_,value = entry.partition('=')
			params[urllib.unquote(key)] = urllib.unquote(value)
		return params
		
		
def shutdown(port):
	session = ExtraGlobal.setdefault(port, 'Sidecar', {})
	session['shutdown'] = True
	

@async(name='Sidecar-REST')
def launch_sidecar(port, RestHandler, resume_session=True, session_timeout=600):
	"""
	This assumes that keep_running() is a function of no arguments which
	is tested initially and after each request.  If its return value
	is true, the server continues.
	"""
	system.util.getLogger('Sidecar').info("Launching sidecar on port %r with %r" % (port, RestHandler))
	
	if resume_session:
		session = ExtraGlobal.setdefault(port, 'Sidecar', {}, lifespan=session_timeout)
	else:
		ExtraGlobal.stash({}, port, 'Sidecar', lifespan=session_timeout)
		session = ExtraGlobal.access(port, 'Sidecar')
		
	server_address = ('localhost', port)
	httpd = SimpleServer(server_address, RestHandler)
	try:
		system.util.getLogger('Sidecar').info("Sidecar started on port %r" % (port,))

		while not ExtraGlobal.setdefault(port, 'Sidecar', {}, lifespan=session_timeout).get('shutdown', False):
			httpd.handle_request()
	except Exception, error:
		system.util.getLogger('Sidecar').info("Exception on port %r: %r" % (port,error))

	except:
		pass
	finally:
		#print 'Shutting down %r' % (httpd.server_address,)
		httpd.server_close()
		ExtraGlobal.trash(port, 'Sidecar') # clear session
		#print '... done!'
		system.util.getLogger('Sidecar').info("Sidecar torn down from port %r" % (port,))
