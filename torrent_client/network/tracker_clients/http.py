import logging
import urllib.parse
from collections import OrderedDict
from typing import Optional, cast

import aiohttp
import bencodepy

from torrent_client.utils import get_auth_key
from torrent_client.models import Peer, DownloadInfo
from torrent_client.network.tracker_clients.base import BaseTrackerClient, TrackerError, parse_compact_peers_list, \
    EventType


__all__ = ['HTTPTrackerClient']


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class HTTPTrackerClient(BaseTrackerClient):
    def __init__(self, url: urllib.parse.ParseResult, download_info: DownloadInfo, our_peer_id: bytes):
        super().__init__(download_info, our_peer_id)
        self._announce_url = url.geturl()
        if url.scheme not in ('http', 'https'):
            raise ValueError('TrackerHTTPClient expects announce_url with HTTP and HTTPS protocol')

        self._tracker_id = None   # type: Optional[bytes]

    def _handle_primary_response_fields(self, response: OrderedDict):
        if b'failure reason' in response:
            raise TrackerError(response[b'failure reason'].decode())

        self.interval = response[b'interval']
        if b'min interval' in response:
            self.min_interval = response[b'min interval']
            if self.min_interval > self.interval:
                raise ValueError('Tracker returned min_interval that is greater than a default interval')

        peers = response[b'peers']
        if isinstance(peers, bytes):
            self._peers = parse_compact_peers_list(peers)
        else:
            self._peers = list(map(Peer.from_dict, peers))

    def _handle_optional_response_fields(self, response: OrderedDict):
        if b'warning message' in response:
            logger.warning('Tracker returned warning message: %s', response[b'warning message'].decode())

        if b'tracker id' in response:
            self._tracker_id = response[b'tracker id']
        if b'complete' in response:
            self.seed_count = response[b'complete']
        if b'incomplete' in response:
            self.leech_count = response[b'incomplete']

    REQUEST_TIMEOUT = 5

    async def announce(self, server_port: int, event: EventType):
        logger.info("announcing to {}".format(self._announce_url))
        params = {
            'info_hash': self._sanitize(self._download_info.info_hash),
            'peer_id': self._sanitize(self._our_peer_id),
            'port': server_port,
            'uploaded': self._statistics.total_uploaded,
            'downloaded': self._statistics.total_downloaded,
            'left': self._download_info.bytes_left,
            'compact': 1,
            'key': get_auth_key(self._announce_url)
        }
        if event != EventType.none:
            params['event'] = event.name
        if self._tracker_id is not None:
            params['trackerid'] = self._tracker_id

        with aiohttp.Timeout(HTTPTrackerClient.REQUEST_TIMEOUT), aiohttp.ClientSession() as session:
            async with session.get(self._announce_url, params=params) as conn:
                response = await conn.read()

        try:
            response = bencodepy.decode(response)
        except bencodepy.DecodingError as e:
            if isinstance(response, bytes):
                response = response.decode()
            raise TrackerError(response)

        logger.debug("received response from announcer: {}".format(response))
        if not response:
            if event == EventType.started:
                raise ValueError('Tracker returned an empty answer on start announcement')
            return
        response = cast(OrderedDict, response)

        self._handle_primary_response_fields(response)
        self._handle_optional_response_fields(response)
