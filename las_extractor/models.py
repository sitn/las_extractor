# -*- coding: utf-8 -*-

import sqlahelper


from sqlalchemy import (
    Column,
    Integer
    )

from papyrus.geo_interface import GeoInterface
from geoalchemy import GeometryColumn, Geometry
    
Base = sqlahelper.get_base()
DBSession = sqlahelper.get_session()

class LidarTileIndex(GeoInterface, Base):
    __tablename__='grid50mfull'
    __table_args__ = {'schema': 'lidar_tile_index', 'autoload': True}
    id=Column('oid', Integer, primary_key=True)
    geom = GeometryColumn(Geometry(srid=21781))


