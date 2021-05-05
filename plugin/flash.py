from army.api.command import parser, group, command, option, argument
from army.api.debugtools import print_stack
from army.api.log import log, get_log_level
from army.api.package import load_project_packages, load_installed_package
from army.api.project import load_project
import os
import re
from subprocess import Popen, PIPE, STDOUT
import sys

def to_relative_path(path):
    home = os.path.expanduser("~")
    abspath = os.path.abspath(path)
    if abspath.startswith(home):
        path = abspath.replace(home, "~", 1)
    cwd = os.path.abspath(os.path.expanduser(os.getcwd()))
    if abspath.startswith(cwd):
        path = os.path.relpath(abspath, cwd)
    return path

tools_path = os.path.expanduser(to_relative_path(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))))

@parser
@group(name="build")
@command(name='flash', help='Flash firmware with Jlink')
def flash(ctx, **kwargs):
    log.info(f"flash")
    
    # load configuration
    config = ctx.config

    # load profile
    profile = ctx.profile
    
    # load project
    project = ctx.project
    if project is None:
        print(f"no project found", sys.stderr)
        exit(1)

    # load dependencies
    try:
        dependencies = load_project_packages(project)
        log.debug(f"dependencies: {dependencies}")
    except Exception as e:
        print_stack()
        print(f"{e}", file=sys.stderr)
        clean_exit()

    # get arch from profile
    arch, arch_package = get_arch(profile, project, dependencies)

    # get target from profile
    target = get_target(profile)

    if arch.mpu is None:
        print("Missing mpu informations from arch", file=sys.stderr)
        exit(1)
        
    # set code build path
    output_path = 'output'
    build_path = os.path.join(output_path, arch.mpu)
    log.info(f"build_path: {build_path}")

    device = arch.mpu
    if device.startswith("ATSAMD"):
        device = device.replace("ATSAMD", "SAMD")
    
    log.info(f"Flash {device} with JLink")
# 
    hex_file = os.path.join(build_path, "bin/firmware.hex")
    binfile = os.path.join(build_path, "bin/firmware.bin")
# 
    jlinkexe = locate_jlink(profile)
    log.debug(f"jlink path: {jlinkexe}")
    
    # TODO: en cas d'immpossibilité de programmation il y a probablement une mauvaise configuration du proc
    # voir http://forum.segger.com/index.php?page=Thread&postID=11854, avec Ozone changer la zone mémoire 00804000
    # 0x00804000 contains the calibration data AUX0–NVM User
    # 0x00804000 = FF C7 E0 D8 5D FC FF FF FF FF FF FF FF FF FF FF

# [[ $opt_erase -ne 0 ]] && erase=erase
# [[ $opt_erase -ne 0 ]] || erase=r

    if os.path.exists('/etc/udev/rules.d/99-jlink.rules')==False:
        print(f"Can not execute jlink with current user, add '{os.path.join(tools_path, 'jlink/99-jlink.rules')}' inside '/etc/udev/rules.d/'", file=sys.stderr)
        exit(1)

    try:
        commandline = [
            f"{os.path.join(tools_path, jlinkexe)}", 
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
        print(f"{e}", file=sys.stderr)
        exit(1)

def get_target(profile):
    target = None
    
    if "target" in profile.data:
        target = profile.data["/target"]
    
    return target

def get_arch(profile, project, dependencies):
    # add arch
    try:
        arch = profile.data["/arch"]
        arch_name = profile.data["/arch/name"]
    except Exception as e:
        print_stack()
        log.error(e)
        print("No arch definition provided by profile", file=sys.stderr)
        exit(1)
    
    if 'name' not in arch:
        print("Arch name missing", file=sys.stderr)
        exit(1)

    package = None
    res_package = None
    if 'package' in arch:
        if 'version' in arch:
            package_version = arch['version']
        else:
            package_version = 'latest'
        package_name = arch['package']
        package = load_installed_package(package_name, package_version)
        res_package = package
    
    if package is None:
        package = project
    
    # search arch in found package
    archs = package.archs
    arch = next(arch for arch in archs if arch.name==arch_name)
    if arch is None:
        print(f"Arch {arch_name} not found in {package}", file=sys.stderr)
        exit(1)
    
    return arch, res_package

def locate_jlink(profile):
    global tools_path

    # search for jlink folder
    jlink_path = profile.data[f"/tools/jlink/path"] 
    if os.path.exists(os.path.expanduser(jlink_path))==False:
        print(f"{jlink_path}: path not found for Jlink", file=sys.stderr)
        exit(1)

    return jlink_path
