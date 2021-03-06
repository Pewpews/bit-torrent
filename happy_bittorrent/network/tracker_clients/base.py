from enum import Enum
from typing import List, Optional

from happy_bittorrent.models import DownloadInfo, Peer
from happy_bittorrent.utils import grouper


__all__ = ['EventType', 'TrackerError', 'BaseTrackerClient']


class EventType(Enum):
    none = 0
    completed = 1
    started = 2
    stopped = 3


class TrackerError(Exception):
    pass


class BaseTrackerClient:
    def __init__(self, download_info: DownloadInfo, our_peer_id: bytes):
        self._download_info = download_info
        self._statistics = self._download_info.session_statistics

        self._our_peer_id = our_peer_id

        self.interval = None      # type: int
        self.min_interval = None  # type: Optional[int]
        self.seed_count = None    # type: int
        self.leech_count = None   # type: int
        self._peers = None

    @property
    def peers(self) -> List[Peer]:
        return self._peers

    async def announce(self, server_port: int, event: EventType):
        raise NotImplementedError

    def _sanitize(self, b):
        ""
        if isinstance(b, bytes):
            b = b.hex()
        return b


def parse_compact_peers_list(data: bytes) -> List[Peer]:
    if len(data) % 6 != 0:
        raise ValueError('Invalid length of a compact representation of peers')
    return list(map(Peer.from_compact_form, grouper(data, 6)))
