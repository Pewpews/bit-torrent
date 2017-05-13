from collections import defaultdict
from bt.message import WireMessage
from bt.conn import AcceptConnection
from bt.tracker import Tracker
from bt.peer import Peer
import bcoding as bencode
from bt import util
from bt.files import File, Piece, Block

import logging
import math
import socket
import urllib


class Torrent(object):
    def __init__(self, client, file_name=None, info_dict=None):
        """Reads existing metainfo file, or writes a new one.
           Builds client, fetches peer list, and construct peers.
        """
        self.client = client
        self.logger = logging.getLogger('bt.torrent.Torrent')
        self.info_dict = info_dict
        if not self.info_dict:
            with open(file_name, 'rb') as f:
                self.info_dict = bencode.bdecode(f)

        self.info_hash = util.sha1_hash(
            bencode.bencode(self.info_dict['info']) # metainfo file is bencoded
            )

        self.piece_length = self.info_dict['info']['piece length']
        self.last_piece_length = self.length() % self.piece_length or self.piece_length
        pieces = self.info_dict['info']['pieces']
        self.pieces_hashes = list(self._read_pieces_hashes(pieces))
        self.num_pieces = len(self.pieces_hashes)
        assert len(self.pieces_hashes) == self.num_pieces
        # assert (self.num_pieces-1) * self.piece_length + self.last_piece_length \
        #        == file_length
        self.files = [f for f in self._create_files()]
        self.tmp_file = open(
                'temp.tmp', 'w+')
        """ Data structure for easy lookup of piece rarity
            pieces[hash] has list of Peer instances with that piece
            Get rarity: len(pieces[hash])
        """
        self.pieces = [
                (Piece(self, i, self.pieces_hashes[i]), []) for i in range(self.num_pieces)]
        for p, _ in self.pieces:
            logging.debug('Piece {} has length {}.'.format(p.index, p.piece_length))

        self._pieces_added = 0
        self._pending_peers = []
        self.trackers = {}
        self.peers = {}
        self.bad_peers = defaultdict(int)
        self.conn = AcceptConnection(self)

        self.get_trackers()
        self.update_peers()

        self.client._reactor.add_connections(self.conn,
                list(p.conn for p in self.peers.values()))

    def handshake(self, conn, addr, msg):
        peer_id = repr(msg[20:])
        self.logger.debug('Testing for peer existence:', self.peers[peer_id])
        # Python will use repr(peer_id) in data structures; store it as such.
        self.peers[peer_id] = Peer(addr[0], addr[1], peer_id, conn)

    def _create_files(self):
        """Generate a new File object for every file the metainfo
            file told us about.
        """
        try:
            yield (File(
                self.piece_length,
                self.info_dict['info']['name'],
                self.info_dict['info']['length']))
            self.logger.info('Appended file {} of length {}'.format(
                    self.info_dict['info']['name'], self.info_dict['info']['length']))
        except KeyError:
            for f in self.info_dict['info']['files']:
                self.logger.info('Appending file {} of length {}'.format(
                        f['path'][len(f['path'])-1], f['length']))
                yield (File(self.piece_length, f['path'], f['length']))

    def get_trackers(self):
        url = self.info_dict['announce']
        if not url in self.trackers:
            self.trackers[url] = Tracker(self, self.client, url)

    def get_block(self, index, begin, length):
        # Assumption: length is <= our block size
        piece = self.pieces[index][0]
        block = piece.blocks[begin]
        return block.read(length)

    def mark_block_received(self, piece_index, begin, block):
        """Return true if entire piece received and verified; false if not.
        """
        piece = self.pieces[piece_index][0]
        if piece.blocks[begin].received: # Already have this block
            return False
        if not piece.write_to_block(begin, block):
            self.logger.info('Received {} of {} blocks in piece {}'.format(
                    piece.num_blocks_received,
                    piece.num_blocks,
                    piece.index))
            return False

        # Entire piece received
        self._pieces_added += 1
        piece.received = True
        assert piece.is_valid()
        if self._pieces_added >= self.num_pieces:
            self.logger.info('*****ALL PIECES RECEIVED*****')
            self._write_to_disk()
            raise util.DownloadCompleteException()
        else:
            self.logger.info('* {} of {} pieces received*'.format(
                    self._pieces_added, self.num_pieces))
        return True

    def _write_to_disk(self):
        start = 0
        for f in self.files:
            new_file = f.ref
            self.tmp_file.seek(start)
            new_file.write(self.tmp_file.read(f.length))
            self.logger.debug('Writing to {}, start {}, length {}'.format(
                    f.path, start, f.length))
            start += f.length

    def pieces_by_rarity(self, peer_id=None):
        """Return array of (piece objects, peers who have them)
            tuples where the i-th item is the i-th rarest.

            Optionally return such a list for a single peer.

        """
        pieces = sorted(self.pieces, key=lambda x: len(x[1]))
        if peer_id:
            pieces = filter(lambda x: peer_id in x[1], pieces)
        return pieces

    def decrease_rarity(self, i, peer_id):
        """Record that peer with peer_id has the i-th piece of this torrent.
        """
        self.logger.debug('Decreasing rarity of piece {} because {} has it.'.format(
                i, peer_id))
        self.pieces[i][1].append(peer_id)

    def length(self):
        if 'length' in self.info_dict['info']:
            return self.info_dict['info']['length']
        return sum(f['length'] for f in self.info_dict['info']['files'])

    @classmethod
    def write_metainfo_file(cls, file_name, tracker_url, contents, piece_length=512):
        info_dict = {
            'name': file_name,
            'length': len(contents),
            # Fields common to single and multi-file below
            'piece_length': piece_length * 1024,
            'pieces': cls._pieces_hashes(contents, piece_length)
        }
        metainfo = {
            'info': info_dict,
            'announce': tracker_url
        }

        with open(file_name, 'w') as f:
            f.write(bencode.bencode(metainfo))
        
        return cls(file_name, metainfo)

    def _read_pieces_hashes(self, pieces):
        """Return array built from 20-byte SHA1 hashes
            of the string's pieces.
        """
        for i in range(0, len(pieces), 20):
            yield pieces[i:i+20]

    @classmethod
    def _pieces_hashes(cls, string, piece_length):
        """Return array built from 20-byte SHA1 hashes
            of the string's pieces.
        """
        output = ""
        current_pos = 0
        num_bytes = len(string)
        while current_pos < num_bytes:
            if current_pos + piece_length > num_bytes:
                to_position = num_bytes
            else:
                to_position = current_pos + piece_length

            piece_hash = util.sha1_hash(string[current_pos:to_position])
            output += piece_hash
            current_pos += piece_length

        return output

    def _num_pieces(self, contents):
        length = len(contents)
        if length < self.piece_length:
            return 1
        else:
            return int(math.ceil(float(length) / self.piece_length))

    def _new_peers(self, peer_list, client):
        """Return new Peer instances for each peer the tracker tells us about.
        """
        own_ext_ip = urllib.request.urlopen('http://ifconfig.me/ip').read() # HACK
        return [Peer(p[0], p[1], client)
                for p in peer_list if p[0] != own_ext_ip]

    def _get_peers(self, resp):
        raw_bytes = [ord(c) for c in resp['peers']]
        peers = []
        for i in range(len(raw_bytes) / 6):
            start = i*6
            end = start + 6
            ip = ".".join(str(i) for i in raw_bytes[start:end-2])
            port = raw_bytes[end-2:end]
            port = port[1] + port[0]*256
            peers.append([ip,port])
        return peers

    def connect_to_peers(self, peer_list):
        for peer in peer_list:
            try:
                if self.peers[peer.peer_id] or self.bad_peers[peer.peer_id] > 0:
                    continue
            except KeyError:
                pass
            handshake = WireMessage.build_handshake(self, peer, self.torrent)
            try:
                peer.conn.connect(peer.ip, peer.port)
            except socket.error as e:
                self.logger.debug('Socket error while connecting to {}:{}: {}'
                    .format(peer.ip, peer.port, e))
            else:
                peer.conn.enqueue_msg(handshake)
                self.peers[peer.peer_id] = peer

    def update_peers(self, seconds=120):
        """Add peers we haven't tried to add yet.
            TODO: Make this happen only ever `seconds` seconds.
        """
        self.logger.debug('UPDATING PEERS >>>>>')
        for t in self.trackers.values():
            resp = t.connect()
            if not resp:
                continue
            self.connect_to_peers(
                    self._new_peers(self._get_peers(resp), self)
                    )

    def notify_closed(self, peer_id):
        """Callback for peer to inform client that it has
            disconnected.
        """
        self.client._reactor.remove_subscriber(peer_id)
        del self.peers[peer_id]
        self.logger.debug('Removed {} from peers.'.format(peer_id))