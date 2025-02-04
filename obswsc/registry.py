from abc import ABC, abstractmethod

import asyncio
import collections
import contextlib
import typing


class RegistryHash(ABC):
  '''Abstract base class for hash strategies.'''

  @abstractmethod
  def hash(self, query: object) -> str:
    '''Map a query to a string.

    Args:
      `query`: the object to be hashed.
    '''

    pass


class Registry:
  '''A registry for managing awaitable callbacks.'''

  def __init__(self, registry_hash: RegistryHash):
    '''Initialize the registry with a hash strategy.

    Args;
      `registry_hash`: a specific hash strategy to map query to callbacks.
    '''

    self.registry_hash = registry_hash

    self.cbs = collections.defaultdict(list)
    self.gcbs = list()  # Global callbacks

  def reg(self, callback: typing.Awaitable, query: object = None):
    '''Register a callback for a specific query. If no query is specified,
    the callback will be registered as a global callback.

    Args:
      `callback`: the callback to register.
      `query`: the query to register the callback for.
    '''

    if not asyncio.iscoroutinefunction(callback):
      raise TypeError("callback must be a coroutine function")

    if query is None:
      self.gcbs.append(callback)
    else:
      hash_value = self.registry_hash.hash(query)
      self.cbs[hash_value].append(callback)

  def unreg(self, callback: typing.Awaitable, query: object = None):
    '''Unregister a callback for a specific query. If no query is specified,
    the callback will be unregistered as a global callback.

    Args:
      `callback`: the callback to unregister.
      `query`: the query to unregister the callback for.
    '''

    if not asyncio.iscoroutinefunction(callback):
      raise TypeError("callback must be a coroutine function")

    with contextlib.suppress(ValueError):
      if query is None:
        self.gcbs.remove(callback)
      else:
        hash_value = self.registry_hash.hash(query)
        self.cbs[hash_value].remove(callback)
        if not self.cbs[hash_value]:
          del self.cbs[hash_value]

  def query(self, query: object = None):
    '''Get a list of callbacks for a specific query.

    Args:
      `query`: the query to get the callbacks for.
    '''

    callbacks = self.gcbs.copy()
    if query is not None:
      hash_value = self.registry_hash.hash(query)
      callbacks.extend(self.cbs.get(hash_value, []))

    return callbacks

  def clear(self):
    '''Clear all registered callbacks.'''

    self.cbs.clear()
    self.gcbs.clear()
