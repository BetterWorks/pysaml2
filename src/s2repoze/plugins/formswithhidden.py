import urlparse
import urllib
import cgi

from paste.httpheaders import CONTENT_LENGTH
from paste.httpheaders import CONTENT_TYPE
from paste.httpheaders import LOCATION
from paste.httpexceptions import HTTPFound
from paste.httpexceptions import HTTPUnauthorized

from paste.request import parse_dict_querystring
from paste.request import parse_formvars
from paste.request import construct_url

from paste.response import header_value

from zope.interface import implements

from repoze.who.interfaces import IChallenger
from repoze.who.interfaces import IIdentifier
from repoze.who.plugins.form import FormPlugin

_DEFAULT_FORM = """
<html>
<head>
  <title>GUI Log In</title>
</head>
<body>
  <div>
     <b>GUI Log In</b>
  </div>
  <br/>
  <form method="POST" action="?__do_login=true">
    <table border="0">
    <tr>
      <td>User Name</td>
      <td><input type="text" name="login"></input></td>
    </tr>
    <tr>
      <td>Password</td>
      <td><input type="password" name="password"></input></td>
    </tr>
    <tr>
      <td></td>
      <td><input type="submit" name="submit" value="Log In"/></td>
    </tr>
    </table>
    %s
  </form>
  <pre>
  </pre>
</body>
</html>
"""

hidden_pre_line = """<input type=hidden name="%s" value="%s">"""

class FormHiddenPlugin(FormPlugin):

    implements(IChallenger, IIdentifier)
    
    # IIdentifier
    def identify(self, environ):
        logger = environ.get('repoze.who.logger','')
        logger and logger.info("formplugin identify")
        logger and logger.info("environ keys: %s" % environ.keys())
        query = parse_dict_querystring(environ)
        # If the extractor finds a special query string on any request,
        # it will attempt to find the values in the input body.
        if query.get(self.login_form_qs): 
            form = parse_formvars(environ)
            from StringIO import StringIO
            # XXX we need to replace wsgi.input because we've read it
            # this smells funny
            environ['wsgi.input'] = StringIO()
            form.update(query)
            qinfo = {}
            for k, v in form.items():
                if k.startswith("_") and k.endswith("_"):
                    qinfo[k[1:-1]] = v
            if qinfo:
                environ["s2repoze.qinfo"] = qinfo
            try:
                login = form['login']
                password = form['password']
            except KeyError:
                return None
            del query[self.login_form_qs]
            query.update(qinfo)
            environ['QUERY_STRING'] = urllib.urlencode(query)
            environ['repoze.who.application'] = HTTPFound(
                                                    construct_url(environ))
            credentials = {'login':login, 'password':password}
            max_age = form.get('max_age', None)
            if max_age is not None:
                credentials['max_age'] = max_age
            return credentials

        return None

    # IChallenger
    def challenge(self, environ, status, app_headers, forget_headers):
        logger = environ.get('repoze.who.logger','')
        logger and logger.info("formplugin challenge")
        if app_headers:
            location = LOCATION(app_headers)
            if location:
                headers = list(app_headers) + list(forget_headers)
                return HTTPFound(headers = headers)
                
        query = parse_dict_querystring(environ)
        hidden = []
        for key,val in query.items():
            hidden.append(hidden_pre_line % ("_%s_" % key, val))

        logger and logger.info("hidden: %s" % (hidden,))
        form = self.formbody or _DEFAULT_FORM
        form = form % "\n".join(hidden)
            
        if self.formcallable is not None:
            form = self.formcallable(environ)
        def auth_form(environ, start_response):
            content_length = CONTENT_LENGTH.tuples(str(len(form)))
            content_type = CONTENT_TYPE.tuples('text/html')
            headers = content_length + content_type + forget_headers
            start_response('200 OK', headers)
            return [form]

        return auth_form


def make_plugin(login_form_qs='__do_login', rememberer_name=None, form=None):
    if rememberer_name is None:
        raise ValueError(
            'must include rememberer key (name of another IIdentifier plugin)')
    if form is not None:
        form = open(form).read()
    plugin = FormHiddenPlugin(login_form_qs, rememberer_name, form)
    return plugin
