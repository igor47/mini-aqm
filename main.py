#!/usr/bin/env python

import click
from colorama import Fore, Style
import logging
import os
import time
from typing import Tuple

from pms7003 import PMS7003, PMSData

AQI_PM25_BREAKPOINTS = {

}
def get_breakpoint(pm25: float) -> Tuple[str, str]:
    """get colorized breakpoint for the pm25 value"""
    if pm25 < 15.5:
        return "Good", Fore.GREEN
    elif pm25 < 40.5:
        return "Moderate", Fore.YELLOW
    elif pm25 < 65.5:
        return "Unhealthy for Certain Groups", f"{Fore.YELLOW}{Style.BRIGHT}"
    elif pm25 < 150:
        return "Unhealthy", Fore.RED
    elif pm25 < 250:
        return "Very Unhealthy", f"{Fore.RED}{Style.BRIGHT}"
    else:
        return "Hazardous", Fore.MAGENTA

def print_debug(data: PMSData) -> None:
    """print the entire PMSData structure to the console"""
    print(
        "============================================================================"
    )
    print(
        "Header : %c %c \t\t | Frame length : %s"
        % (data.header_high, data.header_low, data.frame_length)
    )
    print("PM 1.0 (CF=1) : %s\t | PM 1.0 : %s" % (data.pm1_0_cf1, data.pm1_0_atm))
    print("PM 2.5 (CF=1) : %s\t | PM 2.5 : %s" % (data.pm2_5_cf1, data.pm2_5_atm))
    print(
        "PM 10.0 (CF=1) : %s\t | PM 10.0 : %s" % (data.pm10_0_cf1, data.pm10_0_atm)
    )
    print("0.3um in 0.1L of air : %s" % (data.count_0_3))
    print("0.5um in 0.1L of air : %s" % (data.count_0_5))
    print("1.0um in 0.1L of air : %s" % (data.count_1_0))
    print("2.5um in 0.1L of air : %s" % (data.count_2_5))
    print("5.0um in 0.1L of air : %s" % (data.count_5_0))
    print("10.0um in 0.1L of air : %s" % (data.count_10_0))

    print("Reserved F : %s" % data.reserved)
    print("CHKSUM : %s" % data.checksum)
    print(
        "============================================================================"
    )

def print_pm(data: PMSData) -> None:
    """print PM values to the console"""
    aqi, style = get_breakpoint(data.pm2_5_atm)

    result = {
        "PM 1.0": data.pm1_0_atm,
        "PM 2.5": f"{style}{data.pm2_5_atm}{Style.RESET_ALL}",
        "PM 10": data.pm10_0_atm,
        "AQI": f"{style}{aqi}{Style.RESET_ALL}",
    }

    pairs = [f"{k}: {v}" for k,v in result.items()]
    click.echo("  ".join(pairs))

@click.command()
@click.option(
    "--port",
    default="/dev/ttyUSB0",
    help="Location of PMS7003 TTY device",
    required=True,
    show_default=True,
)
@click.option(
    "--debug",
    default=False,
    help="Print debug data from the device",
    show_default=True,
)
def main(port: str, debug: bool) -> None:
    if not os.access(port, mode=os.R_OK, follow_symlinks=True):
        click.echo(
            f"{Fore.RED}cannot access {port}; check path and permissions", err=True
        )
        return

    dev = PMS7003(port)
    click.echo(f"{Fore.GREEN}beginning to read data from {port}...{Style.RESET_ALL}")

    while True:
        data = dev.read()
        if debug:
            print_verbose(data)
        else:
            print_pm(data)
        time.sleep(1)

if __name__ == "__main__":
    main()
