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

##############################################################################
## PROXY CLASS
##############################################################################
class Proxy():

    def __init__(self, in_bound=5555, out_bound=5556):
        self.in_bound = in_bound
        self.out_bound = out_bound
        self.front_end = None
        self.back_end = None
        self.path = '/proxy'
        self.elect_root_path = '/election'
        self.elect_candidate_path = '/election/candidate_sessionid_'
        self.my_path = ""
        #self.clustersocket = None
        self.candidate_list = []
        self.seq_id = None
        self.ip = get_ip()
        self.zk = start_kazoo_client()
        self.leader = None
        self.leader_node = None
        self.isleader = False
        self.context = zmq.Context()

        print(f'New Proxy Created: {self.ip}')
        
        #Create znode for each instance of this class
        self.my_path = self.zk.create(self.elect_candidate_path, value=b'', sequence=True, ephemeral=True, makepath=True)
        print(f'New Candidate ZNode Created: {self.my_path}')
        
        
        #ensure that leader path exists
        if self.zk.exists(self.path) is None:
            newNode = self.zk.create(self.path, value=b'', ephemeral=True, makepath=True)
        
        #get all children under /election parent
        self.candidate_list = self.zk.get_children(self.elect_root_path)
        
        #candidate list removes parent node (/election/) from name
        #candidate list must be sorted sequentially
        self.candidate_list.sort()
        print(f'Candidate ZNode List: {self.candidate_list}')
        
    def start(self):
        
        #Current Znode becomes LEADER
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
            self.front_end = self.context.socket(zmq.XSUB)
            self.front_end.bind(f"tcp://*:{self.in_bound}")
            self.back_end = self.context.socket(zmq.XPUB)
            self.back_end.setsockopt(zmq.XPUB_VERBOSE, 1)
            self.back_end.bind(f"tcp://*:{self.out_bound}")            
            print(
                f"Broker {self.my_path} is leader - started w/ in_bound={self.in_bound}, out_bound={self.out_bound}")            
            zmq.proxy(self.front_end, self.back_end)
        
        
        #Current Znode becomes FOLLOWER
        else:
            
            def watch_prev_node(prev_node):
                 @self.zk.DataWatch(path=prev_node)
                 def proxy_watcher(data, stat, event):

                    if event is not None:
                        if event.type == "DELETED":
                            print(f'EVENT: {event}')

                        # print(f'Current Leader node status: {self.zk.exists(path=self.path)}')
                            election = self.zk.Election('election/', self.ip)
                            contenders = election.contenders()
                        # print(f'Contenders:\n{contenders}')
                        # ##run() will block until election won - then call elect_leader func
                            election.run(self.won_election) # blocks until wins or canceled
                    else:
                        print("Leader is existing - else stmt")
            
                    
    ################        
            #make current node the follower    
            print(f'Node is FOLLOWER')
            self.isleader = False
            leader_node = self.candidate_list[0]
            print(f'LEADER IS: {leader_node}')
            
            #TODO - remove hotfix - sliced my_path to remove "/election/"
            crnt_node_idx = self.candidate_list.index(self.my_path[10:])
            print(f'Current Node Index: {crnt_node_idx}')
            
            #get node path of largest sequential node smaller than current - ensure sorted list above
            prev_node_path = self.candidate_list[crnt_node_idx - 1]
            print(f'PrevNodePath: {prev_node_path}')
            
            prev_node = self.zk.exists(self.elect_root_path + "/" + prev_node_path, watch_prev_node)
            #TODO - either use DataWatch or get method, which instantiates watch in 2nd argument
            print(f'PreviousNode: {prev_node}')
            while self.isleader is False:
                watch_prev_node(self.elect_root_path + "/" + prev_node_path)
                time.sleep(1)

    def won_election(self): 
        print(" - I'm going to be new leader")
        print(self.path)
        #check leader barrier node
        if self.zk.exists(self.path) is None:
            self.zk.create(self.path, value=self.ip.encode(
                    'utf-8'), ephemeral=True, makepath=True)   
            print(f' - Broker {self.ip} status: Leader')
            ##Flag used to differentiate recieve message and state replication funcs
            self.isleader = True

            ##Set up xpub/xsub sockets
            self.front_end = context.socket(zmq.XSUB)
            self.front_end.bind(f"tcp://*:{self.in_bound}")
            self.back_end = context.socket(zmq.XPUB)
            self.back_end.setsockopt(zmq.XPUB_VERBOSE, 1)
            self.back_end.bind(f"tcp://*:{self.out_bound}")            
            print(
                f"Broker {self.ip} leader: in_bound={self.in_bound}, out_bound={self.out_bound}")            
            zmq.proxy(self.front_end, self.back_end)
        else:
            print("Can I run start recursively?")
            # self.start()
            
            

