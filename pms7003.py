"""
PMS7003 datasheet
http://eleparts.co.kr/data/_gextends/good-pdf/201803/good-pdf-4208690-1.pdf
"""

from dataclasses import dataclass
import glob
import logging
import os
import serial
from serial.tools.list_ports import comports
import struct
import time
from typing import Any, Dict, NamedTuple, List, Optional


class PMSData(NamedTuple):
    header_high: int  # 0x42
    header_low: int  # 0x4d
    frame_length: int  # 2x1(data+check bytes)
    pm1_0_cf1: int  # PM1.0 concentration unit μ g/m3（CF=1，standard particle）
    pm2_5_cf1: int  # PM2.5 concentration unit μ g/m3（CF=1，standard particle）
    pm10_0_cf1: int  # PM10 concentration unit μ g/m3（CF=1，standard particle）
    pm1_0_atm: int  # PM1.0 concentration unit μ g/m3（under atmospheric environment）
    pm2_5_atm: int  # PM2.5 concentration unit μ g/m3（under atmospheric environment）
    pm10_0_atm: int  # PM10 concentration unit μ g/m3  (under atmospheric environment)
    count_0_3: int  # number of particles with diameter beyond 0.3 um in 0.1 L of air.
    count_0_5: int  # number of particles with diameter beyond 0.5 um in 0.1 L of air.
    count_1_0: int  # number of particles with diameter beyond 1.0 um in 0.1 L of air.
    count_2_5: int  # number of particles with diameter beyond 2.5 um in 0.1 L of air.
    count_5_0: int  # number of particles with diameter beyond 5.0 um in 0.1 L of air.
    count_10_0: int  # indicates the number of particles with diameter beyond 10 um in 0.1 L of air.
    reserved: int  # reserved
    checksum: int  # checksum


@dataclass
class SearchResult:
    port: str
    desc: str
    hwid: str
    dev: Optional["PMS7003"] = None
    error: Optional[str] = None


PMSStruct = struct.Struct("!2B15H")

# all the data as unsigned ints for checksum calculation
ChecksumStruct = struct.Struct("!30BH")


class PMS7003(object):

    # PMS7003 protocol data (HEADER 2byte + 30byte)
    PMS_7003_PROTOCOL_SIZE = 32

    HEADER_HIGH = int("0x42", 16)
    HEADER_LOW = int("0x4d", 16)

    # Baud Rate
    SERIAL_SPEED = 9600

    # give up after trying to read for this long
    READ_TIMEOUT_SEC = 2

    @classmethod
    def get_logger(cls, dev: str = None) -> logging.Logger:
        path = ".".join(filter(None, ('mini-aqm', cls.__name__, dev)))
        return logging.getLogger(path)

    @classmethod
    def find_devices(cls, only: Optional[str] = None) -> List[SearchResult]:
        """checks several possible locations for PMS7003 devices

        returns all valid locations
        """
        log = cls.get_logger()

        # figure out possible device paths to check
        if only:
            log.debug(f"listing results from specified port {port}")
            possible = [SearchResult(port=only, desc="user-specified", hwid="")]
        else:
            log.debug("listing results from all com ports...")
            possible = [
                SearchResult(port=p, desc=d, hwid=h) for (p, d, h) in comports()
            ]

        log.debug(f"checking {len(possible)} ports for PMS7003 device...")
        for p in possible:
            log.debug(f"\tchecking port {p.port}...")
            if not os.path.exists(p.port):
                p.error = "no such port"
            elif not os.access(p.port, mode=os.R_OK, follow_symlinks=True):
                p.error = "access denied"
            else:
                try:
                    dev = PMS7003(p.port)
                    if dev.read():
                        p.dev = dev
                    else:
                        p.error = "no data"
                except Exception as e:
                    p.error = str(e)

        return possible

    def __init__(self, port: str):
        self.port = port
        self.buffer: bytes = b""
        self.log = self.get_logger(str(self))

        self.checksum_errors = 0

    def __str__(self) -> str:
        return f"<PMS7003 on {self.id}>"

    @property
    def id(self) -> str:
        return self.port

    @property
    def serial(self) -> serial.Serial:
        """Serial port interface"""
        if not hasattr(self, "_serial"):
            self._serial = serial.Serial(
                self.port, self.SERIAL_SPEED, timeout=self.READ_TIMEOUT_SEC
            )

        return self._serial

    def read(self) -> PMSData:
        """Returns a PMS reading"""
        self.serial.flushInput()

        # try to read a datagram
        began = time.time()
        data = None
        while data is None:
            # have we been trying for too long?
            if time.time() - began > self.READ_TIMEOUT_SEC:
                self.log.warning("read timeout exceeded")
                break

            # read until we have at least the right number of bytes
            while len(self.buffer) < self.PMS_7003_PROTOCOL_SIZE:
                self.buffer += self.serial.read(1024)

            # consume until buffer is nearly-empty
            while len(self.buffer) >= self.PMS_7003_PROTOCOL_SIZE:
                buffer = self.buffer[: self.PMS_7003_PROTOCOL_SIZE]
                maybe_data = PMSData._make(PMSStruct.unpack(buffer))

                # looks like the start of a packet, lets advance the buffer
                if self.header_valid(maybe_data):
                    self.log.debug("found valid header")
                    self.buffer = self.buffer[self.PMS_7003_PROTOCOL_SIZE :]

                    if self.checksum_valid(buffer):
                        data = maybe_data
                    else:
                        self.log.warning("checksum does not match")
                        self.checksum_errors += 1
                        data = None

                # invalid header, we might be mid-packet, advance by 1
                else:
                    self.buffer = self.buffer[1:]
                    data = None

        return data

    @classmethod
    def header_valid(cls, data: PMSData) -> bool:
        """make sure the header is valid"""
        return data.header_high == cls.HEADER_HIGH and data.header_low == cls.HEADER_LOW

    @classmethod
    def checksum_valid(self, buffer: bytes) -> bool:
        """make sure the checksum of the buffer is valid"""
        chksum_data = ChecksumStruct.unpack(buffer)

        # sum every unsigned int (omit the final short)
        calculated = sum(chksum_data[:-1])

        # grab the send value
        sent = chksum_data[-1]

        return calculated == sent
