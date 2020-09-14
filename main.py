#!/usr/bin/env python

import click
from colorama import Fore, Style
import logging
import os
import systemd_watchdog
from typing import Tuple, Optional

from influxdb_logger import InfluxdbLogger
from pms7003 import PMS7003, PMSData


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
    print("PM 10.0 (CF=1) : %s\t | PM 10.0 : %s" % (data.pm10_0_cf1, data.pm10_0_atm))
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

    pairs = [f"{k}: {v}" for k, v in result.items()]
    click.echo("  ".join(pairs))


@click.command()
@click.option(
    "--port",
    default=None,
    help="Location of PMS7003 TTY device",
    show_default="scans possible ports for devices",
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Print debug data from the device",
    show_default=True,
)
@click.option(
    "--log-only/--no-log-only",
    default=False,
    help="Only log to the influxdb log file; nothing on stdout",
)
@click.option(
    "--log-path",
    default="measurements.log",
    help="Location where logs are written",
    show_default=True,
)
def main(
    port: Optional[str], debug: bool, log_only: bool, log_path: str
) -> None:
    devs = PMS7003.get_all(only=port)
    if not devs:
        click.echo(
            f"{Fore.RED}"
            f"cannot find PMS7003 on any checked port; check path and permissions"
            f"{Style.RESET_ALL}",
            err=True
        )
        return

    logger = InfluxdbLogger(log_path)
    click.echo(
        f"{Fore.BLUE}"
        f"writing influxdb measurement {logger.MEASUREMENT} to {logger.path}"
        f"{Style.RESET_ALL}"
    )

    for dev in devs:
        click.echo(f"{Fore.GREEN}beginning to read data from {dev.id}...{Style.RESET_ALL}")

    # systemd watchdog, in case this is running as a systemd service
    wd = systemd_watchdog.watchdog()
    wd.ready()

    while True:
        wd.ping()
        for dev in devs:
            data = dev.read()
            if debug:
                print_verbose(data)
            else:
                logger.emit(
                    fields={k: v for k, v in data._asdict().items() if k.startswith("pm")},
                    tags={"type": "PMS7003", "id": dev.id},
                )
                if not log_only:
                    print_pm(data)

if __name__ == "__main__":
    main()
