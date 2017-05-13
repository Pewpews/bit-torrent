import urllib
from urllib.parse import urlencode
from urllib.request import urlopen
from bt import client, util
import bcoding as bencode
from struct import unpack

class Tracker:

    def __init__(self, torrent, client, announce_url):
        self.announce_url = announce_url
        self.torrent = torrent
        self.client = client
        self.last_error = ""

    def _make_req(self, url):
        """Return bdecoded response of an
            HTTP GET request to url.
        """
        d = None
        try:
            d = urlopen(url)
        except urllib.error.HTTPError as e:
            self._handle_http_error(e)

        return self._handle_tracker_failure(d)

    def connect(self):
        """Try to connect to tracker.
           Return tracker's response.
        """

        params = {
            'info_hash': util.sha1_hash(str(
                bencode.bencode(self.torrent.info_dict['info'])
                )),
            'peer_id': self.client.peer_id,
            'port': self.client.port,
            'uploaded': 0,
            'downloaded': 0,
            'left': self.torrent.length(),
            'event': 'started',
            'key': self.client.key
        }

        get_url = self.announce_url + "?" + urlencode(params)
        return self._make_req(get_url)

    def _handle_http_error(self, e):
        self.last_error = e.reason

    def _handle_tracker_failure(self, data):

        if data:
            bd = bencode.bdecode(data)
            k = 'failure reason'
            if k in bd:
                self.last_error = bd[k]
            else:
                return bd
