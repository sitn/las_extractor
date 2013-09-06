# -*- coding: utf-8 -*-

import sqlahelper


from sqlalchemy import (
    Column,
    Integer
    )

Base = sqlahelper.get_base()
DBSession = sqlahelper.get_session()



class Comment(Base):
    __tablename__ = 'comment'
    __table_args__ = {'schema': 'public', 'autoload': True}
    id = Column(Integer, primary_key=True)


