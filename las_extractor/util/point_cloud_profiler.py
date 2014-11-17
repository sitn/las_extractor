# -*- coding: UTF-8 -*-
# Helping functions for point cloud profiler
# SITN, 2013-2014

import shapefile, csv, os, math, time
import numpy as np
from shapely.geometry import LineString
import uuid
from liblas import file
from datetime import datetime

try:
    import osgeo.ogr as ogr
    import osgeo.osr as osr
    osgeo_loaded = True
except ImportError:
    osgeo_loaded = False

import simplekml
from geoalchemy import WKTSpatialElement, WKBSpatialElement
from las_extractor.models import DBSession, LidarTileIndex

# Get the las file tiles intersected by the buffered profile's line
def generate_tile_list(line, bufferSizeMeter, outputDir, fileList, dataDir):

    # Create buffer around Segment
    polygon = line.buffer(bufferSizeMeter)
    tileList = []

    # Intersect the buffer with the tile index
    wktsPolygon = WKTSpatialElement(str(polygon), 21781)
    intersectResult = DBSession.query(LidarTileIndex).filter(LidarTileIndex.geom.intersects(wktsPolygon)).all()

    # Read the query result and store the path to tiles files into ascii file
    checkEmpty = 0
    for row in intersectResult:
        checkEmpty += 1
        tileList.append(dataDir + str(row.file.strip() + '.las'))

    return polygon, checkEmpty, tileList 

# Read the numpy data and append them to json-serializable list  
def generate_json(profile, jsonOutput, csvOut, classesList, classesNames):

    id = 0
    for row in profile:
        id += 1
        classifName = classesNames[row[4]]
        # csv output
        csvOut.write(str(row[0])+','+str(row[1])+','+str(row[2])+','+str(row[3])+','+str(row[4])+'\n')

        if classifName not in classesList:
            classesList.append(classifName)
        serie = classifName

        # json output
        jsonOutput.append({
            'dist': round(row[0]*100) / 100,
            'values': {
                serie: round(row[1]*100) / 100
            },
            'x': round(row[2]*100)/100,
            'y': round(row[3]*100)/100
        })
    
