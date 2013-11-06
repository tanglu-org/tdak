#!/usr/bin/env python
"""
Helper code for AppStream data generation.

@contact: Debian FTPMaster <ftpmaster@debian.org>
@copyright: 2012-2013 Matthias Klumpp <mak@debian.org>
@license: GNU General Public License version 2 or later
"""

################################################################################

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

################################################################################

from daklib.dbconn import *
from daklib.config import Config

from multiprocessing import Pool
from shutil import rmtree
from tempfile import mkdtemp

import yaml
import daklib.daksubprocess
import os.path

class AppStreamItem(yaml.YAMLObject):
    def __init__(self, id_desktop, pkgname):
        self.id_desktop = id_desktop
        self.pkgname = pkgname
        self.name = {}
        self.summay = {}
        self.description = {}
        self.urls = {}
        self.project_group = ""
        self.icon = {}
        self.mimetypes = []
        self.categories = []
        self.keywords = []
        self.screenshots = []
        self.compulsory_for_desktop = ""

    def __repr__(self):
        return "(id_desktop=%r, pkgname=%r, name=%r, summary=%r, description=%r, urls=%r, project_group=%r, icon=%r, mimetypes=%r, categories=%r, keywords=%r, screenshots=%r, compulsory_for_desktop=%r)" % (
            self.id_desktop, self.pkgname, self.name, self.summary, self.description, self.urls, self.project_group, self.icon, self.mimetypes, self.categories, \
            self.keywords, self.screenshots, self.compulsory_for_desktop)

class AppStreamGenerator(object):
    def __init__(self):
        self._appItems = list()

    def add_application(self, item):
        self._appItems.append(item)

    def process_package(self, filename, pkgname):
        # TODO
        print ("TODO")

    def dump_yaml(self):
        return yaml.dump_all(self._appItems, explicit_start=True)

class UnpackedSource(object):
    '''
    UnpackedSource extracts a source package into a temporary location and
    gives you some convinient function for accessing it.
    '''
    def __init__(self, dscfilename, tmpbasedir=None):
        '''
        The dscfilename is a name of a DSC file that will be extracted.
        '''
        basedir = tmpbasedir if tmpbasedir else Config()['Dir::TempPath']
        temp_directory = mkdtemp(dir = basedir)
        self.root_directory = os.path.join(temp_directory, 'root')
        command = ('dpkg-source', '--no-copy', '--no-check', '-q', '-x',
            dscfilename, self.root_directory)
        daklib.daksubprocess.check_call(command)

    def get_root_directory(self):
        '''
        Returns the name of the package's root directory which is the directory
        where the debian subdirectory is located.
        '''
        return self.root_directory

    def get_changelog_file(self):
        '''
        Returns a file object for debian/changelog or None if no such file exists.
        '''
        changelog_name = os.path.join(self.root_directory, 'debian', 'changelog')
        try:
            return open(changelog_name)
        except IOError:
            return None

    def get_all_filenames(self):
        '''
        Returns an iterator over all filenames. The filenames will be relative
        to the root directory.
        '''
        skip = len(self.root_directory) + 1
        for root, _, files in os.walk(self.root_directory):
            for name in files:
                yield os.path.join(root[skip:], name)

    def cleanup(self):
        '''
        Removes all temporary files.
        '''
        if self.root_directory is None:
            return
        parent_directory = os.path.dirname(self.root_directory)
        rmtree(parent_directory)
        self.root_directory = None

    def __del__(self):
        '''
        Enforce cleanup.
        '''
        self.cleanup()
