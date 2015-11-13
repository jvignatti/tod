#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
geo_utils.py

Helper methods for geographic tasks.
"""

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import with_statement
import os
import shapefile
import shutil
import pycrs
import cartopy
import cartopy.crs as ccrs
from functools import partial
from shapely.ops import transform
import pyproj
from shapely.geometry import LineString, Point, Polygon
from path_finders import get_transport_shp_path, get_division_path
from path_finders import get_project_dir, find_shp_path
from global_vars import IDS_GCBA

POPULATION = "hab"

GKBA_PROJ = ccrs.TransverseMercator(central_longitude=-58.4627,
                                    central_latitude=-34.6297166,
                                    false_easting=100000.0,
                                    false_northing=100000.0,
                                    scale_factor=50.0)


def reproject_point(lat, lon, shp_path):
    point_wgs84 = Point(lat, lon)

    wgs84_prj = os.path.join(get_project_dir(), "shp", "4326.prj")
    fromcrs = pycrs.loader.from_file(wgs84_prj)
    fromcrs_proj4 = fromcrs.to_proj4()

    tocrs = pycrs.loader.from_file(shp_path + ".prj")
    tocrs_proj4 = tocrs.to_proj4()

    # print(fromcrs_proj4)
    project = partial(
        pyproj.transform,
        pyproj.Proj(fromcrs_proj4),
        pyproj.Proj(tocrs_proj4))

    return transform(project, point_wgs84)


class GKBA_Proj(cartopy.crs.Projection):

    def __init__(self):

        crs = prj_to_proj4(get_division_path("radios_censo_2010"))
        proj4_params = {i.split("=")[0].strip(): i.split("=")[1].strip() for
                        i in crs.to_proj4().split("+")[1:-1]}

        proj4_params['no_defs'] = ''

        super(GKBA_Proj, self).__init__(proj4_params)

    @property
    def boundary(self):
        coords = ((self.x_limits[0], self.y_limits[0]),
                  (self.x_limits[1], self.y_limits[0]),
                  (self.x_limits[1], self.y_limits[1]),
                  (self.x_limits[0], self.y_limits[1]),
                  (self.x_limits[0], self.y_limits[0]))

        return cartopy.crs.sgeom.Polygon(coords).exterior

    @property
    def threshold(self):
        return 1e5

    @property
    def x_limits(self):
        return (-900000, 900000)

    @property
    def y_limits(self):
        return (-900000, 900000)


def calculate_area(shape):
    return get_shapely_shape(shape).area


def prj_to_proj4(prj_or_shp_path):
    if prj_or_shp_path[-4:] == ".prj":
        prj_path = prj_or_shp_path
    else:
        prj_path = find_shp_path(prj_or_shp_path) + ".prj"

    crs = pycrs.loader.from_file(prj_path)
    return crs
    # return crs.to_proj4()


def join_df_with_shp(shp_path, df, output_dir, create_pop_density=True):
    """Join data in a DataFrame with a shp from common ids.

    Args:
        shp_path (str): Path where shp is.
        df (pandas.DataFrame): A data frame with data to join by id.
        output_dir (str): Directory where new shp will be.

    Side effects:
        Create a copy of the shp with joined data in output_dir.
        Create population density indicator
    """
    dir_input_shp = os.path.dirname(shp_path)
    shp_name = os.path.basename(shp_path)
    dir_output_shp = os.path.join(get_project_dir(), output_dir, shp_name)

    if os.path.isdir(dir_output_shp):
        # print("should delete")
        shutil.rmtree(dir_output_shp)
    shutil.copytree(dir_input_shp, dir_output_shp)

    sf = shapefile.Reader(shp_path)
    w = shapefile.Writer()

    # creating fields
    for field in sf.fields:
        w.field(*field)
    for indicator in df.columns:
        # print(indicator, str(indicator) in IDS_GCBA.keys(), IDS_GCBA.keys())
        if str(indicator) in IDS_GCBA.values():
            w.field(*[str(indicator), str("C"), 40, 0])
        else:
            w.field(*[str(indicator), str("N"), 20, 18])
    if create_pop_density:
        w.field(*[str("area_km2"), str("N"), 20, 18])
        w.field(*[str("hab_km2"), str("N"), 20, 18])
    # print(w.fields)

    # put df index in unicode
    df.index = [unicode(i) for i in df.index]

    # creating records
    for record_shape in sf.iterShapeRecords():
        record = record_shape.record
        shape = record_shape.shape

        if unicode(record[0]) in df.index:
            for col in df.columns:
                record.append(df[col][unicode(record[0])])
            if create_pop_density:
                area = calculate_area(shape) / 1000000
                record.append(area)
                population = df[POPULATION][unicode(record[0])]
                record.append(population / area)
        else:
            for col in df.columns:
                record.append(0.0)
            if create_pop_density:
                record.append(0.0)
                record.append(0.0)
        # print("\n", record)
        w.record(*record)

    w.saveDbf(os.path.join(dir_output_shp, shp_name))
    # shutil.make_archive(dir_output_shp, 'zip', dir_output_shp)


def get_shapely_shapes(sf_est):
    """Convert shapes to shapely shapes.

    Args:
        sf_est (shapefile.Reader): Reader object for a shapefile.
    """

    if sf_est.shapeType == shapefile.POINT:
        return [Point(*shape.points[0]) for shape in sf_est.iterShapes()]
    elif sf_est.shapeType == shapefile.POLYGON:
        return [Polygon(shape.points) for shape in sf_est.iterShapes()]
    elif sf_est.shapeType == shapefile.POLYLINE:
        return [LineString(shape.points) for shape in sf_est.iterShapes()]

    raise Exception("Can't handle shape type " + unicode(sf_est.shapeType))


def get_shapely_shape(shape):

    if shape.shapeType == shapefile.POINT:
        return Point(*shape.points[0])
    elif shape.shapeType == shapefile.POLYGON:
        return Polygon(shape.points)
    elif shape.shapeType == shapefile.POLYLINE:
        return LineString(shape.points)

    raise Exception("Can't handle shape type " + unicode(shape.shapeType))


def iter_shp_as_shapely(shp_path):
    """Create a generator to iterate shapes and ids of a shapefile.

    Args:
        shp_path (str): Path to a shapefile.

    Yield:
        tuple: Ids and shapes in the shapely format (id_shape, shapely_shape)
    """
    # print(shp_path)
    sf = shapefile.Reader(shp_path)

    for shape_record in sf.iterShapeRecords():
        shape = shape_record.shape
        record = shape_record.record
        yield (record[0], get_shapely_shape(shape))


# THIS FUNCTION CONVERTS A GEOJSON GEOMETRY DICTIONARY TO A PYSHP SHAPE OBJECT
def shapely_to_pyshp(shapelygeom):
    # first convert shapely to geojson
    try:
        shapelytogeojson = shapely.geometry.mapping
    except:
        import shapely.geometry
        shapelytogeojson = shapely.geometry.mapping
    geoj = shapelytogeojson(shapelygeom)
    # create empty pyshp shape
    record = shapefile._Shape()
    # set shapetype
    if geoj["type"] == "Null":
        pyshptype = 0
    elif geoj["type"] == "Point":
        pyshptype = 1
    elif geoj["type"] == "LineString":
        pyshptype = 3
    elif geoj["type"] == "Polygon":
        pyshptype = 5
    elif geoj["type"] == "MultiPoint":
        pyshptype = 8
    elif geoj["type"] == "MultiLineString":
        pyshptype = 3
    elif geoj["type"] == "MultiPolygon":
        pyshptype = 5
    record.shapeType = pyshptype
    # set points and parts
    if geoj["type"] == "Point":
        record.points = geoj["coordinates"]
        record.parts = [0]
    elif geoj["type"] in ("MultiPoint", "Linestring"):
        record.points = geoj["coordinates"]
        record.parts = [0]
    elif geoj["type"] in ("Polygon"):
        record.points = geoj["coordinates"][0]
        record.parts = [0]
    elif geoj["type"] in ("MultiPolygon", "MultiLineString"):
        index = 0
        points = []
        parts = []
        for eachmulti in geoj["coordinates"]:
            points.extend(eachmulti[0])
            parts.append(index)
            index += len(eachmulti[0])
        record.points = points
        record.parts = parts
    return record
