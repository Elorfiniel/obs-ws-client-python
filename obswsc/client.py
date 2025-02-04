from .enums import WebSocketOpCode, EventSubscription
from .registry import Registry, RegistryHash

import asyncio
import base64
import hashlib
import json
import logging
import typing
import websockets


RPC_VERSION = 1


class EventRegistryHash(RegistryHash):
  '''A hash strategy for event objects.'''

  def hash(self, query: object) -> str:
    return query['eventType']


async def obs_ws_recv(ws: websockets.ClientConnection):
  '''Receive a message from the OBS WebSocket server and return the opcode and data.

  Args:
    `ws`: the established websocket connection.

  Returns:
    `op`: the opcode of the message (int).
    `d`: the data of the message (dict).
  '''

  message = json.loads(await ws.recv())
  return message['op'], message['d']


async def obs_ws_send(ws: websockets.ClientConnection, op: int, d: dict):
  '''Send a message to the OBS WebSocket server.

  Args:
    `ws`: the established websocket connection.
    `op`: the opcode of the message (int).
    `d`: the data of the message (dict).
  '''

  await ws.send(json.dumps({'op': op, 'd': d}))


async def obs_ws_auth(ws: websockets.ClientConnection,
                      hello_data: dict,
                      password: str = ''):
  '''Authenticate with the OBS WebSocket server.

  Args:
    `ws`: the established websocket connection.
    `hello_data`: the hello data sent by the OBS WebSocket server (dict).
    `password`: the password of the OBS WebSocket server (optional).
  '''

  identify_data = {
    'rpcVersion': RPC_VERSION,
    'eventSubscriptions': EventSubscription.All.value
  }

  if 'authentication' in hello_data:
    challenge: str = hello_data['authentication']['challenge']
    salt: str = hello_data['authentication']['salt']

    secret = (password + salt).encode('utf-8')
    secret = base64.b64encode(hashlib.sha256(secret).digest())

    auth_str = secret + challenge.encode('utf-8')
    auth_str = base64.b64encode(hashlib.sha256(auth_str).digest())
    auth_str = auth_str.decode('utf-8')

    identify_data['authentication'] = auth_str

  await obs_ws_send(ws, WebSocketOpCode.Identify.value, identify_data)


async def obs_ws_subs(ws: websockets.ClientConnection,
                      events: int = EventSubscription.All.value):
  '''Update the event subscriptions of the OBS WebSocket server.

  Args:
    `ws`: the established websocket connection.
    `events`: the events to subscribe to (int).
  '''

  reidentify_data = {
    'eventSubscriptions': events
  }

  await obs_ws_send(ws, WebSocketOpCode.Reidentify.value, reidentify_data)


async def ws_recv_loop(ws: websockets.ClientConnection,
                       callback: typing.Awaitable):
  '''Create a loop that receives messages from the OBS WebSocket server
  and calls the callback function. The loop will continue until explicitly
  cancelled, or the websocket connection is closed.

  Args:
    `ws`: the established websocket connection.
    `callback`: async function to call with the received message.
  '''

  assert asyncio.iscoroutinefunction(callback)

  while True:
    try:
      opcode, data = await obs_ws_recv(ws)
      await callback(opcode, data)
    except websockets.ConnectionClosed as ex:
      logging.exception(f"connection closed ({ex.code}): {ex.reason}")
      break
    except Exception as ex:
      logging.exception(f"an error occurred while receiving a message")
      continue


async def ws_until_auth(event: asyncio.Event):
  '''Wait until the client is authenticated.

  Args:
    `event`: the event to wait for.
  '''

  await event.wait()


async def ws_set_auth(event: asyncio.Event):
  '''Set the authentication event.

  Args:
    `event`: the event to set.
  '''

  event.set()


async def ws_reset_auth(event: asyncio.Event):
  '''Reset the authentication event.

  Args:
    `event`: the event to reset.
  '''

  event.clear()


class ObsWsClient:
  def __init__(self, url: str = 'ws://localhost:4455', password: str = ''):
    '''Initialize the ObsWsClient with the given URL and password.

    Args:
      `url`: the URL of the OBS WebSocket server.
      `password`: the password of the OBS WebSocket server (optional).
    '''

    self.url = url
    self.password = password

    self.ws = None
    self.task = None

    self.identified = asyncio.Event()

    self.events = Registry(EventRegistryHash())

  def reg_event_cb(self, callback: typing.Awaitable, event_type: str = None):
    '''Register a callback for a specific event type. If not specified, the callback
    will be registered as a global callback.

    Args:
      `callback`: the callback function to register.
      `event_type`: the event type to register the callback for (optional).
    '''

    query = {'eventType': event_type} if event_type is not None else None
    self.events.reg(callback, query)

  def unreg_event_cb(self, callback: typing.Awaitable, event_type: str = None):
    '''Unregister a callback for a specific event type. If not specified, the callback
    will be unregistered as a global callback.

    Args:
      `callback`: the callback function to unregister.
      `event_type`: the event type to unregister the callback for (optional).
    '''

    query = {'eventType': event_type} if event_type is not None else None
    self.events.unreg(callback, query)

  async def connect(self, timeout: int = 30, max_size: int = 4*1024*1024):
    '''Connect to the OBS WebSocket server, waiting for the connection to be established
    until the given timeout is reached, after which an exception is raised.

    Args:
      `timeout`: the timeout in seconds to wait.
      `max_size`: the maximum size of messages in bytes.
    '''

    if self.ws is not None: return

    try:
      self.ws = await websockets.connect(
        self.url,
        subprotocols=['obswebsocket.json'],
        max_size=max_size,
        open_timeout=timeout,
      )
    except Exception as ex:
      logging.exception(f"failed to connect to OBS WebSocket at {self.url}")
      return False

    self.task = asyncio.create_task(ws_recv_loop(self.ws, self.on_message))

    return True

  async def disconnect(self):
    '''Disconnect from the OBS WebSocket server.
    '''

    if self.ws is not None:
      if self.task is not None:
        self.task.cancel()
      await self.ws.close()

      self.ws = None
      self.task = None

      await ws_reset_auth(self.identified)

  async def subscribe(self, events: int = EventSubscription.All.value):
    '''Subscribe to the given events.

    Args:
      `events`: the events to subscribe to (int).
    '''

    await ws_until_auth(self.identified)
    await obs_ws_subs(self.ws, events)

  async def on_message(self, opcode: int, data: dict):
    '''Handle incoming messages from the OBS WebSocket server.

    Args:
      `opcode`: the opcode of the message (int).
      `data`: the data of the message (dict).
    '''

    logging.debug(f"received message ({opcode}): {data}")

    if opcode == WebSocketOpCode.Hello.value:
      await obs_ws_auth(self.ws, data, self.password)

    elif opcode == WebSocketOpCode.Identified.value:
      if 'negotiatedRpcVersion' in data:
        assert data['negotiatedRpcVersion'] == RPC_VERSION
      await ws_set_auth(self.identified)

    elif opcode == WebSocketOpCode.Event.value:
      callbacks = self.events.query(data)
      for callback in callbacks:
        asyncio.create_task(callback(
          event_type=data['eventType'],
          event_data=data.get('eventData', None),
        ))
