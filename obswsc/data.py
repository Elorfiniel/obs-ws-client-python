from dataclasses import dataclass, field
from typing import List


@dataclass
class Event:
  '''Event object.'''

  event_type: str
  event_intent: int
  event_data: dict = None


@dataclass
class Request:
  '''Request object.'''

  req_type: str
  req_data: dict = None


@dataclass
class Response1:
  '''Response object (non-batch).'''

  req_type: str
  req_status: dict
  res_data: dict = None


@dataclass
class Response2:
  '''Response object (batch).'''

  results: List[Response1]
