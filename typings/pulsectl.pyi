from typing import List, TextIO


class PulseObject:
    ...


class PulseSourceSampleSpec:
    rate: int


class PulseSourceInfo(PulseObject):
    name: str
    description: str
    index: int
    channel_count: int
    sample_spec: PulseSourceSampleSpec


class PulseSinkInfo(PulseObject):
    ...


class PulseSourceOutputInfo(PulseObject):
    source: int


class PulseServerInfo(PulseObject):
    default_source_name: str


class PulseError(Exception):
    ...


class PulseIndexError(PulseError):
    ...


class PulseOperationFailed(PulseError):
    ...


class Pulse:
    def __init__(self, name: str) -> None: ...

    def server_info(self) -> PulseServerInfo: ...

    def module_load(self, name: str, args: str) -> int: ...

    def module_unload(self, index: int) -> None: ...

    def source_default_set(self, name: str) -> None: ...

    def get_source_by_name(self, name: str) -> PulseSourceInfo: ...

    def source_list(self) -> List[PulseSourceInfo]: ...

    def source_output_list(self) -> List[PulseSourceOutputInfo]: ...


def connect_to_cli() -> TextIO:
    ...
