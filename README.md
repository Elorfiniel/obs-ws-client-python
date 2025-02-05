# OBS WebSocket Client

A Python library for interacting with OBS Studio through its WebSocket protocol (v5.x.x). This client provides a simple async interface to control OBS Studio programmatically.

## Features

- Support for [OBS WebSocket 5.x.x protocol](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md)
- Asynchronous interface using asyncio

## Requirements

- Python 3.9 or higher
- OBS Studio 28.0.0 or higher with WebSocket server enabled

## Installation

This package uses [Poetry](https://python-poetry.org/) for dependency management. Make sure you have installed Poetry. Then simply run:

```bash
poetry install
```

## Setting up OBS WebSocket Server

1. Open OBS Studio
2. Go to Tools -> WebSocket Server Settings
3. Enable WebSocket server
4. Set the Server Port (default is 4455)
5. Optionally set the password for authentication

## Quickstart

Below is a simple code snippet that demonstrates the usage of ObsWsClient to start and stop recording in OBS Studio. For more examples, checkout the `example` folder.

```python
from obswsc.client import ObsWsClient
from obswsc.data import Request

import asyncio

async def main():
  client = ObsWsClient(url='ws://localhost:4455')

  async with client:
    await client.request(Request('StartRecord'))
    await asyncio.sleep(10.0)
    res = await client.request(Request('StopRecord'))
    print(f'recorded video: {res.res_data["outputPath"]}')

asyncio.run(main())
```

## License

This project is licensed under [the MIT License](LICENSE).

## Acknowledgments

- Thanks to the OBS Studio team for creating the WebSocket protocol.
