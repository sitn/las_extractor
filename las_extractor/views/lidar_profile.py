# -*- coding: UTF-8 -*-
# Adapted from c2c raster profile tool
# SITN, 2013

import sys, os, subprocess, csv, math, threading
from datetime import datetime
import geojson
import numpy as np

from pyramid.view import view_config
from pyramid.i18n import TranslationStringFactory
import pyramid.i18n

from shapely.geometry import LineString
import shapefile 
from datetime import datetime
from pyramid.response import Response, FileResponse
from zipfile import ZipFile as zip
import pkg_resources
from las_extractor.util.point_cloud_profiler import *
from las_extractor.util.temp_file_manager import remove_old_files

import sys

@view_config(route_name='lidar_profile', renderer='jsonp')
def lidar_profile(request):
    """
        Extract LiDAR point cloud profile from buffered polyline and return json file. Also stores the result
        as .csv and .kml temporary file for export fonctionnality

        Tile selection uses postgis polygon intersection. The postgis tile layer requires a attributes pointing to the tile file name
        Recommended tile size is about 50 meters
        
        v1 => v2 Change log
        - Replace call to Fusion PolyClipData.exe by Python loop (using liblas)

        SITN 2013-2014
    """

    _ = request.translate

    # Get resolution settings
    resolution = request.registry.settings['resolution']

    # Get configuration values
    if 'code' in request.params and request.params['code'] == resolution[0]['intranet_code']:
        maxLineDistance = resolution[1]['max_line_distance']
        bufferSizeMeter = resolution[1]['buffer_size']
    else:
        maxLineDistance = resolution[2]['max_line_distance']
        bufferSizeMeter = resolution[2]['buffer_size']

    # limit calculation time to avoid server meltdown...
    maxCalculationTime = request.registry.settings['timeout']

    # required paths 
    outputDir = request.registry.settings['lidar_output_dir'].replace('\\', '/')  
    dataDirStandard = request.registry.settings['lidar_data']
    dataDirNormalized = request.registry.settings['lidar_data_normalized']
    outputCsv = str(uuid.uuid4()) + '.csv' 
    # global variables
    classesNames = {}
    classesList = []  
    jsonOutput=[]
    csvOut = open(outputDir + outputCsv, 'w')
    csvOut.write('distance,altitude,x,y,class\n') # csv file header

    # remove files if older than 10 minutes
    errorMessage = remove_old_files(outputDir, 600)

    if errorMessage != '':
        logFile = open(outputDir + 'lock.log','a')
        logFile.write(str(datetime.now()) + ': ' + errorMessage +'\n')
        logFile.close()

    if outputDir == 'overwriteme' or dataDirStandard == 'overwriteme' or dataDirNormalized == 'overwriteme':
        csvOut.close()
        errorMsg = '<b>' + _('ERROR') + ':</b><p>'
        errorMsg +=  _('Paths not defined in buildout for one of the following variables: ')
        errorMsg += 'outputDir, lidar_data, lidar_data_normalized </p>'
        return {'Warning': errorMsg}

    # Read the profile line posted by the client
    geom = geojson.loads(request.params['geom'], object_hook=geojson.GeoJSON.to_instance)

    # Choose the correct data set and set up the correct variables
    dataType = request.params['dataType'] 
    if dataType == 'standard':
        dataDir = dataDirStandard

        # check if the remote disk is connected
        if not os.path.exists(dataDir):
            csvOut.close()
            errorMsg = '<b>' + _('ERROR') + ':</b><p>'
            errorMsg +=  _('LiDAR data directory not accessible') + '</p>'
            return {'Warning': errorMsg}

    elif dataType == 'normalized':
        dataDir = dataDirNormalized
        # check if the remote disk is connected
        if not os.path.exists(dataDir):
            csvOut.close()
            errorMsg = '<b>' + _('ERROR') + ':</b><p>'
            errorMsg += _('LiDAR data directory not accessible') + '</p>'
            return {'Warning': errorMsg}

    classesNames = request.registry.settings['classes_names_' + dataType]

    # Full line received from client: if too long: return error in order to avoid a client's overflow
    fullLine = LineString(geom.coordinates)
    if fullLine.length > maxLineDistance:
        csvOut.close()
        errorMsg = '<b>' + _('WARNING') + '</b>: <p>' + _('The profile you draw is ')
        errorMsg += str(math.ceil(fullLine.length * 1000) / 1000) + 'm ' +_('long') +', '
        errorMsg +=  _('max allowed length is') +': ' + str(maxLineDistance) + 'm </p>'
        return {'Warning': errorMsg}
    
    # ***Point cloud extractor, V2***
    jsonOutput, zMin, zMax, checkEmpty = pointCloudExtractorV2(geom.coordinates, bufferSizeMeter, outputDir, dataDir, jsonOutput, csvOut, classesList, classesNames)
    
    # If no tile is found in the area intersected by the segment, return error message
    if checkEmpty == 0:
        csvOut.close()
        errorMsg = '<b>' + _('WARNING') + '</b>: <p>'
        errorMsg +=  _('The profile you draw is entirely outside the data extent') + '</p>'
        return {'Warning': errorMsg}
    
    lineZMin = np.min(np.array(zMin))
    lineZMax = np.max(np.array(zMax))

    csvOut.close()

    return {
        'profile': jsonOutput,
        'series':classesList,
        'csvId': outputCsv,
        'zRange': {
            'zMin':lineZMin,
            'zMax':lineZMax
        }
    }

