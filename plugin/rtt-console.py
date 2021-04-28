from army.api.click import verbose_option 
from army.api.debugtools import print_stack
from army.api.log import log, get_log_level
from army import cli, build
import console_plugin
import click
import subprocess
import shutil

# # load plugin default values
# default_tty = "ttyUSB0"
# default_baud = "115200"
# 
# if console_plugin.args and 'tty' in console_plugin.args:
#     default_tty = console_plugin.args['tty']
# 
# if console_plugin.args and 'baud' in console_plugin.args:
#     default_baud = console_plugin.args['baud']

@build.command(name='rtt-console', help='Open RTT console')
@verbose_option()
@click.option('-s', '--speed', default=default_speed, help='Interface sepped in kHz', show_default=True)
@click.option('-d', '--detach', help='Detach console in a window', is_flag=True)
@click.option('-v', '--viewer', help='Show viewer intead of console', is_flag=True)
@click.pass_context
def rtt_console(ctx, speed, detach, viewer, **kwargs):
# def rtt_console(ctx, tty, baud, echo, detach, **kwargs):
    log.info(f"rtt-console")
    
    opts = []
    if echo==True:
        opts.append("-c")

    command = []

    jlinkexe = locate_jlink()
    log.debug(f"jlink path: {jlinkexe}")

    try: 
        command += [
            "picocom", f"/dev/{tty}",
            "-b", f"{baud}",
            "-l",
            "--imap=lfcrlf",
            "--omap=crlf",
            "--escape=a"
        ]
        
        command += opts
        
        if detach==True:
            command += ["&"]

        # TODO add check picocom is installed
        subprocess.check_call(command)
    except Exception as e:
        print_stack()
        log.error(f"{e}")

