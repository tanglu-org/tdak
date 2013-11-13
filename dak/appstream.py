#!/usr/bin/env python
"""
Create AppStream documents

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

import sys
import apt_pkg

from daklib.config import Config
from daklib.dbconn import *
from daklib.contents import BinaryContentsWriter
from daklib.appstreamdata import AppStreamGenerator
from daklib import daklog
from daklib import utils
from multiprocessing import Pool

################################################################################

def usage (exit_code=0):
    print("""Usage: dak appstream [options] subcommand

SUBCOMMANDS
    generate
        update AppStream-$arch.gz files

OPTIONS
     -h, --help
        show this help and exit

OPTIONS for generate
     -a, --archive=ARCHIVE
        only operate on suites in the specified archive

     -s, --suite={stable,testing,unstable,...}
        only operate on specified suite names

     -c, --component={main,contrib,non-free}
        only operate on specified components

     -f, --force
        write AppStream files for suites marked as untouchable, too
""")
    sys.exit(exit_code)

################################################################################

class AppPackageFetcher(object):
    '''
    AppPackageFetcher gets packages of interest for the AppStream data extractor
    '''
    def __init__(self, suite, architecture, overridetype, component):
        self.suite = suite
        self.architecture = architecture
        self.overridetype = overridetype
        self.component = component
        self.session = suite.session()

    def query(self):
        '''
        Returns a query object that is doing most of the work.
        '''
        overridesuite = self.suite
        if self.suite.overridesuite is not None:
            overridesuite = get_suite(self.suite.overridesuite, self.session)
        params = {
            'suite':         self.suite.suite_id,
            'overridesuite': overridesuite.suite_id,
            'component':     self.component.component_id,
            'arch_all':      get_architecture('all', self.session).arch_id,
            'arch':          self.architecture.arch_id,
            'type_id':       self.overridetype.overridetype_id,
            'type':          self.overridetype.overridetype,
        }

        sql_create_temp = '''
create temp table newest_binaries (
    id integer primary key,
    package text,
    version text);

create index newest_binaries_by_package on newest_binaries (package);

insert into newest_binaries (id, package, version)
    select distinct on (package) id, package, version from binaries
        where type = :type and
            (architecture = :arch_all or architecture = :arch) and
            id in (select bin from bin_associations where suite = :suite)
        order by package, version desc;'''
        self.session.execute(sql_create_temp, params=params)

        sql = '''
with

unique_override as
    (select o.package, s.section
        from override o, section s
        where o.suite = :overridesuite and o.type = :type_id and o.section = s.id and
        o.component = :component)

select bc.file, string_agg(f.filename, ', ') as pkgfile, string_agg(b.package, ', ') as package_name, string_agg(b.version, ', ') as version
    from newest_binaries b, bin_contents bc, files f, unique_override o
    where b.id = bc.binary_id and o.package = b.package and b.file = f.id
    group by bc.file'''

        return self.session.query("file", "package_name", "version", "pkgfile").from_statement(sql). \
            params(params)

    def fetch_packages(self):
        for filename, package, version, pkgfile in self.query().yield_per(100):
                if filename.startswith("usr/share/applications") and filename.endswith(".desktop"):
                    yield "%s$%s" % (pkgfile, package)
        # end transaction to return connection to pool
        self.session.rollback()

def appstream_helper(suite_id, arch_id, overridetype_id, component_id):
    '''
    This function is called in a new subprocess and multiprocessing wants a top
    level function.
    '''
    session = DBConn().session(work_mem = 1000)
    suite = Suite.get(suite_id, session)
    architecture = Architecture.get(arch_id, session)
    overridetype = OverrideType.get(overridetype_id, session)
    component = Component.get(component_id, session)
    log_message = [suite.suite_name, architecture.arch_string, \
        overridetype.overridetype, component.component_name]

    pkg_fetcher = AppPackageFetcher(suite, architecture, overridetype, component)
    print([item for item in pkg_fetcher.fetch_packages()])
    #for item in pkg_fetcher.fetch_packages():


    session.close()
    return log_message

class AppStreamWriter(object):
    def generate_appstream_data(self, cnf, archive_names = [], suite_names = [], component_names = [], force = None):
        Logger = daklog.Logger('AppStream generate')

        session = DBConn().session()
        suite_query = session.query(Suite)
        if len(archive_names) > 0:
            suite_query = suite_query.join(Suite.archive).filter(Archive.archive_name.in_(archive_names))
        if len(suite_names) > 0:
            suite_query = suite_query.filter(Suite.suite_name.in_(suite_names))
        component_query = session.query(Component)
        if len(component_names) > 0:
            component_query = component_query.filter(Component.component_name.in_(component_names))
        if not force:
            suite_query = suite_query.filter(Suite.untouchable == False)
        # we only care about deb packages, udebs usually don't contain interesting data for AppStream
        deb_id = get_override_type('deb', session).overridetype_id
        pool = Pool()
        for suite in suite_query:
            suite_id = suite.suite_id
            for component in component_query:
                component_id = component.component_id
                for architecture in suite.get_architectures(skipsrc = True, skipall = True):
                    arch_id = architecture.arch_id
                    # handle packages
                    pool.apply_async(appstream_helper, (suite_id, arch_id, deb_id, component_id))
        pool.close()
        pool.join()
        session.close()

        Logger.close()

################################################################################

def main():
    cnf = Config()
    cnf['Contents::Options::Help'] = ''
    cnf['Contents::Options::Suite'] = ''
    cnf['Contents::Options::Component'] = ''
    cnf['Contents::Options::Force'] = ''
    arguments = [('h', "help",      'Contents::Options::Help'),
                 ('a', 'archive',   'Contents::Options::Archive',   'HasArg'),
                 ('s', "suite",     'Contents::Options::Suite',     "HasArg"),
                 ('c', "component", 'Contents::Options::Component', "HasArg"),
                 ('f', "force",     'Contents::Options::Force'),
                ]
    args = apt_pkg.parse_commandline(cnf.Cnf, arguments, sys.argv)
    options = cnf.subtree('Contents::Options')

    if (len(args) != 1) or options['Help']:
        usage()

    archive_names   = utils.split_args(options['Archive'])
    suite_names     = utils.split_args(options['Suite'])
    component_names = utils.split_args(options['Component'])

    force = bool(options['Force'])

    if args[0] == 'generate':
        aswriter = AppStreamWriter()
        aswriter.generate_appstream_data(cnf, archive_names, suite_names, component_names, force)
        return

    usage()

if __name__ == '__main__':
    main()
