# -*- coding: utf-8 -*-

import sqlahelper


from sqlalchemy import (
    Column,
    Integer
    )

from geoalchemy2 import Geometry
    
Base = sqlahelper.get_base()
DBSession = sqlahelper.get_session()

class LidarTileIndex(Base):
    __tablename__='grid50mfull'
    __table_args__ = {'schema': 'lidar_tile_index', 'autoload': True}
    id=Column('oid', Integer, primary_key=True)
    geom = Column(Geometry("POLYGON", srid=21781))
