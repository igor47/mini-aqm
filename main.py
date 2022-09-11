#!/usr/bin/env python

import click
from colorama import Fore, Style
import logging
import os
import systemd_watchdog
from typing import Tuple, Optional, List

from influxdb_logger import InfluxdbLogger
from pms7003 import PMS7003, PMSData, SearchResult

def get_aqi(pm25: float) -> str:
    """return the aqi for the pm25 value"""
    # https://en.wikipedia.org/wiki/Air_quality_index#Computing_the_AQI
    # Table for computing AQI from PM2.5, ug/m3
    # c_low, c_high, i_low, i_high
    breakpoint_table = [
        [    0,  12.0,   0,  50],
        [ 12.1,  35.4,  51, 100],
        [ 35.5,  55.4, 101, 150],
        [ 55.5, 150.4, 151, 200],
        [150.5, 250.4, 201, 300],
        [250.5, 350.4, 301, 400],
        [350.5, 500.4, 401, 500],
    ]
    category_row = next(x for x in breakpoint_table if pm25 <= x[1])

    c_low, c_high, i_low, i_high = category_row
    aqi = (i_high - i_low) / (c_high - c_low) * (pm25 - c_low) + i_low
    return round(aqi)


def get_aqi_level(aqi: float) -> Tuple[str, str]:
    """get colorized breakpoint for the aqi value"""
    if aqi < 50:
        return "Good", Fore.GREEN
    elif aqi < 100:
        return "Moderate", Fore.YELLOW
    elif aqi < 150:
        return "Unhealthy for Certain Groups", f"{Fore.YELLOW}{Style.BRIGHT}"
    elif aqi < 200:
        return "Unhealthy", Fore.RED
    elif aqi < 300:
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
    aqi = get_aqi(data.pm2_5_atm)
    level, style = get_aqi_level(aqi)

    result = {
        "PM 1.0": data.pm1_0_atm,
        "PM 2.5": f"{style}{data.pm2_5_atm}{Style.RESET_ALL}",
        "PM 10": data.pm10_0_atm,
        "AQI": f"{style}{aqi} ({level}){Style.RESET_ALL}",
    }

    pairs = [f"{k}: {v}" for k, v in result.items()]
    click.echo("  ".join(pairs))

def configure_logging(debug: bool) -> None:
    """sets up logging to stdout"""
    root = logging.getLogger("mini-aqm")
    root.addHandler(logging.StreamHandler())
    root.setLevel(logging.DEBUG if debug else logging.ERROR)
    root.debug("configured debug logging")

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
def main(port: Optional[str], debug: bool, log_only: bool, log_path: str) -> None:
    configure_logging(debug)

    log = logging.getLogger("mini-aqm.main")
    log.debug("looking for possible PMS7003 devices...")

    possible: List[SearchResult] = PMS7003.find_devices(only=port)
    if not any(possible):
        click.echo(
            f"{Fore.RED}"
            f"no serial devices found. is your device plugged in? did you install drivers?"
            f"{Style.RESET_ALL}",
            err=True,
        )
        return

    for p in possible:
        if p.dev is None:
            click.echo(
                f"{Fore.YELLOW}"
                f"error on {p.desc} {p.port}: {p.error}"
                f"{Style.RESET_ALL}",
                err=True,
            )

    devs = [p.dev for p in possible if p.dev]
    if not any(devs):
        click.echo(
            f"{Fore.RED}"
            f"no PMS7003 devices found; resolve any errors printed above and try again"
            f"{Style.RESET_ALL}",
            err=True,
        )
        return

    logger = InfluxdbLogger(log_path)
    click.echo(
        f"{Fore.BLUE}"
        f"writing influxdb measurement {logger.MEASUREMENT} to {logger.path}"
        f"{Style.RESET_ALL}"
    )

    for dev in devs:
        click.echo(
            f"{Fore.GREEN}beginning to read data from {dev.id}...{Style.RESET_ALL}"
        )

    # systemd watchdog, in case this is running as a systemd service
    wd = systemd_watchdog.watchdog()
    wd.ready()

    while True:
        wd.ping()
        for dev in devs:
            data = dev.read()
            if data is None:
                click.echo(f"{Fore.RED}PMS7003 returned no data!{Style.RESET_ALL}")

            elif debug:
                print_debug(data)
            else:
                logger.emit(
                    fields={
                        k: v for k, v in data._asdict().items() if k.startswith("pm")
                    },
                    tags={"type": "PMS7003", "id": dev.id},
                )
                if not log_only:
                    print_pm(data)


if __name__ == "__main__":
    main()
