from pyramid.response import Response
from pyramid.view import view_config

@view_config(route_name='home', renderer='index.mako')
def home(request):
    
    return {'one':'toto', 'project':'las_extractor'}
