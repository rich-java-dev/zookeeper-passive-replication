import uuid
import zmq
from zmq.utils.monitor import recv_monitor_message
import threading
import netifaces as ni
from kazoo.client import KazooClient
from random import randrange

context = zmq.Context()

class Publisher():

    def __init__(self, port=5555, zkserver="10.0.0.1", topic=12345, proxy=True):
        self.port = port
        self.proxy = proxy
        self.topic = topic
        #path is publisher id
        self.pubid = uuid.uuid4()
        self.path = f"/publishers/{self.pubid}"
        self.leader_path = "/leader"
        self.zk = start_kazoo_client(zkserver)
        self.ip = get_ip()
        self.socket = context.socket(zmq.PUB)
        self.strength = randrange(1,11)

    def start(self):
        print(f'Publisher: {self.ip}')
        self.init_monitor()

        if not self.zk.exists(self.path):
            self.zk.create(self.path, ephemeral=True, makepath=True)


        print(f'Publishing w/ proxy={self.proxy} and topic:{self.topic}')

        if self.proxy:  # PROXY MODE

            @self.zk.DataWatch(self.proxy_path)
            def proxy_watcher(data, stat):
                print(f"Publisher: proxy watcher triggered. data:{data}")
                if data is not None:
                    intf = data.decode('utf-8')
                    conn_str = f'tcp://{intf}:{self.port}'
                    print(f"connecting: {conn_str}")
                    self.socket.connect(conn_str)
                    self.register_publisher()


        return lambda topic, msg: self.socket.send_string(f'publish {self.pubid} {topic} {self.strength} {msg}')
    
    def register_publisher(self):
        reg_msg = f'register {self.pubid} {self.topic} {self.strength}'
        self.socket.send_string(reg_msg)



    def init_monitor(self):
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
                #TODO - uncomment - old connection not dying
                # print("Event: {}".format(evt))
                if evt['event'] == zmq.EVENT_MONITOR_STOPPED:
                    break
            monitor.close()
            print()
            print('event monitor stopped.')

        monitor = self.socket.get_monitor_socket()

        t = threading.Thread(target=evt_monitor, args=(monitor,))
        t.start()
        
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
