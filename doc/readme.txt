Small 10 points connector:

 -----    -------
|  9  7  5  3  1 |
| 10  8  6  4  2 |
 ----------------
 1:  VREF = 3.3V
 7:  TMS  = SWDIO
 9:  TCK  = SWCLK
 10: GND

# update jlink clone firmware manually (V7/V8)
$ JLinkExe -device STM32F205RE -if swd -speed 12000
J-Link>connect
J-Link>loadbin firmware.bin, 0x08000000
