# -*- coding: utf-8 -*-

from pyramid.config import Configurator
from pyramid.renderers import JSONP

from sqlalchemy import engine_from_config

import sqlahelper

import yaml

from las_extractor.lib import dbreflection

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """

    engine = engine_from_config(
        settings,
        'sqlalchemy.')
    sqlahelper.add_engine(engine)

    dbreflection.init(engine)

    settings.setdefault('mako.directories','las_extractor:templates')
    settings.setdefault('reload_templates',True)

    settings.update(yaml.load(file(settings.get('app.cfg'))))

    config = Configurator(settings=settings)
    
    config.add_subscriber('las_extractor.i18n.add_renderer_globals',
                      'pyramid.events.BeforeRender')
    config.add_subscriber('las_extractor.i18n.add_localizer',
                      'pyramid.events.NewRequest')

    config.add_translation_dirs('las_extractor:locale/')

    config.add_renderer('jsonp', JSONP(param_name='callback'))

    config.add_static_view('static', 'static', cache_max_age=3600)

    config.add_route('home', '/')

    config.add_route('lidar_profile', '/lidar/profile')
    config.add_route('lidar_csv', '/lidar/lidarprofil.csv')
    config.add_route('lidar_kml', '/lidar/kml')
    config.add_route('lidar_shp', '/lidar/shp.zip')
    config.add_route('lidar','/lidar')

    config.scan()
    return config.make_wsgi_app()

