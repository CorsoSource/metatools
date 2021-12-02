from shared.tools.pretty import pdir, p, prettify
from shared.tools.meta import getFunctionCallSigs
from shared.tools.sidecar import SimpleREST
from shared.tools.global import ExtraGlobal

from ast import literal_eval
from cgi import escape
import re, sys, os

try:
	from com.inductiveautomation.ignition.gateway import SRContext as GateawayContext
except ImportError:
	from com.inductiveautomation.ignition.gateway import IgnitionGateway as GatewayContext 


GLOBAL_CACHE_TIMEOUT = 600
WHITELIST_GLOBALS = set(['shared', 'system', 'fpmi', 're'])
WHITELIST_LOCALS = set([]) #'context'])


class CrowbarREST(SimpleREST):


	def do_GET(self):
		try:
			self._do_GET()
		except Exception, error:
			system.util.getLogger('Crowbar').error(repr(error))
			
			
	def _do_GET(self):
		debug = ''

		host, port = self.server.server_address
		endpoint_url = 'http://%s:%s/' % (host, port)

		#endpoint_url = 'https://localhost.corso.systems:8043/main/system/webdev/Debugger/context/'
		#endpoint_url = 'https:%s' % (str(request['servletRequest'].httpURI).partition('?')[0],)

		params = self.params or {}

		statement = params.get('eval', '')

		session = ExtraGlobal.setdefault(port, 'Sidecar', {}, lifespan=GLOBAL_CACHE_TIMEOUT)

		session_aliases = session.setdefault('aliases', {})
		statement_history = session.setdefault('statement_history', [])

		#context = session.setdefault('context', SRContext.get())

		while statement in statement_history:
			statement_history.remove(statement)
		statement_history.append(statement)

		#	from java.util import Collections
		#	debug = """Debug:
		#		|%r
		#		|%s
		#		""" % (
		#			context.getModuleManager().getModules().__class__,
		#			isinstance(context.getModuleManager().getModules(), Collections),
		#		)

		try:
		#		global_scope = globals().copy() # ['app', 'shared', 'system', 'fpmi', 'doGet']
		#		local_scope = locals().copy() # 	
		#				['request', 'session_aliases', 'os', 'prettify', 'session', 'pdir', 
		#				 'session_id', 'global_scope', 'sys', 'params', 'p', 'ExtraGlobal', 
		#				 'literal_eval', 're', 'endpoint_url', 'statement', 'context', 
		#				 'getFunctionCallSigs', 'escape']

			global_scope = session.get('global_scope', {})
			if not global_scope:
				for var_name in WHITELIST_GLOBALS:
					try:
						global_scope[var_name] = globals()[var_name]
					except KeyError:
						pass

			local_scope = session.get('local_scope', {})
			if not local_scope:
				for var_name in WHITELIST_LOCALS:
					try:
						local_scope[var_name] = locals()[var_name]
					except KeyError:
						pass

			local_scope.update(session_aliases)
			
			local_scope['context'] = GatewayContext.get()
			
			# Make calculations stick around by seeing what's changed.
			local_things_before = local_scope.keys()
			
			try:
				code = compile(statement, '<pretty-eval>', 'eval')
				result = eval( code , global_scope , local_scope )
			except SyntaxError:
				code = compile(statement, '<pretty-eval>', 'exec')
				result = eval( code , global_scope , local_scope )
			
			for new_thing in (set(local_scope.keys()) - set(local_things_before)):
				session_aliases[new_thing] = local_scope[new_thing]

			error = ''
			if 'alias' in params:
				session_aliases[params['alias']] = result
				
		except Exception, error:
			# https://stackoverflow.com/a/1278740/11902188
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback_details = {
				 'filename': exc_traceback.tb_frame.f_code.co_filename,
				 'lineno'  : exc_traceback.tb_lineno,
				 'name'    : exc_traceback.tb_frame.f_code.co_name,
				 'type'    : exc_type.__name__,
				 'message' : exc_value.message, # or see traceback._some_str()
				}
			del(exc_type, exc_value, exc_traceback) 
			error = '%r\n\n%s' % (error, p(traceback_details, directPrint=False))
			result = None
			show = repr

		if result is None:
			result = ''

		# decode fails in 2.7 it seems, but not 2.5? Weird.
		output_p = p(result, ellipsisLimit=120, directPrint=False)
		try:
			output_p = output_p.decode('utf8')
		except:
			pass
		output_p = '<br>'.join(escape(output_p).splitlines())
	
		output_pdir = pdir(result, ellipsisLimit=120, directPrint=False)
		try:
			output_pdir = output_pdir.decode('utf8')
		except:
			pass
		output_pdir = '<br>'.join(escape(output_pdir).splitlines())

		AUTO_ATTRIBUTE_PATTERN = re.compile(r'^(\W*)(\w+)(\W+.*)$', re.M)
		IDENTIFIER_PATTERN = re.compile(r'([a-z0-9A-Z.]+)(@[a-f0-9]+)')
		CLASS_PATTERN      = re.compile(escape(r'(\<|(com|java|org)\.)([a-z0-9._]+)(\.[a-z0-9_]+)(\>|\.\.\.|)'), re.I)

		auto_attribute_span = r'\1<span style="color:green">\2\3</span>'

		lines = []
		for line in output_pdir.split('<br>'):
			m = AUTO_ATTRIBUTE_PATTERN.match(line)
			if m:
				whitespace, attribute, remainder = m.groups()
				if attribute == attribute.upper():
					line = '<span style="color:gray">%s</span>' % line			
				elif len(attribute) > 1:
					attribute = attribute[0].upper() + attribute[1:]
					if any('%s%s%s' % (whitespace, suffix, attribute) in output_pdir for suffix in 'get is to'.split()):
						line = AUTO_ATTRIBUTE_PATTERN.sub(auto_attribute_span, line)
			
			line = IDENTIFIER_PATTERN.sub(r'\1<span style="color:darkblue">\2</span>', line)
			line = CLASS_PATTERN.sub(r'<span style="color:goldenrod">\1\3<span style="color:khaki">\4</span>\5</span>', line)	
			
			lines.append(line)
		output_pdir = '<br>'.join(lines)
			
		# add easy clicks
		getter_pattern = re.compile(r'^(\W*)(get)(\w+)', re.M)
		getter_url = r'\1<span style="color:green">\2</span><a href="%s?eval=%s.\2\3()" style="color:cyan;text-decoration:none">\3</a>' % (endpoint_url, statement)
		output_pdir = '<br>'.join(
			getter_pattern.sub(getter_url, line)
			for line
			in output_pdir.split('<br>')
			)

		session_alias_datalist = []
		for alias in session_aliases:
			escaped_option = escape(alias.decode('utf8'))
			session_alias_datalist.append('   <option value="%s">%s</option>' % (escaped_option, escaped_option))
		session_alias_datalist = '\n'.join(session_alias_datalist)

		statement_history_datalist = []
		for ix, prev_statement in enumerate(reversed(statement_history)):
			escaped_option = escape(prev_statement.decode('utf8'))
			statement_history_datalist.append('   <option value="%s">[%d] %s</option>' % (
											  escaped_option, len(statement_history) - ix - 1, escaped_option))
		statement_history_datalist = '\n'.join(statement_history_datalist)

		del result
		del session_aliases
		del statement_history

		output = """
		<html>
		<head>
		<meta charset="UTF-8" />
		</head>
		<body style="font-family:consolas;font-size:10px; background-color:black; color:lime;">
		<form action="%(endpoint_url)s"
		      style="font-family:consolas;font-size:12px; background-color:black; color:yellow;">
		Statement: 
			<input type="text" name="eval"  id="eval"  list="statements" value="%(statement)s" autofocus
			 style="font-family:consolas;font-size:12px; background-color:black; color:yellow; width:700px; height:30px">
		=&gt;
			<input type="text" name="alias" id="alias" list="aliases" value=""
			 style="font-family:consolas;font-size:12px; background-color:black; color:yellow; width:120px; height:30px">
		<input type="submit" style="visibility: hidden;" />
		<datalist id="aliases">
		   %(session_alias_datalist)s
		</datalist>
		<datalist id="statements">
		   %(statement_history_datalist)s
		</datalist>
		</form>
		<div style="font-family:consolas;font-size:10px; background-color:black; color:lightgray;">
		<pre>%(debug)s</pre>
		</div>
		<div style="font-family:consolas;font-size:10px; background-color:black; color:red;">
		<pre>%(error)s</pre>
		</div>
		<div style="font-family:consolas;font-size:10px; background-color:black; color:cyan;">
		<pre>%(output_p)s</pre>
		</div>
		<div style="font-family:consolas;font-size:10px; background-color:black; color:lime; overflow-y: auto; height: 950px">
		<pre>%(output_pdir)s</pre>
		</div>
		</body>
		</html>
		""" % locals()

		self.respond_html(output)
		
		
## Example tag event script
#if any([
#	initialChange,
#	missedEvents,
#	]):
#	return
#
#port = int(tagPath.rpartition(' ')[2])
#
#if currentValue.value:	
#	from shared.tools.sidecar import launch_sidecar
#	from shared.tools.crowbar import CrowbarREST
#	
#	server_thread = launch_sidecar(port, CrowbarREST, hostname='127.0.0.1', resume_session=False)
#	
#else:
#	from shared.tools.sidecar import shutdown
#	shutdown(port)
##		from shared.tools.thread import dangerouslyKillThreads
##		dangerouslyKillThreads('Sidecar.*', bypass_interlock = 'Yes, seriously.')
