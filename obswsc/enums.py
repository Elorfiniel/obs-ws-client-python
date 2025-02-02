import enum


class WebSocketOpCode(enum.Enum):
  Hello = 0
  Identify = 1
  Identified = 2
  Reidentify = 3
  Event = 5
  Request = 6
  RequestResponse = 7
  RequestBatch = 8
  RequestBatchResponse = 9


class WebSocketCloseCode(enum.Enum):
  DontClose = 0
  UnknownReason = 4000
  MessageDecodeError = 4002
  MissingDataField = 4003
  InvalidDataFieldType = 4004
  InvalidDataFieldValue = 4005
  UnknownOpCode = 4006
  NotIdentified = 4007
  AlreadyIdentified = 4008
  AuthenticationFailed = 4009
  UnsupportedRpcVersion = 4010
  SessionInvalidated = 4011
  UnsupportedFeature = 4012


class RequestBatchExecutionType(enum.Enum):
  NoneType = -1
  SerialRealtime = 0
  SerialFrame = 1
  Parallel = 2


class RequestStatus(enum.Enum):
  Unknown = 0
  NoError = 10
  Success = 100
  MissingRequestType = 203
  UnknownRequestType = 204
  GenericError = 205
  UnsupportedRequestBatchExecutionType = 206
  NotReady = 207
  MissingRequestField = 300
  MissingRequestData = 301
  InvalidRequestField = 400
  InvalidRequestFieldType = 401
  RequestFieldOutOfRange = 402
  RequestFieldEmpty = 403
  TooManyRequestFields = 404
  OutputRunning = 500
  OutputNotRunning = 501
  OutputPaused = 502
  OutputNotPaused = 503
  OutputDisabled = 504
  StudioModeActive = 505
  StudioModeNotActive = 506
  ResourceNotFound = 600
  ResourceAlreadyExists = 601
  InvalidResourceType = 602
  NotEnoughResources = 603
  InvalidResourceState = 604
  InvalidInputKind = 605
  ResourceNotConfigurable = 606
  InvalidFilterKind = 607
  ResourceCreationFailed = 700
  ResourceActionFailed = 701
  RequestProcessingFailed = 702
  CannotAct = 703


class EventSubscription(enum.Enum):
  NoneType = 0
  General = (1 << 0)
  Config = (1 << 1)
  Scenes = (1 << 2)
  Inputs = (1 << 3)
  Transitions = (1 << 4)
  Filters = (1 << 5)
  Outputs = (1 << 6)
  SceneItems = (1 << 7)
  MediaInputs = (1 << 8)
  Vendors = (1 << 9)
  Ui = (1 << 10)
  All = 0b11111111111
  InputVolumeMeters = (1 << 16)
  InputActiveStateChanged = (1 << 17)
  InputShowStateChanged = (1 << 18)
  SceneItemTransformChanged = (1 << 19)


class ObsMediaInputAction(enum.Enum):
  OBS_WEBSOCKET_MEDIA_INPUT_ACTION_NONE = 0
  OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY = 1
  OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE = 2
  OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP = 3
  OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART = 4
  OBS_WEBSOCKET_MEDIA_INPUT_ACTION_NEXT = 5
  OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PREVIOUS = 6


class ObsOutputState(enum.Enum):
  OBS_WEBSOCKET_OUTPUT_UNKNOWN = 0
  OBS_WEBSOCKET_OUTPUT_STARTING = 1
  OBS_WEBSOCKET_OUTPUT_STARTED = 2
  OBS_WEBSOCKET_OUTPUT_STOPPING = 3
  OBS_WEBSOCKET_OUTPUT_STOPPED = 4
  OBS_WEBSOCKET_OUTPUT_RECONNECTING = 5
  OBS_WEBSOCKET_OUTPUT_RECONNECTED = 6
  OBS_WEBSOCKET_OUTPUT_PAUSED = 7
  OBS_WEBSOCKET_OUTPUT_RESUMED = 8
