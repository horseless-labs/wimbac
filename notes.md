# 2026-02-22
## 1925
Wrote code to produce a single sample of trip updates and positions. Just used
terminal commands to save two samples to make sure things were being updated
properly.

## 2019
Basic map is up. Ran into the following error at 15-second intervals, and
changed to 30-second intervals to good effect:

```Traceback (most recent call last):
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/urllib3/response.py", line 903, in _error_catcher
    yield
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/urllib3/response.py", line 1028, in _raw_read
    data = self._fp_read(amt, read1=read1) if not fp_closed else b""
           ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/urllib3/response.py", line 1011, in _fp_read
    return self._fp.read(amt) if amt is not None else self._fp.read()
           ~~~~~~~~~~~~~^^^^^
  File "/usr/lib/python3.13/http/client.py", line 479, in read
    s = self.fp.read(amt)
  File "/usr/lib/python3.13/socket.py", line 719, in readinto
    return self._sock.recv_into(b)
           ~~~~~~~~~~~~~~~~~~~~^^^
  File "/usr/lib/python3.13/ssl.py", line 1304, in recv_into
    return self.read(nbytes, buffer)
           ~~~~~~~~~^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.13/ssl.py", line 1138, in read
    return self._sslobj.read(len, buffer)
           ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
ConnectionResetError: [Errno 104] Connection reset by peer

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/requests/models.py", line 820, in generate
    yield from self.raw.stream(chunk_size, decode_content=True)
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/urllib3/response.py", line 1257, in stream
    data = self.read(amt=amt, decode_content=decode_content)
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/urllib3/response.py", line 1112, in read
    data = self._raw_read(amt)
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/urllib3/response.py", line 1027, in _raw_read
    with self._error_catcher():
         ~~~~~~~~~~~~~~~~~~~^^
  File "/usr/lib/python3.13/contextlib.py", line 162, in __exit__
    self.gen.throw(value)
    ~~~~~~~~~~~~~~^^^^^^^
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/urllib3/response.py", line 930, in _error_catcher
    raise ProtocolError(f"Connection broken: {e!r}", e) from e
urllib3.exceptions.ProtocolError: ("Connection broken: ConnectionResetError(104, 'Connection reset by peer')", ConnectionResetError(104, 'Connection reset by peer'))

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/flask/app.py", line 1536, in __call__
    return self.wsgi_app(environ, start_response)
           ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/flask/app.py", line 1514, in wsgi_app
    response = self.handle_exception(e)
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/flask/app.py", line 1511, in wsgi_app
    response = self.full_dispatch_request()
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/flask/app.py", line 919, in full_dispatch_request
    rv = self.handle_user_exception(e)
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/flask/app.py", line 917, in full_dispatch_request
    rv = self.dispatch_request()
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/flask/app.py", line 902, in dispatch_request
    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "/home/mireles/horseless/wimbac3/app.py", line 27, in api_vehicles
    data = merge_trip_updates_and_positions(update_url, pos_url)
  File "/home/mireles/horseless/wimbac3/merge_feeds.py", line 103, in merge_trip_updates_and_positions
    upd_feed = load_feed(update_url)
  File "/home/mireles/horseless/wimbac3/merge_feeds.py", line 15, in load_feed
    response = requests.get(url, timeout=10)
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/requests/api.py", line 73, in get
    return request("get", url, params=params, **kwargs)
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/requests/api.py", line 59, in request
    return session.request(method=method, url=url, **kwargs)
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/requests/sessions.py", line 589, in request
    resp = self.send(prep, **send_kwargs)
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/requests/sessions.py", line 746, in send
    r.content
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/requests/models.py", line 902, in content
    self._content = b"".join(self.iter_content(CONTENT_CHUNK_SIZE)) or b""
                    ~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/mireles/horseless/wimbac3/.venv/lib/python3.13/site-packages/requests/models.py", line 822, in generate
    raise ChunkedEncodingError(e)
requests.exceptions.ChunkedEncodingError: ("Connection broken: ConnectionResetError(104, 'Connection reset by peer')", ConnectionResetError(104, 'Connection reset by peer'))
```

## 2040
Notes on setting up InfluxDB **without a Docker container**.

```
pip install influxdb-client
pip freeze > requirements.txt
```

Add InfluxData repository:

```
curl -fsSL https://repos.influxdata.com/influxdata-archive.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/influxdata-archive.gpg

echo 'deb [signed-by=/etc/apt/keyrings/influxdata-archive.gpg] https://repos.influxdata.com/debian stable main' \
| sudo tee /etc/apt/sources.list.d/influxdata.list
```

```
sudo apt update
sudo apt install influxdb2
```

```
sudo systemctl enable influxdb
sudo systemctl start influxdb
sudo systemctl status influxdb
```

Visit localhost:8086

