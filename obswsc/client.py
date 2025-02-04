from .enums import WebSocketOpCode, EventSubscription
from .registry import Registry, RegistryHash

import asyncio
import base64
import hashlib
import json
import logging
import typing
import uuid
import websockets


RPC_VERSION = 1


class EventRegistryHash(RegistryHash):
  '''A hash strategy for event objects.'''

  def hash(self, query: object) -> str:
    return query['eventType']


class RequestRegistryHash(RegistryHash):
  '''A hash strategy for request objects.'''

  def hash(self, query: object) -> str:
    return query['requestType']


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

  identify_d = {
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

    identify_d['authentication'] = auth_str

  await obs_ws_send(ws, WebSocketOpCode.Identify.value, identify_d)


async def obs_ws_subs(ws: websockets.ClientConnection,
                      events: int = EventSubscription.All.value):
  '''Update the event subscriptions of the OBS WebSocket server.

  Args:
    `ws`: the established websocket connection.
    `events`: the events to subscribe to (int).
  '''

  reidentify_d = {
    'eventSubscriptions': events
  }

  await obs_ws_send(ws, WebSocketOpCode.Reidentify.value, reidentify_d)


async def obs_ws_request(ws: websockets.ClientConnection,
                         request_type: str,
                         request_data: dict = None):
  '''Make a request to the OBS WebSocket server. Returns a unique ID
  for the request, so that the response can be matched to the request.

  Args:
    `ws`: the established websocket connection.
    `request_type`: the type of the request (str).
    `request_data`: the data of the request (dict, optional).
  '''

  request_id = str(uuid.uuid4())
  request_d = {
    'requestType': request_type,
    'requestId': request_id,
  }
  if request_data is not None:
    request_d['requestData'] = request_data

  await obs_ws_send(ws, WebSocketOpCode.Request.value, request_d)

  return request_id


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


async def until_event(event: asyncio.Event):
  '''Wait until the event is set.

  Args:
    `event`: the event to wait for.
  '''

  await event.wait()


async def set_event(event: asyncio.Event):
  '''Set the event.

  Args:
    `event`: the event to set.
  '''

  event.set()


async def reset_event(event: asyncio.Event):
  '''Reset the event.

  Args:
    `event`: the event to reset.
  '''

  event.clear()


class RequestRecord:
  '''Record for a request made to the OBS WebSocket server.'''

  def __init__(self):
    self.event = asyncio.Event()
    self.response_data = None

  async def wait(self):
    await until_event(self.event)

  async def done(self):
    await set_event(self.event)

  def set_data(self, data: dict):
    self.response_data = data

  def get_data(self):
    return self.response_data


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

    self.e_cbs = Registry(EventRegistryHash())
    self.r_cbs = Registry(RequestRegistryHash())

    self.requests: typing.Dict[str, RequestRecord] = dict()

  def reg_event_cb(self, callback: typing.Awaitable, event_type: str = None):
    '''Register a callback for a specific event type. If not specified, the callback
    will be registered as a global callback.

    Args:
      `callback`: the callback function to register.
      `event_type`: the event type to register the callback for (optional).
    '''

    query = {'eventType': event_type} if event_type is not None else None
    self.e_cbs.reg(callback, query)

  def unreg_event_cb(self, callback: typing.Awaitable, event_type: str = None):
    '''Unregister a callback for a specific event type. If not specified, the callback
    will be unregistered as a global callback.

    Args:
      `callback`: the callback function to unregister.
      `event_type`: the event type to unregister the callback for (optional).
    '''

    query = {'eventType': event_type} if event_type is not None else None
    self.e_cbs.unreg(callback, query)

  def reg_request_cb(self, callback: typing.Awaitable, request_type: str = None):
    '''Register a callback for a specific request type. If not specified, the callback
    will be registered as a global callback.

    Args:
      `callback`: the callback function to register.
      `request_type`: the request type to register the callback for (optional).
    '''

    query = {'requestType': request_type} if request_type is not None else None
    self.r_cbs.reg(callback, query)

  def unreg_request_cb(self, callback: typing.Awaitable, request_type: str = None):
    '''Unregister a callback for a specific request type. If not specified, the callback
    will be unregistered as a global callback.

    Args:
      `callback`: the callback function to unregister.
      `request_type`: the request type to unregister the callback for (optional).
    '''

    query = {'requestType': request_type} if request_type is not None else None
    self.r_cbs.unreg(callback, query)

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
        self.task = None

      await self.ws.close()
      self.ws = None

      await reset_event(self.identified)
      self.requests.clear()

  async def subscribe(self, events: int = EventSubscription.All.value):
    '''Subscribe to the given events.

    Args:
      `events`: the events to subscribe to (int).
    '''

    await until_event(self.identified)
    await obs_ws_subs(self.ws, events)

  async def request(self, request_type: str, request_data: dict = None):
    '''Make a request to the OBS WebSocket server, wait until the response is received.

    Args:
      `request_type`: the type of the request (str).
      `request_data`: the data of the request (dict, optional).
    '''

    await until_event(self.identified)

    request_id = await obs_ws_request(self.ws, request_type, request_data)

    self.requests[request_id] = RequestRecord()
    await self.requests[request_id].wait()

    request_record = self.requests.pop(request_id)
    return request_record.get_data()

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
      await set_event(self.identified)

    elif opcode == WebSocketOpCode.Event.value:
      callbacks = self.e_cbs.query(data)
      for callback in callbacks:
        asyncio.create_task(callback(
          event_type=data['eventType'],
          event_intent=data['eventIntent'],
          event_data=data.get('eventData', None),
        ))

    elif opcode == WebSocketOpCode.RequestResponse.value:
      callbacks = self.r_cbs.query(data)
      for callback in callbacks:
        asyncio.create_task(callback(
          request_type=data['requestType'],
          request_id=data['requestId'],
          request_status=data['requestStatus'],
          response_data=data.get('responseData', None),
        ))

      if data['requestId'] in self.requests:
        request_record = self.requests[data['requestId']]
        request_record.set_data(dict(
          request_status=data['requestStatus'],
          response_data=data.get('responseData', None),
        ))
        await request_record.done()
