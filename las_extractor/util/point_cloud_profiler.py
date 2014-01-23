# -*- coding: UTF-8 -*-
# Helping function for point cloud profiler
# SITN, 2013

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

# Generate the tile liste required by Fusion POlyClipData.exec
def generate_tile_list(line, bufferSizeMeter, outputDir, fileList, dataDir):
    # Create Shapely LineString object for the current segment

    # Create buffer around Segment
    polygon = line.buffer(bufferSizeMeter) 

    # Intersect the buffer with the tile index
    wktsPolygon = WKTSpatialElement(str(polygon), 21781)
    intersectResult = DBSession.query(LidarTileIndex).filter(LidarTileIndex.geom.intersects(wktsPolygon)).all()

    # Read the query result and store the path to tiles files into ascii file
    l = open(outputDir + fileList,'w')
    checkEmpty = 0
    for row in intersectResult:
        checkEmpty += 1
        l.write(dataDir + str(row.file.strip() + '.las\n')) 
    l.close()

    return polygon, checkEmpty

# Transform the Shapely buffer object into ESRI shapefile (required by FUSION Tools) 
def write_polygon_shapefile(polygon, outputDir, intersectPolygon):

    pointList = list(polygon.exterior.coords) 
    shapeParts = []
    for point in pointList:
        xy = list(point)
        shapeParts.append(list(point)) 
    outPolygon = shapefile.Writer(shapefile.POLYGON)
    outPolygon.poly(parts=[shapeParts])
    outPolygon.field('FIRST_FLD', 'C', '40')
    outPolygon.record('1')
    outPolygon.save(outputDir+intersectPolygon)
    del outPolygon
 
# Arrange the data into numpy array and use fast sorting functionnalities
def generate_numpy_profile(outputDir, outputTxt, xyStart, xyEnd, distanceFromOrigin):

    # Segment vector (referential change)
    xOB = xyEnd[0] - xyStart[0]
    yOB = xyEnd[1] - xyStart[1]

    # Read the fusion tools output and create the json output
    csvData = open(outputDir+outputTxt)
    csv.register_dialect('pcl', delimiter=' ', skipinitialspace=0)
    reader = csv.reader(csvData, dialect='pcl')
    lineList = []
    table = []

    # Iterate over extracted LiDAR points
    for row in reader:
        x = float(row[0])
        y = float(row[1])
        z = float(row[2])
        classif = int(row[3])
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
    csvData.close()

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

# remove temporary file written to disk during procedure
def remove_temp_files(outputDir, fileList, intersectPolygon, outputLas, outputTxt):
    os.remove(outputDir+fileList)
    os.remove(outputDir+intersectPolygon+'.shp')
    os.remove(outputDir+intersectPolygon+'.shp.idx')
    os.remove(outputDir+intersectPolygon+'.shx')
    os.remove(outputDir+intersectPolygon+'.dbf')
    os.remove(outputDir+outputLas)
    os.remove(outputDir+outputTxt)
    
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
