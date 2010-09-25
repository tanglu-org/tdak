#!/usr/bin/env python

"""
Config access class

@contact: Debian FTPMaster <ftpmaster@debian.org>
@copyright: 2008  Mark Hymers <mhy@debian.org>
@license: GNU General Public License version 2 or later
"""

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

# <NCommander> mhy, how about "Now with 20% more monty python references"

################################################################################

import os
import apt_pkg
import socket

################################################################################

default_config = "/etc/dak/dak.conf" #: default dak config, defines host properties

def which_conf_file():
    return os.getenv("DAK_CONFIG", default_config)

class Config(object):
    """
    A Config object is a singleton containing
    information about the DAK configuration
    """

    __shared_state = {}

    def __init__(self, *args, **kwargs):
        self.__dict__ = self.__shared_state

        if not getattr(self, 'initialised', False):
            self.initialised = True
            self._readconf()
            self._setup_routines()

    def _readconf(self):
        apt_pkg.init()

        self.Cnf = apt_pkg.newConfiguration()

        apt_pkg.ReadConfigFileISC(self.Cnf, which_conf_file())

        # Check whether our dak.conf was the real one or
        # just a pointer to our main one
        res = socket.gethostbyaddr(socket.gethostname())
        conffile = self.Cnf.get("Config::" + res[0] + "::DakConfig")
        if conffile:
            apt_pkg.ReadConfigFileISC(self.Cnf, conffile)

        # Rebind some functions
        # TODO: Clean this up
        self.get = self.Cnf.get
        self.SubTree = self.Cnf.SubTree
        self.ValueList = self.Cnf.ValueList
        self.Find = self.Cnf.Find
        self.FindB = self.Cnf.FindB

    def has_key(self, name):
        return self.Cnf.has_key(name)

    def __getitem__(self, name):
        return self.Cnf[name]

    def __setitem__(self, name, value):
        self.Cnf[name] = value

    @staticmethod
    def get_db_value(name, default=None, rettype=None):
        from daklib.dbconn import DBConfig, DBConn, NoResultFound
        try:
            res = DBConn().session().query(DBConfig).filter(DBConfig.name == name).one()
        except NoResultFound:
            return default

        if rettype:
            return rettype(res.value)
        else:
            return res.value

    def _setup_routines(self):
        """
        This routine is the canonical list of which fields need to exist in
        the config table.  If your dak instance is to work, we suggest reading it

        Of course, what the values do is another matter
        """
        for field in [('db_revision',      None,       int),
                      ('defaultsuitename', 'unstable', str),
                      ('signingkeyids',    '',         str),
                      ('exportpath',       '',         str)
                      ]:
            setattr(self, 'get_%s' % field[0], lambda x=None: self.get_db_value(field[0], field[1], field[2]))
            setattr(Config, '%s' % field[0], property(fget=getattr(self, 'get_%s' % field[0])))

    def get_defaultsuite(self):
        from daklib.dbconn import get_suite
        suitename = self.defaultsuitename
        if not suitename:
            return None
        else:
            return get_suite(suitename)

    defaultsuite = property(get_defaultsuite)

