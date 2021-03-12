import zmq
from zmq.utils.monitor import recv_monitor_message
import threading
import time
import matplotlib.pyplot as plt
import netifaces as ni
from random import randrange
from kazoo.client import KazooClient
from kazoo.client import KazooState
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
        self.path = "/proxy"
        self.brokerpath = "/broker"
        self.clustersocket = None
        self.ip = get_ip()
        self.zk = start_kazoo_client()
        self.id = str(randrange(1000,10000))
        self.isleader = False
        self.context = zmq.Context()

    def start(self):
        print(f"Proxy: {self.ip}")
        
        ##Create broker znode for each instance of Proxy class
        if self.zk.exists(self.brokerpath) is None:
            self.zk.create(self.brokerpath, value=b'', ephemeral=False, makepath=True)
        broker_path = self.brokerpath + '/' + self.id
        self.zk.create(path=broker_path, value=b'', ephemeral=True, makepath=True)
        print(f'Broker {self.id} znode created under /broker')

        

    ##Check znode leader Existence 
        
        ##Make broker follower if leader exists
        if self.zk.exists(self.path):
            print(f'Broker {self.id} is a follower')   
            ##Flag used to differentiate recieve message and state replication funcs
            self.isleader = False
            self.watch_leader()
            
           
            ##get leader znode tuple value (value=self.ip_encode, znodestat)
            leader_ip = (self.zk.get(self.path)[0]).decode('utf-8')
            print(f'Leader IP - {leader_ip}')
            ##make node cluster socket to update each node's local state (push for leader, pull for follower)
            
            context = zmq.Context()
            self.clustersocket = context.socket(zmq.PULL)
            #self.clustersocket.setsockopt(zmq.RCVTIMEO, 30000)
            self.clustersocket.connect(f'tcp://{leader_ip}:5559')
            print(f'Follower broker {self.id} connected to cluster PULL from {leader_ip}:5559') 
            
            while self.isleader is False:
                try:
                    msg = self.clustersocket.recv_string()
                    print('Follower recv state from leader')
                    print(msg) 
                except Exception as e:
                    print(f'Timeout PULLing from leader:\n {e}')
                    continue
            
        ##Make leader if no leader znode already exists
        else:
            self.zk.create(self.path, self.ip.encode(
                        'utf-8'), ephemeral=True, makepath=True)
            while self.zk.exists(self.path) is None:
                pass
            print(f'Broker {self.id} is now a leader')
            ##Flag used to differentiate recieve message and state replication funcs
            self.isleader = True
            ##make node cluster socket to update each node's local state (push for leader, pull for follower)
            self.clustersocket = self.context.socket(zmq.PUSH)
            self.clustersocket.bind('tcp://*:5559')
            ##TODO - check if we need a sleep or recursive timeout function to allow time to setup socket
            print(f'Leader broker {self.id} Bound to Port 5559')

            ##Set up xpub/xsub sockets            
            # many SUB handling
            front_end = self.context.socket(zmq.XSUB)
            front_end.bind(f"tcp://*:{self.in_bound}")
            # many PUB handling
            back_end = self.context.socket(zmq.XPUB)
            back_end.setsockopt(zmq.XPUB_VERBOSE, 1)
            back_end.bind(f"tcp://*:{self.out_bound}")            
            print(
                f"Proxy started w/ in_bound={self.in_bound}, out_bound={self.out_bound}")            
            zmq.proxy(front_end, back_end)
            
        cluster_thread = threading.Thread(target=self.replicate_data_to_followers, args=())
        threading.Thread.setDaemon(cluster_thread, True)
        cluster_thread.start()

    def watch_leader(self):
        ##Watch leader node for changes - call proxy_watcher on each change
        @self.zk.DataWatch(path=self.path)
        def proxy_watcher(data, stat):
            print(f"Proxy: watcher triggered. data:{data}, stat={stat}")
            if self.zk.exists(path=self.path) is None:
            #if data is None:
                ##if no leader znode - run Kazoo election recipe
                election = self.zk.Election('broker/', self.id)
                ##run() will block until election won - then call elect_leader func
                election.run(self.elect_leader) # blocks until wins or canceled
                
    def elect_leader(self): 
        print("running elect leader")
        if self.zk.exists(self.path) is None:
            self.zk.create(self.path, value=self.ip.encode(
                    'utf-8'), ephemeral=True, makepath=True)   
            while self.zk.exists(self.path) is None:
                pass
            print(f'Broker {self.id} is the leader')
            ##Flag used to differentiate recieve message and state replication funcs
            self.isleader = True
            context = zmq.Context()
            self.clustersocket = context.socket(zmq.PUSH)
            self.clustersocket.bind('tcp://*:5559')
            #if broker_socket != None:
            print(f'Leader broker {self.id} Bound to Cluster Socket PUSH to Port 5559')
        
            ##Set up xpub/xsub sockets
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
            
    def replicate_data_to_followers(self):
        #receive publisher meta data
        while self.isleader is True:
            self.clustersocket.send_string("Cluster comm working")
            print("cluster socket working")
            time.sleep(5)
            

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
                print("Event: {}".format(evt))
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
    print(f'interface: {intf_name}')
    return ni.ifaddresses(intf_name)[ni.AF_INET][0]['addr']


def start_kazoo_client(intf="10.0.0.1", port="2181"):
    url = f'{intf}:{port}'
    print(f"starting ZK client on '{url}'")
    zk = KazooClient(hosts=url)
    zk.start()
    return zk


    