##############################################################################
## PUBLISHER CLASS
##############################################################################
class Publisher():

    def __init__(self, port=5555, topic=12345, proxy=True):
        self.port = port
        self.proxy = proxy
        self.topic = topic
        self.path = f"/topic/{topic}"
        self.proxy_path = "/proxy"
        self.zk = start_kazoo_client()
        self.ip = get_ip()
        self.socket = context.socket(zmq.PUB)
        self.flag = False



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
                # self.socket.shutdown(socket.SHUT_RDWR)
                if self.flag is True:
                    self.socket.close()
                    self.socket = context.socket(zmq.PUB)
                if data is not None:
                    intf = data.decode('utf-8')
                    conn_str = f'tcp://{intf}:{self.port}'
                    print(f"connecting: {conn_str}")
                    self.socket.connect(conn_str)
                    self.flag = True

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
                print("Event1: {}".format(evt))
                if evt['event'] == zmq.EVENT_MONITOR_STOPPED:
                    break
            monitor.close()
            print()
            print('event monitor stopped.')

        monitor = self.socket.get_monitor_socket()

        t = threading.Thread(target=evt_monitor, args=(monitor,))
        t.start()

##############################################################################
## SUBSCRIBER CLASS
##############################################################################
class Subscriber():

    def __init__(self, port=5556, topic='12345', proxy=True):
        self.port = port
        self.topic = topic
        self.proxy_path = "/proxy"
        self.path = f"/topic/{topic}"
        self.proxy = proxy
        self.ip = get_ip()
        self.socket = context.socket(zmq.SUB)
        self.zk = start_kazoo_client()

    def start(self):
        print(f"Subscriber: {self.ip}")

        if self.proxy:  # PROXY MODE

            @self.zk.DataWatch(self.proxy_path)
            def proxy_watcher(data, stat):
                print(f"Subscriber: proxy watcher triggered. data:{data}")
                if data is not None:
                    intf = data.decode('utf-8')
                    conn_str = f'tcp://{intf}:{self.port}'
                    self.socket.connect(conn_str)
                    print(f"connected: {conn_str}")
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
        print("sub subscribe setup")

        return lambda: self.socket.recv_string()

    def plot_data(self, data_set, label=""):

        # plot the time deltas
        fig, axs = plt.subplots(1)
        axs.plot(range(len(data_set)), data_set, label)
        axs.set_title(
            f"RTTs '{label}' - topic '{self.topic}' - host '{self.ip}'")
        axs.set_ylabel("Delta Time (Pub - Sub)")
        axs.set_xlabel("Number of Samples")
        plt.show()

                

                    

##############################################################################
def get_ip():
    intf_name = ni.interfaces()[1]
    print("*****START-UP*****")
    print(f'Interface: {intf_name}')
    return ni.ifaddresses(intf_name)[ni.AF_INET][0]['addr']


def start_kazoo_client(intf="10.0.0.1", port="2181"):
    url = f'{intf}:{port}'
    zk = KazooClient(hosts=url)
    print(f"Zookeeper Client Started: '{url}'")
    zk.start()
    print("*******************\n")
    return zk


    

