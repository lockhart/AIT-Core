import zmq.green as zmq
import gevent
import gevent.monkey; gevent.monkey.patch_all()

import ait.core
import ait.server
from ait.core import log


class AitBroker(gevent.Greenlet):

    def __init__(self):
        self.context = zmq.Context()
        self.XSUB_URL = ait.config.get('server.xsub',
                                        ait.server.DEFAULT_XSUB_URL)
        self.XPUB_URL = ait.config.get('server.xpub',
                                        ait.server.DEFAULT_XPUB_URL)

        gevent.Greenlet.__init__(self)

    def _run(self):
        self.setup_proxy()
        self.subscribe_all()

        log.info("Starting proxy...")
        while True:
            log.info('Polling...')
            gevent.sleep(0)
            socks = dict(self.poller.poll())

            if socks.get(self.frontend) == zmq.POLLIN:
                message = self.frontend.recv_multipart()
                self.backend.send_multipart(message)

            if socks.get(self.backend) == zmq.POLLIN:
                message = self.backend.recv_multipart()
                self.frontend.send_multipart(message)

    def setup_proxy(self):
        self.frontend = self.context.socket(zmq.XSUB)
        self.frontend.bind(self.XSUB_URL)

        self.backend = self.context.socket(zmq.XPUB)
        self.backend.bind(self.XPUB_URL)

        # Initialize poll set
        self.poller = zmq.Poller()
        self.poller.register(self.frontend, zmq.POLLIN)
        self.poller.register(self.backend, zmq.POLLIN)

    def subscribe_all(self):
        for stream in (self.inbound_streams + self.outbound_streams):
            if not type(stream.input_) is int:
                self.subscribe(stream, stream.input_)

        for plugin in self.plugins:
            for input_ in plugin.inputs:
                self.subscribe(plugin, input_)

    def subscribe(self, subscriber, publisher):
        log.info('Subscribing {} to topic {}'.format(subscriber, publisher))
        subscriber.sub.setsockopt(zmq.SUBSCRIBE, str(publisher))