@view_config(route_name='lidar_csv')
def lidar_csv(request):
    """
        Read the csv file stored at profile creation time, and return it
    """
    outputDir = request.registry.settings['lidar_output_dir'].replace('\\','/') 
    csvFileId = request.params['csvFileUID']
    return FileResponse(outputDir + csvFileId, request = request, content_type = 'text/csv; charset=utf-8')

@view_config(route_name='lidar_kml')
def lidar_kml(request):
    """
        Read the csv file stored on disk and transform it to kml
    """

    markerUrl = request.static_url('las_extractor:static/images/googleearthview/')
    outputDir = request.registry.settings['lidar_output_dir'].replace('\\', '/') 
    csvFileId = request.params['csvFileUID']

    classesNames = request.registry.settings['classes_names_'+request.params['dataType']]

    csvData = open(outputDir+csvFileId)
    outputKml = outputDir + str(uuid.uuid4()) + '.kml'

    is_generated = csv2kml(
        csvData,
        markerUrl,
        outputKml,
        classesNames,
        request.registry.settings['kml_colors']
    )

    if is_generated is False:
        strResult = [
           u'<?xml version="1.0" encoding="UTF-8"?>',
            u'<kml xmlns="http://www.opengis.net/kml/2.2">',
            u'<Document><Placemark><name>Point</name>',
            u'<description>Ce point est simulé car le serveur ne supporte pas la',
            u' création de fichier KML.</description>',
            u'<Point><coordinates>6.86835,46.90513,0</coordinates>',
            u'</Point></Placemark></Document></kml>'
        ]
        strResult = ''.join(strResult)
    else:
        data = open(outputKml)
        strResult = ''
        for row in data:
            strResult+= str(row)
        csvData.close() 
    return Response(strResult, headers={
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename="lidarprofil.kml"'
    })

@view_config(route_name='lidar_shp')
def lidar_shp(request):
    """
        Transform the profile line (2D) to ESRI shapefile
    """

    # set up paths
    geom = geojson.loads(request.params['geom'], object_hook =  geojson.GeoJSON.to_instance)
    outputDir = request.registry.settings['lidar_output_dir'].replace('\\', '/') 
    outputShp= outputDir + str(uuid.uuid4())

    # Create pyshp polyline ESRI shapfile and write it to disk
    shapeParts = []
    outShp = shapefile.Writer(shapefile.POLYLINE)
    outShp.line(parts=[geom.coordinates])
    outShp.field('FIRST_FLD','C','40')
    outShp.record('First','Line')
    outShp.save(outputShp)

    # zip the shapefile for nice single output
    zipShp = zip(outputShp +'.zip', mode='w')
    zipShp.write(outputShp + '.shp', os.path.basename(outputShp + '.shp'))
    zipShp.write(outputShp + '.dbf', os.path.basename(outputShp + '.dbf'))
    zipShp.write(outputShp + '.shx', os.path.basename(outputShp + '.shx'))
    zipShp.close()

    # remove files
    os.remove(outputShp + '.shx')
    os.remove(outputShp + '.shp')
    os.remove(outputShp + '.dbf')

    return FileResponse(outputShp + '.zip', request = request, content_type = 'application/zip')