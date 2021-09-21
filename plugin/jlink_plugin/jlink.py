import curses
import importlib
from importlib.machinery import SourceFileLoader
import os
import re
import time
import sys

# import pylink
file_path = os.path.realpath(__file__)
jlink_plugin_path = os.path.realpath(os.path.join(file_path, "..", ".."))
for path in os.listdir(os.path.join(jlink_plugin_path, 'env', 'lib')):
    pkg = os.path.join(jlink_plugin_path, 'env', 'lib', path, 'site-packages')
    if os.path.exists(pkg):
        sys.path.append(pkg)

import pylink


class JLinkException(Exception):
    def __init__(self, message):
        self.message = message

def prettify_size(size):
    if size<1000:
        return f"{size}B"
    elif size<1e6:
        return f"{size/1000}kB"
    elif size<1e9:
        return f"{size/1e6}MB"
    else:
        return f"{size}B"

def print_pbar(percent, pos=None):
    pass # TODO with curses
        
class JLink:
    def __init__(self, device, serial=None, interface='swd', speed='auto', verbose=False):
        self._device = device
        self._serial = serial
        self._interface = interface
        self._speed = speed
        self._verbose = verbose
        
        jlink_path = os.path.realpath(os.path.join(jlink_plugin_path, "jlink", "libjlinkarm.so"))
        print(jlink_path)
        if os.path.exists(jlink_path)==False:
            raise JLinkException(message=f"{jlink_path}: file not found")
        lib = pylink.library.Library(jlink_path)

        if verbose==True:
            self._jlink = pylink.JLink(lib, log=sys.stdout.write, detailed_log=sys.stdout.write)
        else:
            self._jlink = pylink.JLink(lib)
        self._jlink.disable_dialog_boxes()

    def timeout(self, duration, command, *args, **kwargs):
        if duration is None:
            return command(*args, **kwargs)
        else:
            t = time.time()
            res = None
            error = None
            while time.time()-t<duration:
                try:
                    error = None
                    return command(*args, **kwargs)
                except Exception as e:
#                     print("--", e)
                    error = e
            if error is not None:
                raise error
            return None

    def open(self, timeout=None):
        print("open")
        self.timeout(timeout, self._jlink.open, self._serial)
        if self._interface=='swd':
            self._jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
        self._jlink.sync_firmware()

    def connect(self, timeout=None):
        print("connect")
        self.timeout(timeout, self._jlink.connect, chip_name=self._device, speed=self._speed, verbose=self._verbose)
        core_name = self._jlink.core_name()
        print(f"detected core {core_name}")

        
    def reset(self, timeout=None, ms=0, halt=True):
        print("reset")
        self.timeout(timeout, self._jlink.reset, ms=ms, halt=halt)
    
    def erase(self, timeout=None):
        print("erase")
        self.timeout(timeout, self._jlink.erase)

    def _on_progress(self, action, progress_string, percentage):
        num = 40
        step = 100/num

        if action==b'Program' and progress_string is not None:
            progress_string = progress_string.decode("utf-8")
            m = re.match(".*\(([0-9]*) Bytes\).*", progress_string)
            if m:
                self._written += int(m.group(1))
            p = (self._written/self._flash_size)*100
            while self._current_step<p:
                print('=', end='')
                self._current_step += step

    def flash(self, data, addr=0x0, power_on=False, flags=0, timeout=None):
        print(f"flash {prettify_size(len(data))}")
        self._flash_size = len(data)
        self._written = 0
        self._current_step = 0
        self.timeout(timeout, self._jlink.flash, data=data, addr=addr, on_progress=self._on_progress, power_on=power_on)
        print()
        
    def flash_file(self, path, addr=0x0, power_on=False, flags=0, timeout=None):
        size = os.path.getsize(path)
        print(f"flash {prettify_size(size)}")
        self._flash_size = size
        self._written = 0
        self._current_step = 0
        self.timeout(timeout, self._jlink.flash_file, path=path, addr=addr, on_progress=self._on_progress, power_on=power_on)
        print()
    
    def restart(self, num_instructions=0, skip_breakpoints=False, timeout=None):
        print("restart")
        self.timeout(timeout, self._jlink.restart, num_instructions=num_instructions, skip_breakpoints=skip_breakpoints)

    def core_serial_number(self):
        if self._device.lower().startswith('atsamd21'):
            word0 = self._jlink.memory_read(0x0080A00C, 1, nbits=32)[0]
            word1 = self._jlink.memory_read(0x0080A040, 1, nbits=32)[0]
            word2 = self._jlink.memory_read(0x0080A044, 1, nbits=32)[0]
            word3 = self._jlink.memory_read(0x0080A048, 1, nbits=32)[0]
            return '{0:08X}'.format(word3)+"-"+'{0:08X}'.format(word2)+"-"+'{0:08X}'.format(word1)+"-"+'{0:08X}'.format(word0)
        else:
            raise JLinkException(f"core_serial_number not implemented for {self._device}")

# jlink = JLink('ATSAMD21G18')
# jlink.open(30)
# jlink.connect(30)
# print(jlink.core_serial_number())
# jlink.erase(30)
# jlink.flash_file('/home/seb/git/bootloader/output/SAMD21G18A/bin/firmware.bin', power_on=True, timeout=30)
# jlink.reset(30, halt=False)
