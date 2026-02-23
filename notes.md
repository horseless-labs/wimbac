# 2026-02-22
## 1925
Wrote code to produce a single sample of trip updates and positions. Just used
terminal commands to save two samples to make sure things were being updated
properly.

## 2019
Basic map is up. Ran into the following error at 30-second intervals:

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