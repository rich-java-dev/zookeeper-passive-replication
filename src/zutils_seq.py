import zmq
from zmq.utils.monitor import recv_monitor_message
import threading
import time
import matplotlib.pyplot as plt
import netifaces as ni
from random import randrange, randint
from kazoo.client import KazooClient
from kazoo.client import KazooState
from kazoo.protocol.states import EventType
from kazoo.exceptions import (
    ConnectionClosedError,
    NoNodeError,
    KazooException
)

context = zmq.Context()

class Proxy():

    def __init__(self, zkserver="10.0.0.1", in_bound=5555, out_bound=5556):
        self.in_bound = in_bound
        self.out_bound = out_bound
        self.path = '/proxy'
        self.elect_root_path = '/election'
        self.elect_candidate_path = '/election/candidate_sessionid_'
        self.my_path = ""
        self.candidate_list = []
        self.ip = get_ip()
        self.zk = start_kazoo_client(zkserver)
        self.leader_node = None
        self.isleader = False
        self.context = zmq.Context()
        
        #Create znode for each instance of this class
        self.my_path = self.zk.create(self.elect_candidate_path, value=b'', sequence=True, ephemeral=True, makepath=True)
        print(f'Created Candidate ZNode: {self.my_path}')
        print(f'Candidate IP: {self.ip}\n')

        
        #ensure that leader path exists
        if self.zk.exists(self.path) is None:
            self.zk.create(self.path, value=b'', ephemeral=True, makepath=True)
        
        #get all children as candidates under '/election' parent
        self.candidate_list = self.zk.get_children(self.elect_root_path)
        
        #candidate list removes parent node (/election/) from name, not in seq order
        self.candidate_list.sort()
        print('#### Get Leader Candidate Nodes ####')
        print(f'Candidate ZNode List: {self.candidate_list}\n')


    def start(self):
        print('####  Determine Leader/Follower  ####')
        #Current Znode is first in sequential candidate list and becomes LEADER
        if self.my_path.endswith(self.candidate_list[0]):
            self.leader_node = self.my_path
            self.isleader = True
            print(f'Node is LEADER: {self.my_path}')
            print(f'My IP: {self.ip}')
            
            #set method requires byte string
            encoded_ip = self.ip.encode('utf-8')
            self.zk.set('/proxy', encoded_ip)
            self.zk.set(self.my_path, encoded_ip)
            
            #Set up zmq proxy socket
            front_end = self.context.socket(zmq.XSUB)
            front_end.bind(f"tcp://*:{self.in_bound}")
            back_end = self.context.socket(zmq.XPUB)
            back_end.setsockopt(zmq.XPUB_VERBOSE, 1)
            back_end.bind(f"tcp://*:{self.out_bound}")            
            print(
                f"Node {self.my_path} is leader - started w/ in_bound={self.in_bound}, out_bound={self.out_bound}")            
            zmq.proxy(front_end, back_end)
        
        #Znodes exist earlier in candidate list - Current node becomes FOLLOWER
        else:
            #def watch function on previous node in candidate list
            def watch_prev_node(prev_node):
                 @self.zk.DataWatch(path=prev_node)
                 def proxy_watcher(data, stat, event):

                     #need to check first if None - then check event type
                    if event is not None:
                        if event.type == "DELETED":
                            print('\n#### Leader Delete Event  ####')
                            print(f'EVENT: {event}\n')

                            election = self.zk.Election('election/', self.ip)
                            #comment out contenders - not needed yet
                            # contenders = election.contenders()
                            election.run(self.won_election) # blocks until wins or canceled
                    else:
                        print("...leader exists")
                        #bootstap short poll - need something like expo backoff
                        time.sleep(1)
                        
            print(f'Node is FOLLOWER')
            self.isleader = False
            leader_node = self.candidate_list[0]
            print(f'Following this leader: {leader_node}')
            
            #Find previous seq node in candidate list
            crnt_node_idx = self.candidate_list.index(self.my_path[10:])
            prev_node_path = self.candidate_list[crnt_node_idx - 1]            
            prev_node = self.zk.exists(self.elect_root_path + "/" + prev_node_path, watch_prev_node)
            print(f'Watching first previous sequential node: {prev_node_path}')
            
            #set watch on previous node
            while self.isleader is False:
                watch_prev_node(self.elect_root_path + "/" + prev_node_path)


    def won_election(self): 
        print(f'New Leader Won Election: {self.my_path}')
        
        #check leader barrier node
        if self.zk.exists(self.path) is None:
            self.zk.create(self.path, value=self.ip.encode(
                    'utf-8'), ephemeral=True, makepath=True)   
            print(f'New Leader IP: {self.ip}')
            
            #Flag used to differentiate recieve message and state replication funcs
            self.isleader = True

            ##Set up xpub/xsub sockets
            front_end = context.socket(zmq.XSUB)
            front_end.bind(f"tcp://*:{self.in_bound}")
            back_end = context.socket(zmq.XPUB)
            back_end.setsockopt(zmq.XPUB_VERBOSE, 1)
            back_end.bind(f"tcp://*:{self.out_bound}")            
            print(
                f"Proxy {self.ip} leader: in_bound={self.in_bound}, out_bound={self.out_bound}\n")            
            zmq.proxy(front_end, back_end)
        # else:
        #     print("Can I run start recursively?")
        #     # self.start()

class Publisher():

    def __init__(self, port=5555, zkserver="10.0.0.1", topic=12345, proxy=True):
        self.port = port
        self.proxy = proxy
        self.topic = topic
        self.path = f"/topic/{topic}"
        self.proxy_path = "/proxy"
        self.zk = start_kazoo_client(zkserver)
        self.ip = get_ip()
        self.socket = context.socket(zmq.PUB)

    def start(self):
        print(f"Publisher: {self.ip}")
        self.init_monitor()

        if not self.zk.exists("/topic"):
            self.zk.create("/topic")

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

        else:  # FLOOD MODE
            conn_str = f'tcp://{self.ip}:{self.port}'
            print(f"binding: {conn_str}")
            self.socket.bind(conn_str)

            print(f"Publisher: creating znode {self.path}:{self.ip}")
            self.zk.create(self.path, value=self.ip.encode(
                'utf-8'), ephemeral=True)

        return lambda topic, msg: self.socket.send_string(f'{topic} {msg}')

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
