las_extractor
=============
A Python webframework to extract LAS data to json
=============

License
---------------

GNU General Public License, see LICENSE


Requirements
---------------

* Python 2.6-2.7
* Fusion Tools (see http://forsys.cfr.washington.edu/fusion/fusionlatest.html, freeware, unknown license...)
* LAStools (see http://www.cs.unc.edu/~isenburg/lastools/, LGPL license with restrictions, please check out the license)

Fusion and LAStools are Windows programs. They might run (not tested) under Linux using Wine.

* PostgreSQL/PostGIS database containing a schema `lidar_tile_index` which should contain a table `grid50mfull`. This table contains polygons describing the tiling of your LAS files. See the wiki for a better description on how to create this table.

Getting Started
---------------

To install the application
* Clone this repository
* Run Bootstrap: `python bootstrap.py --version 1.5.2 --distribute`
* Before running buildout, you will need to create your own buildout file. To do so, copy/paste the existing `buildout.cfg`file and rename it (`buildout_<project>.cfg`)
* Open your buildout file in your favorite editor...
* Delete everthing except the `[vars]`section
* Once done add the following code on top of your buildout file:
```
[buildout]
extends = buildout.cfg
```
* In the `[vars]` section, replace all `overwriteme` values with your own values (see wiki for value signification)
* Run buildout: 
```
cd <project>
buildout\bin\buildout -c buildout_<project>.cfg
```
* Add the Apache folder in your Apache conf file (needs the mod_wsgi to be active):`Include <project_folder>/Apache/*.conf`

This application uses the Pyramid webframework. For more details, please refer to the <a href="http://docs.pylonsproject.org/projects/pyramid" target=_blank>pyramid documentation</a>.

