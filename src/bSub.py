import uuid
import zmq
from zmq.utils.monitor import recv_monitor_message
import threading
import netifaces as ni
from kazoo.client import KazooClient
import matplotlib.pyplot as plt
context = zmq.Context()

class Subscriber():

    def __init__(self, port=5556, zkserver="10.0.0.1", topic='12345', proxy=True):
        self.port = port
        self.topic = topic
        self.proxy_path = "/proxy"
        self.path = f"/topic/{topic}"
        self.proxy = proxy
        self.ip = get_ip()
        self.socket = context.socket(zmq.SUB)
        self.zk = start_kazoo_client(zkserver)

    def start(self):
        print(f"Subscriber: {self.ip}")

        if self.proxy:  # PROXY MODE

            @self.zk.DataWatch(self.proxy_path)
            def proxy_watcher(data, stat):
                print(f"Subscriber: proxy watcher triggered. data:{data}")
                if data is not None:
                    intf = data.decode('utf-8')
                    conn_str = f'tcp://{intf}:{self.port}'
                    print(f"connecting: {conn_str}")
                    self.socket.connect(conn_str)

        else:  # FLOOD MODE

            @self.zk.DataWatch(self.path)
            def pub_watcher(data, stat):
                print(f"Publisher: topic watcher triggered. data:{data}")
                if data is not None:
                    intf = data.decode('utf-8')
                    conn_str = f'tcp://{intf}:{self.port}'
                    print(f"connecting: {conn_str}")
                    self.socket.connect(conn_str)

        self.socket.setsockopt_string(zmq.SUBSCRIBE, self.topic)

        return lambda: self.socket.recv_string()

    def plot_data(self, data_set, label=""):

        # plot the time deltas
        fig, axs = plt.subplots(1)
        axs.plot(range(len(data_set)), data_set)
        axs.set_title(
            f"RTTs '{label}' - topic '{self.topic}' - host '{self.ip}'")
        axs.set_ylabel("Delta Time (Pub - Sub)")
        axs.set_xlabel("Number of Samples")
        plt.show()


def get_ip():
    intf_name = ni.interfaces()[1]
    print('\n####  Start-Up  ####')
    print(f'interface: {intf_name}')
    return ni.ifaddresses(intf_name)[ni.AF_INET][0]['addr']


def start_kazoo_client(intf="10.0.0.1", port="2181"):
    url = f'{intf}:{port}'
    print(f"starting ZK client on '{url}'")
    zk = KazooClient(hosts=url)
    zk.start()
    return zk