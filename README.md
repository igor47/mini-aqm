# mini-aqm

Contains code that displays data from the MiniAQI device.
For info on the device, see [the accompanying blog post](https://igor.moomers.org/minimal-viable-air-quality).

## Setup ##

This repo uses [poetry](https://python-poetry.org/).
You can install `poetry` globally:

```bash
$ pip install poetry
```

## Running

Use poetry to install dependencies:

```bash
$ poetry install
```

Invoke with poetry:

```bash
$ poetry run ./main.py
```

You can get help by passing `--help`.

### Options

By default, this program will scan a few possible `tty` ports to find a PMS7003.
You may wish to pass the location explicitly, by using `--port <port>`.

Also, by default, the program will print quality measurements to the terminal.
It will also print them, in [influxdb line protocol format](https://docs.influxdata.com/influxdb/v1.8/write_protocols/line_protocol_tutorial/), to `measurements.log`.
You may wish to disable printing to the terminal with `--log-only`, and customize the location of the log file with `--log-path`.

## Running as a `systemd` service

On a recent Linux, you can run this as a service.
Modify the included `mini-aqm.service` file, and edit the `WorkingDirectory` and `ExecStart` variables.
`WorkingDirectory` should point at the location where you have this repo checked out.
`ExecStart` (and `ExecStartPre`) should have the path to your `poetry` binary -- find it with `which poetry`.
You may also wish to customize the arguments to `main.py`, for instance to set `--log-path`.

To install the service:

```bash
cat mini-aqm.service | sudo tee /etc/systemd/system/mini-aqm.service
sudo systemctl daemon-reload
sudo systemctl start mini-aqm
```

## With `telegraf`

You might want to pull the measurements into a time series database using [`telegraf`](https://github.com/influxdata/telegraf).
You can do so by using the [`tail`](https://github.com/influxdata/telegraf/tree/master/plugins/inputs/tail) plugin.
The configuration looks like this:

```
[[inputs.tail]]
   files = ["/home/igor47/repos/mini-aqm/measurements.log"]
```

Customize the path where your `measurements.log` file is found.
You may wish to pass an explicit path to `main.py` using `--log-path <path>`.
