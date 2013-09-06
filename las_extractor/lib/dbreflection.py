# -*- coding: utf-8 -*-

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

def init(engine):
    """
Initialize the db reflection module. Give the declarative base
class an engine, required for the reflection.
"""
    Base.metadata.bind = engine