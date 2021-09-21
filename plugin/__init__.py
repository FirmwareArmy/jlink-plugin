from army.api.command import get_army_parser
import sys
import os

class JLinkPluginException(Exception):
    def __init__(self, message):
        self.message = message

parser = get_army_parser()
if parser.find_group("build") is None:
    parser.add_group(name="build", help="Build Commands", chain=True)


import jlink_plugin.flash
