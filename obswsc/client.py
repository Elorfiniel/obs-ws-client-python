from .enums import (
  WebSocketOpCode, EventSubscription,
  RequestBatchExecutionType,
)
from .data import Event, Request, Response1, Response2
from .registry import Registry, RegistryHash

from dataclasses import dataclass, field
from typing import Awaitable, Dict, List, Union

import asyncio
import base64
import hashlib
import json
import logging
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


async def obs_ws_request_1(ws: websockets.ClientConnection,
                           request: Request):
  '''Make a request to the OBS WebSocket server. Returns a unique ID
  for the request, so that the response can be matched to the request.

  Args:
    `ws`: the established websocket connection.
    `request`: the request object.
  '''

  request_id = str(uuid.uuid4())
  request_d = {
    'requestType': request.req_type,
    'requestId': request_id,
  }
  if request.req_data is not None:
    request_d['requestData'] = request.req_data

  await obs_ws_send(ws, WebSocketOpCode.Request.value, request_d)

  return request_id


async def obs_ws_request_2(ws: websockets.ClientConnection,
                           requests: List[Request],
                           halt_on_failure: bool = False,
                           execution_type: RequestBatchExecutionType = RequestBatchExecutionType.SerialRealtime.value):
  '''Make a batch of requests to the OBS WebSocket server. Returns a unique ID
  for the request, so that the response can be matched to the request.

  Args:
    `ws`: the established websocket connection.
    `requests`: the list of request objects.
    `halt_on_failure`: whether to halt on failure (bool, optional).
    `execution_type`: the execution type of the requests (int, optional).
  '''

  request_id = str(uuid.uuid4())
  request_d = {
    'requestId': request_id,
    'haltOnFailure': halt_on_failure,
    'executionType': execution_type,
    'requests': list(),
  }
  for request in requests:
    request_item = {'requestType': request.req_type}
    if request.req_data is not None:
      request_item['requestData'] = request.req_data
    request_d['requests'].append(request_item)

  await obs_ws_send(ws, WebSocketOpCode.RequestBatch.value, request_d)

  return request_id


async def ws_recv_loop(ws: websockets.ClientConnection,
                       callback: Awaitable):
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


@dataclass
class RequestRecord:
  '''Record for a request made to the OBS WebSocket server.'''

  event: asyncio.Event = field(default_factory=asyncio.Event)
  response_data: dict = None

  async def wait(self):
    await until_event(self.event)

  async def done(self):
    await set_event(self.event)

  def set_data(self, data: Union[Response1, Response2]):
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

    self.requests: Dict[str, RequestRecord] = dict()

  def reg_event_cb(self, callback: Awaitable, event_type: str = None):
    '''Register a callback for a specific event type. If not specified, the callback
    will be registered as a global callback.

    Args:
      `callback`: the callback function to register.
      `event_type`: the event type to register the callback for (optional).
    '''

    query = {'eventType': event_type} if event_type is not None else None
    self.e_cbs.reg(callback, query)

  def unreg_event_cb(self, callback: Awaitable, event_type: str = None):
    '''Unregister a callback for a specific event type. If not specified, the callback
    will be unregistered as a global callback.

    Args:
      `callback`: the callback function to unregister.
      `event_type`: the event type to unregister the callback for (optional).
    '''

    query = {'eventType': event_type} if event_type is not None else None
    self.e_cbs.unreg(callback, query)

  def reg_request_cb(self, callback: Awaitable, request_type: str = None):
    '''Register a callback for a specific request type. If not specified, the callback
    will be registered as a global callback.

    Args:
      `callback`: the callback function to register.
      `request_type`: the request type to register the callback for (optional).
    '''

    query = {'requestType': request_type} if request_type is not None else None
    self.r_cbs.reg(callback, query)

  def unreg_request_cb(self, callback: Awaitable, request_type: str = None):
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

  async def _handle_request(self, request_id: str):
    '''Handle a request to the OBS WebSocket server.

    Args:
      `request_id`: the request ID.
    '''

    self.requests[request_id] = RequestRecord()
    await self.requests[request_id].wait()

    request_record = self.requests.pop(request_id)
    return request_record.get_data()

  async def request(self, request: Request):
    '''Make a request to the OBS WebSocket server, wait until the response
    is received. Returns the request status and response data.

    Args:
      `request`: the request object.
    '''

    await until_event(self.identified)

    request_id = await obs_ws_request_1(self.ws, request)
    return await self._handle_request(request_id)

  async def batch_request(self, requests: List[Request],
                          halt_on_failure: bool = False,
                          execution_type: RequestBatchExecutionType = RequestBatchExecutionType.SerialRealtime.value):
    '''Make a batch request to the OBS WebSocket server, wait until the
    response is received. Returns the request status and response data.

    Args:
      `requests`: the list of request objects.
      `halt_on_failure`: whether to halt on failure (bool, optional).
      `execution_type`: the execution type of the requests (int, optional).
    '''

    await until_event(self.identified)

    request_id = await obs_ws_request_2(self.ws, requests, halt_on_failure, execution_type)
    return await self._handle_request(request_id)

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
      event = Event(
        event_type=data['eventType'],
        event_intent=data['eventIntent'],
        event_data=data.get('eventData', None),
      )
      for callback in callbacks:
        asyncio.create_task(callback(event))

    elif opcode == WebSocketOpCode.RequestResponse.value:
      callbacks = self.r_cbs.query(data)
      response = Response1(
        req_type=data['requestType'],
        req_status=data['requestStatus'],
        res_data=data.get('responseData', None),
      )
      for callback in callbacks:
        asyncio.create_task(callback(response))

      if data['requestId'] in self.requests:
        request_record = self.requests[data['requestId']]
        request_record.set_data(response)
        await request_record.done()

    elif opcode == WebSocketOpCode.RequestBatchResponse.value:
      results: List[Response1] = list()
      for response_item in data['results']:
        callbacks = self.r_cbs.query(response_item)
        response = Response1(
          req_type=response_item['requestType'],
          req_status=response_item['requestStatus'],
          res_data=response_item.get('responseData', None),
        )
        for callback in callbacks:
          asyncio.create_task(callback(response))
        results.append(response)

      if data['requestId'] in self.requests:
        request_record = self.requests[data['requestId']]
        request_record.set_data(Response2(results))
        await request_record.done()
