
import logging
import logging.handlers
import os
import time

class InfluxdbLogger:
    """Repeatedly logs data from all devices"""
    LOG_OUTPUT_FILE = "measurements.log"

    # the influxdb measurement we're outputting
    MEASUREMENT = "bmnode"

    # how big should the log file get before rotating?
    MAX_SIZE_BYTES = 1024 * 1024 * 10  # 10 megabytes

    # how many backup files to keep after rotating?
    # must be at least 1 to enable rotation
    MAX_BACKUP_FILES = 1

    @property
    def datalog(self) -> logging.Logger:
        if not hasattr(self, "_datalog"):
            # make sure our destination exists
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.LOG_OUTPUT_FILE)))
            except FileExistsError:
                pass

            # grab the data logger
            datalog = logging.getLogger("monitor.data")

            # ignore any parent loggers -- these lines get written to file ONLY
            datalog.propagate = False

            # log at INFO
            datalog.setLevel(logging.INFO)

            # rotate the files every once in a while to allow files to close
            handler = logging.handlers.RotatingFileHandler(
                self.LOG_OUTPUT_FILE,
                maxBytes=self.MAX_SIZE_BYTES,
                backupCount=self.MAX_BACKUP_FILES,
            )
            datalog.addHandler(handler)

            # save as root logger
            self._datalog = datalog

        return self._datalog

    @property
    def hostname(self) -> str:
        if not hasattr(self, "_hostname"):
            self._hostname = open("/etc/hostname").read().strip()
        return self._hostname

    @classmethod
    def d2str(cls, d) -> str:
        """convert dictionary of key/value pairs to a string"""
        pairs = [f"{k.replace(' ', '_')}={v}" for k,v in d.items()]
        return ",".join(pairs)

    def emit(self, fields, tags, measurement=None) -> None:
        """logs specified fields and tags in influxdb format"""
        # grab timestamp
        ts = time.time_ns()

        # what's the measurement
        measurement = measurement if measurement else self.MEASUREMENT

        # output the log;
        # https://docs.influxdata.com/influxdb/v1.8/write_protocols/line_protocol_tutorial/
        self.datalog.info(
            f"{self.MEASUREMENT},{self.d2str(tags)} {self.d2str(fields)} {ts}"
        )
