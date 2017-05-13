import socket
import time
from bt import util
from bt.torrent import Torrent
from bt.reactor import Reactor
import logging

class Client(object):
    def __init__(self, key="NGaWT13Rt60S8A" , port=6881):
        self.port = port
        self.key = key
        self.logger = logging.getLogger('bt.peer.client')
        self.peer_id = self._gen_peer_id()
        self.torrents = []
        self._reactor = Reactor()

    def add_torrent(self, file_name=None, info_dict=None):
        self.torrents.append(Torrent(self, file_name, info_dict))

    def start(self):
        self._reactor.select()

    def _gen_peer_id(self):
        """Return a hash of the (not necessarily fully qualified)
            hostname of the machine the Python interpreter
            is running on, plus a timestamp.
        """
        seed = socket.gethostname() + str(time.time())
        return util.sha1_hash(seed)
