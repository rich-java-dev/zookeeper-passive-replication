from kazoo.client import KazooClient
from kazoo.client import KazooState
from kazoo.exceptions import (
    ConnectionClosedError,
    NoNodeError,
    KazooException
)
import logging

logging.basicConfig()

import os
import sys
import time
import threading
import zmq
from random import randint

#############################
## Max's Notes
## Utilize push/pull zmq sockets
## - if need sophisticated load-balancing - need to revisit with router/dealer et al
## - Should we utilize pub/sub instead for the leader/worker nodes?
## 
## Can create dicts to hold pub/sub ids topics, publications but will lose if leader/follower dies unless pushing state changes
##
## TODOS
## - factor out znode paths
## - add pub/sub state - dict, znode, DB?
#############################

class Broker:
    def __init__(self, zkserverip, broker_address):
        self.broker_id = randint(1000, 10000) #TODO - removed uuid.uuid4() - easier to read using 4 digit random
        self.context = zmq.Context()
        self.follower_socket = None
        self.leader_socket = None
       
        self.broker_address = broker_address
        self.zkaddress = zkserverip + ':2181'
        zk = KazooClient(hosts=self.zkaddress)
        
        self.zk.start() #need to check to ensure ZK is running'
        print('Broker %s connected to ZooKeeper server.')


#############################################################
        ##TODO-MXM - should we only create broker znode if not a leader?
        if self.zk.exists('/broker') is None:
            self.zk.create(path='/broker', value=b'', ephemeral=False, makepath=True)
        # Create a Znode in ZooKeeper
        broker_path = '/broker/' + self.broker_id
        self.zk.create(path=broker_path, value=b'', ephemeral=True, makepath=True)
        print(f'Broker {self.broker_id} znode created under /broker')

#############################################################
        if zk.exists('/leader'):
            print(f'Broker {self.broker_id} is a follower')
            
            #Watch leader path for changes
            @zk.DataWatch(path='/leader')
            def watch_leader(data, state):
                if zk.exists(path='/leader') is None:
                    election = zk.Election('/broker/', self.broker_id)
                    election.run(elect_leader) # blocks until wins or canceled
          
            #Create follower sock for receiving messages from leader
            crnt_leader_address = str(zk.get('/leader')[0])
            self.follower_socket = self.context.socket(zmq.PULL)
            #socket options?
            self.follower_socket.connect(f'tcp://{crnt_leader_address}:5559')
            print(f'Follower broker {self.broker_id} connected to leader {crnt_leader_address}:5559')
            
            # TODO - Update to make sure only followers run this
            while True:
                try:
                    recv_msg = self.follower_socket.recv_string()
                except:
                    print("Time out error")
                
                #TODO Replace with actual call to store message data
                print(f'Recv msg from leader\n{recv_msg}\n')
                                                        
        else:
            zk.create('/leader', value=broker_address, emphemeral=True, makepath=True)
            while zk.exists(path='/leader') is None:
                pass
            print(f'Broker {self.broker_id} is now a leader')
            leader_socket = self.context.socket(zmq.PUSH)
            leader_socket.bind('tcp://*:5559')
            #if broker_socket != None:
            print(f'Leader broker {self.broker_id} Bound to Port 5559')
                    
#############################################################
        def elect_leader(self):
            if zk.exists(path='leader') is None:
                zk.create('/leader', value=broker_address, ephemeral=True, makepath=True)   
                while zk.exists(path='/leader') is None:
                    pass
                print(f'Broker {self.broker_id} is the leader')
                context = zmq.Context()
                leader_socket = context.socket(zmq.PUSH)
                leader_socket.bind('tcp://*:5559')
                #if broker_socket != None:
                print(f'Leader broker {self.broker_id} Bound to Port 5559')
            
#############################################################   
        def watch_publishers(self):
            if zk.exists('/publisher') is None:
                zk.create(path='/publisher', value=b'', ephemeral=False, makepath=True)

            @zk.ChildrenWatch(path='/publisher')
            def watch_publishers(children):
                print("Remove publishers from state")

#############################################################   

