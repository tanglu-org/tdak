#!/usr/bin/python
# Copyright (C) 2013 Matthias Klumpp <mak@debian.org>
#
# Licensed under the GNU General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import apt_pkg
from optparse import OptionParser

from pkginfo import *

class SyncPackage:
    def __init__(self):
        self.debugMode = False

        parser = SafeConfigParser()
        parser.read(['/srv/dak/sync-debian.conf', 'sync-debian.conf'])
        self._momArchivePath = parser.get('MOM', 'path')
        self._destDistro = parser.get('SyncTarget', 'distro_name')

    def initialize(self, source_suite, target_suite, component):
        self._sourceSuite = source_suite
        self._component = component
        pkginfo_src = PackageInfoRetriever(self._momArchivePath, "debian", source_suite)
        pkginfo_dest = PackageInfoRetriever(self._momArchivePath, self._destDistro, target_suite)
        self._pkgs_src = pkginfo_src.get_packages_dict(component)
        self._pkgs_dest = pkginfo_dest.get_packages_dict(component)

    def _import_debian_package(self, pkg):
        # TODO: Call dak to import the source package
        print("Attempt to import package: %s" % (pkg))
        return False

    def _can_sync_package(self, src_pkg, dest_pkg, quiet=False):
        if self._destDistro in dest_pkg.version:
            print("Package %s contains Tanglu-specific modifications. Please merge the package instead of syncing it. (Version in target: %s, source is %s)" % (package_name, dest_pkg.version, srv.pkg_version))
            return False

        compare = version_compare(dest_pkg.version, src_pkg.version)
        if compare >= 0:
            print("Package %s is newer in the target distro. (Version in target: %s, source is %s)" % (package_name, dest_pkg.version, srv.pkg_version))
            return False
        return True

    def sync_package(self, package_name):
        if not package_name in self._pkgs_src:
            print("Cannot sync %s, package doesn't exist in Debian (%s/%s)!" % (package_name, self._sourceSuite, self._component))
            return False
        src_pkg = self._pkgs_src[package_name]

        if not package_name in self._pkgs_dest:
            ret = self._import_debian_package(src_pkg)
            return ret

        dest_pkg = self._pkgs_dest[package_name]

        if not self._can_sync_package(src_pkg, dest_pkg):
            return False

        # we can now sync the package
        ret = self._import_debian_package(src_pkg)
        return ret

def main():
    # init Apt, we need it later
    apt_pkg.init()

    parser = OptionParser()
    parser.add_option("-i",
                  action="store_true", dest="import_pkg", default=False,
                  help="import a package")

    (options, args) = parser.parse_args()

    if options.import_pkg:
        sync = SyncPackage()
        if len(args) != 4:
            print("Invalid number of arguments (need source-suite, target-suite, component, package-name)")
            sys.exit(1)
        source_suite = args[0]
        target_suite = args[1]
        component = args[2]
        package_name = args[3]
        sync.initialize(source_suite, target_suite, component)
        ret = sync.sync_package(package_name)
	if not ret:
            sys.exit(2)
    else:
        print("Run with -h for a list of available command-line options!")

if __name__ == "__main__":
    os.environ['LANG'] = 'C'
    os.environ['LC_ALL'] = 'C'
    main()
