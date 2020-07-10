from army.api.click import verbose_option 
from army.api.project import load_project
from army.api.debugtools import print_stack
from army.api.log import log, get_log_level
from army.api.package import load_project_packages
from army.army import cli, build
import os
import click
import re
from subprocess import Popen, PIPE, STDOUT

def to_relative_path(path):
    home = os.path.expanduser("~")
    abspath = os.path.abspath(path)
    if abspath.startswith(home):
        path = abspath.replace(home, "~", 1)
    cwd = os.path.abspath(os.path.expanduser(os.getcwd()))
    if abspath.startswith(cwd):
        path = os.path.relpath(abspath, cwd)
    return path

toolchain_path = to_relative_path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def locate_jlink():
    global toolchain_path

    # search for jlink folder
    jlink_path = os.path.join('jlink', 'JLinkExe')
    if os.path.exists(os.path.join(toolchain_path, jlink_path))==False:
        log.error(f"jlink was not found inside '{toolchain_path}', check plugin installation")
        exit(1)

    return jlink_path

def get_arch(config, target, dependencies):
#     if 'arch' not in target:
#         log.error(f"arch not defined for target '{target['name']}'")
#         exit(1)
#     target_arch = target['arch']
    
    res = None
    found_dependency = None
    for dependency in dependencies:
        for arch in dependency.arch:
            if arch==target.arch:
                if found_dependency is not None:
                    log.error(f"arch from {dependency.name} already defined in {found_dependency.name}")
                    exit(1)
                res = (dependency, dependency.arch[arch])
                found_dependency = dependency
#                 if 'definition' not in res:
#                     log.error(f"missing arch definition from {dependency['module']}")
#                     exit(1)

    if res is None:
        log.error(f"no configuration available for arch '{target.arch}'")
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
    
@build.command(name='flash', help='Flash firmware')
@verbose_option()
@click.pass_context
def flash(ctx, **kwargs):
    global toolchain_path

    log.info(f"flash")
    
    # load configuration
    config = ctx.parent.config

    # load project
    project = ctx.parent.project
    if project is None:
        print(f"no project found", sys.stderr)
        exit(1)
    
    # get target config
    target = ctx.parent.target
    target_name = ctx.parent.target_name
    if target is None:
        print(f"no target specified", file=sys.stderr)
        exit(1)

    output_path = 'output'
    build_path = os.path.join(output_path, target_name)
    log.info(f"build_path: {build_path}")
    
    # load dependencies
    try:
        dependencies = load_project_packages(project, target_name)
        log.debug(f"dependencies: {dependencies}")
    except Exception as e:
        print_stack()
        print(f"{e}", file=sys.stderr)
        clean_exit()

    # get device
    dependency, arch = get_arch(config, target, dependencies)
    log.debug(f"arch: {arch}")
    device = cmake_get_variable(os.path.join(dependency.path, arch.definition), "DEVICE")
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
        