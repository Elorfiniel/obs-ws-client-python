from obswsc.client import ObsWsClient
from obswsc.data import Event, Request, Response1

import argparse
import asyncio
import functools


async def event_listener(event: Event, trigger: asyncio.Event):
  if event.event_type == 'RecordStateChanged':
    if event.event_data['outputActive']:
      trigger.set()


async def timer(time: float, trigger: asyncio.Event):
  await trigger.wait()
  await asyncio.sleep(time)


async def main(cmdargs: argparse.Namespace):
  '''This example shows how to use the ObsWsClient class to:

  1. Manage connection/disconnection with context manager.
  2. Send "StartRecord" request.
  3. Set up a timer to stop recording after a while.
  4. Send "StopRecord" request.
  '''

  timer_trigger = asyncio.Event()
  listener = functools.partial(event_listener, trigger=timer_trigger)

  client = ObsWsClient(url=cmdargs.url, password=cmdargs.password)
  client.reg_event_cb(listener, 'RecordStateChanged')

  async with client:
    await client.request(Request('StartRecord'))
    await timer(cmdargs.duration, timer_trigger)
    res: Response1 = await client.request(Request('StopRecord'))

  print(f'recorded video: {res.res_data["outputPath"]}')


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Example of using ObsWsClient class.')

  parser.add_argument('--url', type=str, default='ws://localhost:4455',
                      help='URL of the OBS WebSocket server.')
  parser.add_argument('--password', type=str, default='',
                      help='Password of the OBS WebSocket server.')

  parser.add_argument('--duration', type=float, default=30.0,
                      help='Duration of the recording in seconds.')

  cmdargs = parser.parse_args()
  asyncio.run(main(cmdargs))
