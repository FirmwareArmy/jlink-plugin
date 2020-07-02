import shutil
import os
import extargparse
import sys
from config import Config
from config import load_project
from command import Command
import jlink_plugin
from log import log
import dependency
import re
from subprocess import Popen, PIPE, STDOUT
from debugtools import print_stack

def to_relative_path(path):
    home = os.path.expanduser("~")
    abspath = os.path.abspath(path)
    if abspath.startswith(home):
        path = abspath.replace(home, "~", 1)
    cwd = os.path.abspath(os.path.expanduser(os.getcwd()))
    if abspath.startswith(cwd):
        path = os.path.relpath(abspath, cwd)
    return path

toolchain_path = to_relative_path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

def init_parser(parentparser, config):
    parser = parentparser.add_parser('flash', help='Flash firmware')
    parser.set_defaults(func=project_flash)

    # add army default commands
    subparser = parser.add_subparsers(metavar='COMMAND', title=None, description=None, help=None, parser_class=extargparse.ArgumentParser, required=False)
    
    flash_command = Command('flash', jlink_plugin.build_commands.flash, subparser, {})
    flash_command.register()
    flash_command.add_parent('compile', config)


def locate_jlink():
    global toolchain_path

    # search for jlink folder
    jlink_path = os.path.join('jlink', 'JLinkExe')
    if os.path.exists(os.path.join(toolchain_path, jlink_path))==False:
        log.error(f"jlink was not found inside '{toolchain_path}', check plugin installation")
        exit(1)

    return jlink_path

def get_arch(config, target, dependencies):
    if 'arch' not in target:
        log.error(f"arch not defined for target '{target['name']}'")
        exit(1)
    target_arch = target['arch']
    
    res = None
    found_dependency = None
    for dependency in dependencies:
        dependency_arch = dependency['config'].arch()
        for arch in dependency_arch:
            if arch==target_arch:
                if found_dependency is not None:
                    log.error(f"arch from {dependency['module']} already defined in {found_dependency['module']}")
                    exit(1)
                res = dependency_arch[arch]
                res['path'] = dependency['path']
                res['module'] = dependency['module']
                found_dependency = dependency
                if 'definition' not in res:
                    log.error(f"missing arch definition from {dependency['module']}")
                    exit(1)

    if res is None:
        log.error(f"no configuration available for arch '{target_arch}'")
        exit(1)
    
    return res

def cmake_get_variable(path, name):
    log.debug(f"open {path}")
    try:
        with open(path, "r") as file:
            line = file.readline()
            while(line):
                name_search = re.search('set\((.*) (.*)\)', line, re.IGNORECASE)

                if name_search:
                    if name_search.group(1)==name:
                        return name_search.group(2)
    
                line = file.readline()
            
    except Exception as e:
        print_stack()
        log.error(f"{e}")
        exit(1)
    
    return None
    
def project_flash(args, config, **kwargs):
    global toolchain_path

    
    try:
        # load project configuration
        config = load_project(config)
        if not config:
            log.error("Current path is not a project")
            exit(1)
    except Exception as e:
        print_stack()
        log.error(f"{e}")
        return

    # get target config
    target = None
    if config.command_target():
        # if target is specified in command line then it is taken by default
        log.info(f"Search command target: {config.command_target()}")
        
        # get target config
        for t in config.targets():
            if t==config.command_target():
                target = config.targets()[t]
                target['name'] = t
        if target is None:
            log.error(f"Target not found '{config.command_target()}'")
            exit(1)
    elif config.default_target():
        log.info(f"Search default target: {config.default_target()}")
        for t in config.targets():
            if t==config.default_target():
                target = config.targets()[t]
                target['name'] = t
        if target is None:
            log.error(f"Target not found '{config.default_target()}'")
            exit(1)
    else:
        log.error(f"No target specified")
        exit(1)
    log.debug(f"target: {target}")

    build_path = os.path.join(config.output_path(), target["name"])
    log.debug(f"build path: {build_path}")
    
    try:
        # load built firmware configuration
        build_config = Config(None, os.path.join(build_path, 'army.toml'))
        build_config.load()
    except Exception as e:
        print_stack()
        log.error(f"{e}")
        return

    # load dependencies
    if build_config.config['build']['debug']:
        dependencies = dependency.load_dev_dependencies(config, target)
    else:
        # TODO dependencies = dependency.load_dependencies(config, target)
        dependencies = dependency.load_dev_dependencies(config, target)

    # get device
    arch = get_arch(config, target, dependencies)
    log.debug(f"arch: {arch}")
    device = cmake_get_variable(os.path.join(arch['path'], arch['module'], arch['definition']), "DEVICE")
    if device is None:
        log.error(f"No device found for target {target}")
        exit(1)

    log.info("Flash $device with JLink")
# 
    hex_file = os.path.join(build_path, "bin/firmware.hex")
    binfile = os.path.join(build_path, "bin/firmware.bin")
# 
    jlinkexe = locate_jlink()
    log.debug(f"jlink path: {jlinkexe}")
    
    # TODO: en cas d'immpossibilité de programmation il y a probablement une mauvaise configuration du proc
    # voir http://forum.segger.com/index.php?page=Thread&postID=11854, avec Ozone changer la zone mémoire 00804000
    # 0x00804000 contains the calibration data AUX0–NVM User
    # 0x00804000 = FF C7 E0 D8 5D FC FF FF FF FF FF FF FF FF FF FF

# [[ $opt_erase -ne 0 ]] && erase=erase
# [[ $opt_erase -ne 0 ]] || erase=r

    if os.path.exists('/etc/udev/rules.d/99-jlink.rules')==False:
        log.error(f"Can not execute jlink with current user, add '{os.path.join(toolchain_path, 'jlink/99-jlink.rules')}' inside '/etc/udev/rules.d/'")
        exit(1)

    try:
        commandline = [
            f"{os.path.join(toolchain_path, jlinkexe)}", 
            "-device", f"at{device}", 
            "-if", "swd", 
            "-speed", "12000"
        ]
        log.info(" ".join(commandline))
        p = Popen(commandline, stdout=PIPE, stdin=PIPE, stderr=PIPE)
#         stdout_data = p.communicate(input=b'data_to_write')[0]
#         print(stdout_data.decode('utf-8'))
        commands = [
            "connect",
            "r",
            # {erase}
            f"loadfile {hex_file}",
            "exit"
        ]
        for command in commands:
            p.stdin.write(f"{command}\n".encode('utf-8'))
            p.stdin.flush()
        line = p.stdout.readline()
        while line:
            print(line.decode('utf-8'), end='')
            line = p.stdout.readline()

        p.stdin.close()
        p.terminate()
        p.wait(timeout=0.2)

    except Exception as e:
        print_stack()
        log.error(f"{e}")
        exit(1)
        