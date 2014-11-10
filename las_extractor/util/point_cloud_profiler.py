# -*- coding: UTF-8 -*-
# Helping functions for point cloud profiler
# SITN, 2013-2014

import shapefile, csv, os, math, time
import numpy as np
from shapely.geometry import LineString

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
 
# Arrange the data into numpy array and use its fast sorting functionalities
def generate_numpy_profile(exctractedPoints, xyStart, xyEnd, distanceFromOrigin):
    
    lineList = []
    table = []
    # Segment vector (referential change)
    xOB = xyEnd[0] - xyStart[0]
    yOB = xyEnd[1] - xyStart[1]

    # Iterate over extracted LiDAR points
    for point in exctractedPoints:
        x = point['x']
        y = point['y']
        z = point['z']
        classif = point['classification']
        # segment origin - point vector
        xOA = x - xyStart[0]
        yOA = y - xyStart[1]
        # calculate the cosinus between the Origin - LiDAR point vector and the current segment
        cosAlpha = (xOA * xOB + yOA * yOB)/(np.sqrt(xOA * xOA + yOA * yOA) * np.sqrt( xOB * xOB + yOB * yOB))
        # store results into lists
        lineList = [x, y, z, cosAlpha, classif]
        table.append(lineList)

    # Convert the list into numpy array for fast sorting functionnalities
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

    return profile

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
            'dist': math.ceil(row[0]*1000) / 1000,
            'values': {
                serie: math.ceil(row[1]*1000) / 1000
            },
            'x': row[2],
            'y': row[3]
        })
    
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
