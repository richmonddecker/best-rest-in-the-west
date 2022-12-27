import cgi, types
from json import loads, dumps
from copy import deepcopy
from urllib import parse as urlparse

from gevent.pywsgi import WSGIServer
import gevent

from api import UserAPI

def parseAndDelistArguments(args):
    if isinstance(args, str) and args[:1] in ['{', '[']:
        args = loads(args)
    if isinstance(args, list):
        return args
    else:
        args = urlparse.parse_qs(args)
    return delistArguments(args)


def delistArguments(args):
    '''
        Takes a dictionary, 'args' and de-lists any single-item lists then
        returns the resulting dictionary.
        {'foo': ['bar']} would become {'foo': 'bar'}
    '''
    
    def flatten(k, v):
        if len(v) == 1 and isinstance(v, list):
            return (str(k), v[0])
        return (str(k), v)

    return dict([flatten(k, v) for k, v in args.items()])


VALID_VERSIONS = ['v1.0']

def application(env, start_response):

    api = UserAPI()

    path = env['PATH_INFO']

    if path == '/':
        start_response('302 Moved Temporarily', [('Location', 'http://blueboard.com')])
        return ''

    if path == '/favicon.ico': 
        start_response('301 Moved Permanently', [('Location', 'http://blueboard.com/favicon.ico')])
        return ''
    
    path = path.split('/')
    if len(path) < 2 or path[1] != 'v1.0':
        start_response('400 Bad Request', [('Content-Type', 'text/plain')])
        return f'Invalid API version in URL: {path[1]}\nCurrently supported version(s): {", ".join(VALID_VERSIONS)}'

    path = path[2:]
    if not path[-1]: path.pop()

    if path[0] != 'users':
        start_response('400 Bad Request', [('Content-Type', 'text/plain')])
        return f'Endpoint /{path[0]} does not exist. This API supports only the /users endpoint.'

    method = env['REQUEST_METHOD'].upper()
    
    args = parseAndDelistArguments(env['QUERY_STRING'])

    wsgi_input = env['wsgi.input']

    if wsgi_input.content_length and method != 'PUT':
        post_env = env.copy()
        post_env['QUERY_STRING'] = ''
        form = cgi.FieldStorage(
            fp=env['wsgi.input'],
            environ=post_env,
            keep_blank_values=True
        )
        form_data = [(k, form[k].value) for k in form.keys()]
        args.update(form_data)

    try:
        if method == 'PUT':
            wsgi_input = wsgi_input.read()
            args.update(parseAndDelistArguments(wsgi_input))
            response = api.update_user(path[1], args)
            if response is None:
                start_response('404 Not Found', [('Content-Type', 'text/plain')])
                return f'No user found with specified uuid: {path[1]}'

        if method == 'GET':
            if len(path) > 1:
                response = api.get_users(path[1])
                if response is None:
                    start_response('404 Not Found', [('Content-Type', 'text/plain')])
                    return f'No user found with specified uuid: {path[1]}'
            else:
                response = api.get_users()
        
        if method == 'POST':
            response = api.create_user(args)
        
        if method == 'DELETE':
            response = api.delete_user(path[1])
            if response[0] is None:
                start_response('404 Not Found', [('Content-Type', 'text/plain')])
                return f'No user found with specified uuid: {path[1]}'
            if response[1] is not None:
                raise Exception(f"Failed to delete requested user: {path[1]}")
            response = "user deleted successfully"

        ret = { 
            'path' : path,
            'args' : args,
            'method' : method,
            'response': response #the output of the functions you call
        }
        start_response('200 OK', [('Content-Type', 'application/json')])
        return dumps(ret)

    except Exception as inst:
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return str(inst)


def formatted_application(env, start_response):
    return iter([application(env, start_response).encode()])


if __name__ == '__main__':
    wsgi_port = 8000
    print('serving on %s...' % wsgi_port)
    WSGIServer(('', wsgi_port), formatted_application).serve_forever()
