#### A fork of Zach's BitTorrent Client to use in Happypanda X

A BitTorrent client written in Python. Supports multi-file torrents.

This client implements a rarest-first piece download strategy. That is, the client will attempt to download those pieces that are least common in the swarm before it downloads the more-common pieces.

#### Changes

- Port to Python 3
- Add key auth in tracker request
- Refactor