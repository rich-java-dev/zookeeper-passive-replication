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
        self.zk = start_kazoo_client(zkserver)
        self.context = zmq.Context()
        self.in_bound = in_bound
        self.out_bound = out_bound
        self.leader_path = '/leader'
        self.elect_root_path = '/election'
        self.elect_candidate_path = '/election/candidate_sessionid_'
        self.candidate_list = []
        self.pub_root_path = '/publishers'
        self.my_path = ""
        self.ip = get_ip()
        self.leader_node = None
        self.isleader = False
        self.pub_data = {} #{topic: {pubid: {pub_values: [], strength: someval}}}
        self.replica_socket = None # set up PUSH/PULL socket for state transfer
        self.replica_port = "5557"
        self.front_end_socket = None
        self.back_end_socket = None

        #Create Znode - CANDIDATES - /election/candidate_sessionid_n
        self.my_path = self.zk.create(self.elect_candidate_path, value=b'', sequence=True, ephemeral=True, makepath=True)
        print(f'Created Candidate ZNode: {self.my_path}')
        print(f'Candidate IP: {self.ip}\n')

        
        #Create Znode - LEADER - /leader
        if self.zk.exists(self.leader_path) is None:
            self.zk.create(self.leader_path, value=b'', ephemeral=True, makepath=True)
        
        #Get and Sort candidate list
        self.candidate_list = self.zk.get_children(self.elect_root_path)
            #list absent of parent node (/election/) from name, not in seq order
        self.candidate_list.sort()
        print('#### Get Leader Candidate Nodes ####')
        print(f'Candidate ZNode List: {self.candidate_list}\n')

        #Create Znode - PUBLISHERS - /publishers
        if self.zk.exists(self.pub_root_path) is None:
            self.zk.create(path=self.pub_root_path, value=b'', ephemeral=False, makepath=True)
            
        #Set publisher watch - to update pub_data dict on failure
        #@self.zk.ChildrenWatch(path=self.pub_root_path) #TODO - ensure znode parent for publishers
        #def watch_pubs(children):
        #    self.pub_change(children)
    
    #Delete failed pubs from pub_data dict
    def pub_change(self, children):
        for topic in self.pub_data.keys():
            for pubid in self.pub_data[topic].keys():
                if pubid not in children:
                    del self.pub_data[topic][pubid]

    def start(self):
        print('####  Determine Leader/Follower  ####')
        #Compare first sequential node with my IP - if same - set me to leader
        if self.my_path.endswith(self.candidate_list[0]):
            self.leader_node = self.my_path
            self.isleader = True
            print(f'Node is LEADER: {self.my_path}')
            print(f'My IP: {self.ip}')
            
            #set method requires byte string
            encoded_ip = self.ip.encode('utf-8')
            self.zk.set(self.leader_path, encoded_ip)
            self.zk.set(self.my_path, encoded_ip)
            
            #Set up zmq proxy socket
            self.front_end_socket = self.context.socket(zmq.XSUB)
            self.front_end_socket.bind(f"tcp://*:{self.in_bound}")
            self.back_end_socket = self.context.socket(zmq.XPUB)
            self.back_end_socket.setsockopt(zmq.XPUB_VERBOSE, 1)
            self.back_end_socket.bind(f"tcp://*:{self.out_bound}")            
            print(
                f"Node {self.my_path} is leader - started w/ in_bound={self.in_bound}, out_bound={self.out_bound}")            
            
            #Uncomment proxy to allow two kinds of comm types from pub
            #zmq.proxy(self.front_end_socket, self.back_end_socket)
           
            #set up comms between ensemble brokers to transfer state
            self.replica_socket = self.context.socket(zmq.PUSH)
            self.replica_socket.bind(f"tcp://*:{self.replica_port}")
        
            #thread to continuously receive pub msgs
            get_pub_msg_thread = threading.Thread(target=self.get_pub_msg, args=())
            threading.Thread.setDaemon(get_pub_msg_thread, True)
            get_pub_msg_thread.start()
        
        
        
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

            #set up comms between ensemble brokers to transfer state
            leader_ip = self.zk.get(self.leader_path)[0].decode('utf-8')
            print(f'leaderip: {leader_ip} and replicaport: {self.replica_port}')
            self.replica_socket = self.context.socket(zmq.PULL)
            self.replica_socket.connect(f'tcp://{leader_ip}:{self.replica_port}')
            #TODO - set timeout if leader is down?
            
            self.replicate_data()
     
        
    def get_pub_msg(self):
        print("Thread - getpubmsg - started")
        #barrier until become leader
        while self.isleader is False:
            pass
        while True:
            print("getpubmsg while loop***")
            msg = self.front_end_socket.recv_string()
            message = msg.split(' ')
            msg_type = message[0]
            pubid = message[1]
            topic = message[2]
            strength = message[3]
            if msg_type == 'register':
                self.update_data('publisher', pubid, topic, strength, '')
            elif msg_type == 'publish':
                publication = message[4]
                self.update_data('publication', pubid, topic, strength, publication)
                
            #reliable multicast PUSH/PULL on state transaction
            #TODO - I'm just resending original message - is there a better way?
            #self.replica_socket.send_string(msg)
            ##update replicate data too


    def update_data(self, add_this, pubid, topic, strength, publication):
        try:
            if add_this == 'publisher':
                if topic not in self.pub_data.keys():
                    self.pub_data.update({topic: {pubid: {'strength': strength, 'publications': []}}})
                elif pubid not in self.pub_data[topic].keys():
                    self.pub_data[topic].update({pubid: {'strength': strength, 'publications': []}})
            elif add_this == 'publication':
                stored_publication = publication + '--' + str(time.time())
                self.pub_data[topic][pubid]['publications'].append(stored_publication)
        except KeyError as ex:
            print(ex)

    def replicate_data(self):
        #barrier - must be follower - may need to be update if replicated leaders
        while self.isleader is False:
            try:
                recv_pushed_pub_data = self.replica_socket.recv_string()
            except Exception as e:
                print(f'timeout error {e}')
                continue
            message = recv_pushed_pub_data.split(' ')
            msg_type = message[0]
            pubid = message[1]
            topic = message[2]
            strength = message[3]
            if msg_type == 'register':
                self.update_data('publisher', pubid, topic, strength, '')
            elif msg_type == 'publish':
                publication = message[4]
                self.update_data('publication', pubid, topic, strength, publication)
                

    def won_election(self): 
        print(f'New Leader Won Election: {self.my_path}')
        
        #check leader barrier node
        if self.zk.exists(self.leader_path) is None:
            self.zk.create(self.leader_path, value=self.ip.encode(
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
