import shutil
import os
import extargparse
import sys
from config import Config


def init_parser(parentparser, config):
    parser = parentparser.add_parser('flash', help='Flash firmware')
    parser.set_defaults(func=project_clean)

    # add army default commands
    subparser = parser.add_subparsers(metavar='COMMAND', title=None, description=None, help=None, parser_class=extargparse.ArgumentParser, required=False)

def project_clean(args, config, **kwargs):
    pass