# 2026-03-01
We have [Realtime GTFS Map](http://wimbac.com/) up after a great deal of fighting with DNS through Namecheap.
## WIMBAC – Infrastructure & Service Setup Notes

This session transitioned WIMBAC from a manually run local script into a persistent, server-backed service with InfluxDB running on a remote Ubuntu instance.

Below are the exact locations of the relevant system components.
## InfluxDB Installation & Configuration

### APT Repository Configuration

InfluxDB was installed via the official InfluxData Debian repository.

Relevant files:
- Repository entry:
    `/etc/apt/sources.list.d/influxdata.list`
- GPG keyring used for signature verification:
    `/etc/apt/keyrings/influxdata-archive.gpg`

If Influx installation ever breaks again, these are the first two places to inspect.
### InfluxDB Data Storage

InfluxDB v2 stores its data and metadata under:

- Bolt metadata store:
    `/root/.influxdbv2/influxd.bolt`
- Engine data directory:
    `/root/.influxdbv2/engine/`

If the database appears “empty” or corrupted, this directory is the physical storage location.
### InfluxDB Service

InfluxDB runs as a systemd service.

Service name:

```
influxdb
```

Useful commands:

```
sudo systemctl status influxdb
sudo systemctl restart influxdb
sudo journalctl -u influxdb -f
```

## WIMBAC Service Configuration

WIMBAC is now managed by systemd rather than being run manually.

### Service Definition File

The service file is located at:

```
/etc/systemd/system/wimbac.service
```

This file defines:
- `WorkingDirectory`
- `ExecStart`
- `User`
- `Environment=` variables
- Restart policy

If environment variables need to change, this is where they are defined.

After modifying it:

```
sudo systemctl daemon-reload
sudo systemctl restart wimbac
```

### WIMBAC Application Directory

```
/home/mireles/wimbac/
```

Inside that directory:
- Flask app
- GTFS-RT ingestion code
- Any static files
- Requirements file
- Virtual environment (if used)

This directory is referenced in the `WorkingDirectory=` field inside the service file.

### Environment Variables

Environment variables (Influx URL, token, org, bucket, etc.) are defined directly in:

```
/etc/systemd/system/wimbac.service
```

Example structure inside the service file:

```
Environment="INFLUX_URL=http://localhost:8086"
Environment="INFLUX_TOKEN=..."
Environment="INFLUX_ORG=..."
Environment="INFLUX_BUCKET=..."
```

These are injected into the process at runtime.

They are **not** hardcoded into the application source.
### WIMBAC Service Management

Service name:

```
wimbac
```

Useful commands:

```
sudo systemctl status wimbac
sudo systemctl restart wimbac
sudo journalctl -u wimbac -f
```

If ingestion ever silently stops, check the logs here first.

## Current System Architecture

On the server:
- InfluxDB runs as a systemd-managed database service.
- WIMBAC runs as a systemd-managed ingestion service.
- WIMBAC writes GTFS-RT data to InfluxDB at `localhost:8086`.
- Data persists under `/root/.influxdbv2/`.

There is no manual process required to start ingestion.  
If the server reboots, both services restart automatically.

Future debugging map:

If ingestion fails:
1. Check `wimbac` service logs.
2. Check `influxdb` service status.
3. Verify environment variables in `wimbac.service`.
4. Confirm Influx is listening on port 8086.
5. Inspect `/root/.influxdbv2/` if data integrity is suspected

That’s the operational memory of tonight.

# 2026-03-02
## 2000
Created fetch_gtfs_static.py, which downloads the relevant schedule data from
https://www.riderta.com/sites/default/files/gtfs/latest/google_transit.zip
and saves it into data/raw.

Main targets there will probably be stops.txt, trips.txt, and possibly
routes.txt.

## 2039
Interface consideration: it might be better to have a user start looking
at a map with static stops, instead of the cluster of vehicles that is
currently displayed by default. They can then select a stop or route, which
can then trigger the display of relevant vehicles.

# 2026-03-03
## 2120
Noticed extremely cluttered interface when the site populated the map with
all available vehicle positions. The first and most sensible step to address
this was to allow a user to select a given stop, then have relevant
vehicles populate the map. Implemented proof-of-concept of just looking at
all vehicles withing a great circle distance of the selected stop, but this
will likely be refined to be replaced by or relegated to a supporting role
to the actual routes.

Implemented a simple caching mechanism for vehicle positions in app.py. Added
refresh_latest_vehicles_if_stale(), which is now called by
`/api/vehicles`, `/api/vehicles_near`, and `/api/vehicles_nearest`. The
cache was meant to decouple user requests from ingestion of vehicle data.

Added try-catch logic to requests for GTFS-RT data and saving to Influx.

Large expansion of `index.html` for stop clicking logic, addition of user
hints, and clearer graphics. Currently:
- Small blue circles for stops.
- Hollow blue circles for a selected stop.
- Large blue circle for vehicles.

**Next Steps**
- MAKE ICONS LARGER FOR MOBILE!!
- Considering adding a CSS stylesheet.