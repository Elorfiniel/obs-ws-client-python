from obswsc.client import ObsWsClient
from obswsc.data import Request, Response1

import argparse
import asyncio
import logging
import pprint


async def main(cmdargs: argparse.Namespace):
  '''This example shows how to use the ObsWsClient class to:

  1. Connect to the OBS WebSocket server.
  2. Send "GetVersion" request.
  3. Receive response.
  4. Disconnect from the OBS WebSocket server.
  '''

  client = ObsWsClient(url=cmdargs.url, password=cmdargs.password)

  try:
    if await client.connect():
      request = Request('GetVersion', None)
      response: Response1 = await client.request(request)
      print(f'status: {pprint.pformat(response.req_status)}')
      print(f'request: {response.req_type}, response data:')
      print(f'{pprint.pformat(response.res_data, compact=True)}')
  except Exception as ex:
    logging.exception('cannot get version about OBS WebSocket server')
  finally:
    await client.disconnect()


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Example of using ObsWsClient class.')

  parser.add_argument('--url', type=str, default='ws://localhost:4455',
                      help='URL of the OBS WebSocket server.')
  parser.add_argument('--password', type=str, default='',
                      help='Password of the OBS WebSocket server.')

  cmdargs = parser.parse_args()
  asyncio.run(main(cmdargs))
