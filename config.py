#!/usr/bin/env python
LICENSE="""
Copyright (C) 2011  Michael Ihde

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from pycommando.commando import command
import os
import yaml

QUANT_DIR=os.path.expanduser("./quant/config")

@command("config")
def getConfig():
    return CONFIG 

class _Config(object):
    __CONFIG_FILE = os.path.join(QUANT_DIR, "quant.cfg")
    __YAML = None

    def __init__(self, fileName):
        self.__CONFIG_FILE = os.path.join(QUANT_DIR, fileName)
        self.load()

    def has_key(self, index):
        return self.__YAML.has_key(index)

    def __getitem__(self, index):
        return self.__YAML[index]

    def __str__(self):
        return yaml.dump(self.__YAML)

    def load(self):
        try:
            self.__YAML = yaml.load(open(self.__CONFIG_FILE))
        except IOError:
            pass
        # If a configuration is empty or didn't load, create a sample portfolio
        if self.__YAML == None:
            self.__YAML = {"portfolios": {"cash": {"$": 10000.0}}}
            self.commit()

    def commit(self):
        f = open(self.__CONFIG_FILE, "w")
        f.write(yaml.dump(self.__YAML))
        f.close()

# Create a global config singleton object
#CONFIG = _Config()
