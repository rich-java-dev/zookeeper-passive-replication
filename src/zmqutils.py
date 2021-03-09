import zmq
from zmq.utils.monitor import recv_monitor_message
import threading
import time
import netifaces as ni

context = zmq.Context()


class Proxy():

    def __init__(self, in_bound=5555, out_bound=5556):
        self.in_bound = in_bound
        self.out_bound = out_bound
        self.path = "/proxy"
        self.zk = None
        self.ip = get_ip()

    def start(self):
        print(self.ip)
        self.zk = start_kazoo_client()

        @self.zk.DataWatch(self.path)
        def watcher(data, stat):
            print(f"Proxy: watcher triggered. data:{data}, stat={stat}")
            if data is None:
                if not self.zk.exists(self.path):
                    self.zk.create(self.path, value=self.ip.encode('utf-8'))

        # many SUB handling
        front_end = context.socket(zmq.XSUB)
        front_end.bind(f"tcp://*:{self.in_bound}")

        # many PUB handling
        back_end = context.socket(zmq.XPUB)
        back_end.setsockopt(zmq.XPUB_VERBOSE, 1)
        back_end.bind(f"tcp://*:{self.out_bound}")

        print(
            f"Proxy started w/ in_bound={self.in_bound}, out_bound={self.out_bound}")

        zmq.proxy(front_end, back_end)


def publisher(interface, port=5555, bind=True, connect=False, topic_min=0, topic_max=100000):
    conn_str = f'tcp://{interface}:{port}'

    evt_map = {}
    for val in dir(zmq):
        if val.startswith('EVENT_'):
            key = getattr(zmq, val)
            print("%21s : %4i" % (val, key))
            evt_map[key] = val

    def evt_monitor(monitor):
        while monitor.poll():
            evt = recv_monitor_message(monitor)
            evt.update({'description': evt_map[evt['event']]})
            print("Event: {}".format(evt))
            if evt['event'] == zmq.EVENT_MONITOR_STOPPED:
                break
        monitor.close()
        print()
        print('event monitor stopped.')

    socket = context.socket(zmq.PUB)
    monitor = socket.get_monitor_socket()

    t = threading.Thread(target=evt_monitor, args=(monitor,))
    t.start()

    print(
        f'Publishing to {conn_str} w/ topic range:[{topic_min},{topic_max}]')

    if bind:
        for intf in interface:
            conn_str = f'tcp://{intf}:{port}'
            print(f"binding: {conn_str}")
            socket.bind(conn_str)

    if connect:
        for intf in interface:
            conn_str = f'tcp://{intf}:{port}'
            print(f"connecting: {conn_str}")
            socket.connect(conn_str)

    return lambda topic, msg: socket.send_string(f'{topic} {msg}')


def subscriber(interface='', port=5556, topic='', net_size=0):
    conn_str = f'tcp://{interface}:{port}'
    socket = context.socket(zmq.SUB)

    print(f"Subscribing to '{conn_str}' w/ topic '{topic}'")

    if(net_size > 0):
        for i in range(net_size):
            conn_str = f'tcp://10.0.0.{i}:{port}'
            print(f"connecting: {conn_str}")
            socket.connect(conn_str)
    else:
        for intf in interface:
            conn_str = f'tcp://{intf}:{port}'
            print(f"connecting: {conn_str}")
            socket.connect(conn_str)

    socket.setsockopt_string(zmq.SUBSCRIBE, topic)

    return lambda: socket.recv_string()


def get_ip():
    intf_name = ni.interfaces()[1]
    print(f'interface: {intf_name}')
    return ni.ifaddresses(intf_name)[ni.AF_INET][0]['addr']