def pointCloudExtractorV2(coordinates, bufferSizeMeter, outputDir, dataDir, jsonOutput, csvOut, classesList, classesNames, perfLogStr):
    
    distanceFromOrigin = 0
    zMin = []
    zMax = []
    # Iterate over line segments
    for i in range(0, len(coordinates) -  1):
    
        # Store the results of the points extraction for current segment
        exctractedPoints = []
        # generate unique names for output filenames
        fileList = 'fileList_' + str(uuid.uuid4()) + '.txt'
        intersectPolygon = 'intersectPolygon_' + str(uuid.uuid4())
        outputLas = 'ouputlas_' + str(uuid.uuid4()) + '.las'
        outputTxt = 'ouputtxt_' + str(uuid.uuid4()) + '.txt'

        # Segment start and end coordinates
        xyStart = coordinates[i]
        xyEnd = coordinates[i + 1]
    
        # current line segment
        segment = LineString([xyStart, xyEnd])

        # generate the tile list intersected by the buffer around the segment segment
        beforeRequest = datetime.now()
        polygon, checkEmpty, tileList = generate_tile_list(segment, bufferSizeMeter, outputDir, fileList, dataDir)
        afterRequest = datetime.now()
        perfLogStr += '***********PG REQUEST TIME*************\n'
        perfLogStr += str(afterRequest - beforeRequest) + '\n'
        
        # Point Cloud extractor V2
        seg = {'y1': xyStart[1], 'x1': xyStart[0], 'y2': xyEnd[1], 'x2': xyEnd[0]}
        
        # Vector parallel to segment
        xOA = seg['x2'] - seg['x1']
        yOA = seg['y2'] - seg['y1']

        table = []
        
        startIterateTile = datetime.now()
        for tile in tileList:
            cloud = file.File(tile, mode = 'r')
            # iterate over cloud's points
            for p in cloud:
                # Needs enhancements...
                if p.x <= max(seg['x1'] + bufferSizeMeter, seg['x2'] + bufferSizeMeter) \
                and p.x >= min(seg['x1'] - bufferSizeMeter, seg['x2'] - bufferSizeMeter) \
                and p.y <= max(seg['y1'] + bufferSizeMeter, seg['y2'] + bufferSizeMeter) \
                and p.y >= min(seg['y1'] - bufferSizeMeter, seg['y2'] - bufferSizeMeter):
                    xOB = p.x - seg['x1']
                    yOB = p.y - seg['y1']
                    hypo = math.sqrt(xOB * xOB + yOB * yOB)
                    cosAlpha = (xOA * xOB + yOA * yOB)/(math.sqrt(xOA * xOA + yOA * yOA) * hypo)
                    alpha = math.acos(cosAlpha)
                    normalPointToLineDistance = math.sin(alpha) * hypo
                    # Filter for normal distance smaller or equal to buffer size
                    if normalPointToLineDistance <= bufferSizeMeter:
                        exctractedPoints.append({'x': p.x, 'y': p.y, 'z': p.z, 'classification': p.classification})
                        lineList = [p.x, p.y, p.z, cosAlpha, p.classification]
                        table.append(lineList)
            cloud.close()

        stopIterateTile = datetime.now()
        perfLogStr += '*********ITERATE OVER TILE AND POINTS TIME*************\n'
        perfLogStr += str(stopIterateTile - startIterateTile) + '\n'
        # Convert the list into numpy array for fast sorting
        data = np.array(table)

        # copy the coordinates into new variables
        xvalues = np.copy(data[:, 0])
        yvalues = np.copy(data[:, 1])
        
        # translate the LiDAR points' coordinates to the segment origin
        data[:,0] = data[:, 0] - xyStart[0]
        data[:,1] = data[:, 1] - xyStart[1]

        # Add and arrange all required values into numpy array and project points on segment vector
        profile = np.transpose(np.array([np.sqrt(data[:, 0] * data[:, 0] + data[:, 1] * data[:, 1]) * data[:, 3] \
            + distanceFromOrigin, data[:, 2], xvalues, yvalues, data[:, 4], data[:, 3]]))

        # Sort distances in increasing order
        profile = profile[profile[:, 0].argsort()]
        
        # profile = generate_numpy_profile(exctractedPoints, xyStart, xyEnd, distanceFromOrigin)
        
        # increment the distance from the line origin
        distanceFromOrigin += segment.length

        # store segment min/max z value
        zMin.append(np.min(profile[:,1]))
        zMax.append(np.max(profile[:,1]))

        # Read the numpy data and append them to json-serializable list
        generate_json(profile, jsonOutput, csvOut, classesList, classesNames)
        
    return jsonOutput, zMin, zMax, checkEmpty, perfLogStr
    
# Export csv output file to google kml 3D
def csv2kml(csvFile, markerUrl, outputKml, classesNames, kmlColors):
        """
        CSV (EPSG: 21781) to  KML  (EPSG:432 tranformation
        """

        if osgeo_loaded is False:
            return False

        # OGR projections
        ch1903 = osr.SpatialReference()
        ch1903.ImportFromEPSG(21781)
        google = osr.SpatialReference()
        google.ImportFromEPSG(4326)

        # Read data from CSV file and output them to KML
        csv.register_dialect('pcl', delimiter=',', skipinitialspace=0)
        reader = csv.reader(csvFile, dialect='pcl')
        reader.next()
        kml = simplekml.Kml()

        for row in reader:  
            # Create OGR geometry
            ogrPoint = ogr.Geometry(ogr.wkbPoint)
            ogrPoint.AddPoint(float(row[2]), float(row[3]))
            ogrPoint.AssignSpatialReference(ch1903)
            ogrPoint.TransformTo(google)
            # Write KML using simple kml tiny library
            kmlPoint = kml.newpoint(name=classesNames[float(row[4])])
            kmlPoint.coords = [(ogrPoint.GetX(), ogrPoint.GetY(), row[1])]
            kmlPoint.altitudemode = simplekml.AltitudeMode.absolute
            kmlPoint.style.labelstyle.color = simplekml.Color.black
            kmlPoint.style.labelstyle.scale = 0.0
            kmlPoint.style.iconstyle.scale = 0.2
            kmlPoint.style.iconstyle.icon.href = markerUrl + kmlColors[float(row[4])]
        kml.save(outputKml)
        return True
