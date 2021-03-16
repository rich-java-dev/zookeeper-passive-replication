# Distributed Systems Principles - Assignment 2
## Pub/Sub Distributed Message Queue with Leader Election/Zookeeper
### Richard White, Max Coursey 


 PUB/SUB model supported by the ZeroMQ (ZMQ) middleware. Application maintains a broker, well known to the publishers and subscribers. This broker performs matchmaking. Data is disseminated from publishers to subscribers in a globally configurable way using one of the two approaches.

> 1) Simulated "Flooding" - Publisher’s middleware layer directly send the data to the subscribers who are interested in the topic being published by this publisher. 

> 2) Centralized -  Publisher’s middleware sends information to the broker, which then sends on to the subscribers for this topic.

The latency is calculated in two ways - First with wireshark sniffing and a second way by utilizing timestamps for the publishers sent time and the subscriber's received time.  The plots of latency are generated with Matplotlib.

The main.py method can take an arugment of the number of pub/subs and whether to utilize the centralized or simulated flooding method.

## Built With
- Ubuntu 20.04 (on VirtualBox)
- Python3
- Mininet
- ZeroMQ
- Zookeeper
- Wireshark

Python libraries:
 - kazoo
 - pyshark
 - matplotlib
 - pyzmq
 - mininet
 - netifaces

**What you need to install on Ubuntu:**
- mininet - http://mininet.org/download/
- python3/pip3  - sudo apt install python3-pip
- wireshark - sudo pip install wireshark (also included with mininet)
- pyshark - sudo pip install pyshark
- zmq - sudo -H pip3 install pyzmq
- matplotlib - sudo apt-get install python3-matplotlib

## SET-UP:
- Clone repo - https://github.com/rich-java-dev/cs6381-assignment2.git
- Navigate to cs6381-assignment2 folder
- run **pip install -r requirements.txt**
 - This will ensure all the of python packages used are installed.
- run **sudo mn -c** between runs
- run **ps -e | grep java** to get a list of pids for java apps to ensure zookeeper is not already running
- run **sudo kill {pid}** to kill any existing java apps (We will deploy Zookeeper on a mininet host)


## Running via main.py script
- Run the following commands from main Ubuntu CLI (not any mininet xterm window)

With Broker:
 >sudo python3 main.py --zkpath='/path/to/zkserver/bin' --pub_count=10 --proxy_mode

For flooding:
 >sudo python3 main.py --zkpath='/path/to/zkserver/bin' --pub_count=10

## **Running mininet and commands manually in xterm windows**
 > sudo mn -x --topo=linear,10
 > **host1**: /path/to/zookeeper/bin/zkServer.sh start
 > **host2**: python3 proxy.py --zkserver={ip if not host1, else ommit}
 > **host3**: python3 proxy.py --zkserver={ip if not host1, else ommit}
 > **host4**: python3 proxy.py --zkserver={ip if not host1, else ommit}
 > **host5**: python3 publisher.py --proxy --zkserver={ip if not host1, else ommit}
 > **host6**: python3 subscriber.py --proxy --samples=10000 --zkserver={ip if not host1, else ommit}

- Once the Subscriber begins receiving messages, kill host2
- Host3 will be elected leader, and after a few seconds the subscriber will begin receiving connections via the new proxy
- Kill Host3, and Host4 will be elected leader, same as described above.


## App Structure

**proxy.py**
usage: proxy.py --xin=5555 --xout=5556 --zkserver=10.0.0.1 [-h] [--zkserver ZKSERVER] [--xin XIN] [--xout XOUT]

>optional arguments:
  -h, --help            show this help message and exit
  --zkserver ZKSERVER, --zkintf ZKSERVER
  --xin XIN, --in_bound XIN
  --xout XOUT, --out_bound XOUT


**publisher.py**
usage: publisher.py [-h] [--zkserver ZKSERVER] [--port PORT] [--topic TOPIC] [--proxy]

>optional arguments:
  -h, --help            show this help message and exit
  --zkserver ZKSERVER, --zkintf ZKSERVER
  --port PORT
  --topic TOPIC
  --proxy

**subscriber.py**
usage: subscriber.py [-h] [--proxy] [--zkserver ZKSERVER] [--port PORT] [--topic TOPIC]
                     [--sample_size SAMPLE_SIZE] [--label LABEL]

>optional arguments:
  -h, --help            show this help message and exit
  --proxy
  --zkserver ZKSERVER, --zkintf ZKSERVER
  --port PORT
  --topic TOPIC
  --sample_size SAMPLE_SIZE, --samples SAMPLE_SIZE
  --label LABEL

**monitor.py** 
(pyshark api for monitoring TCP packets (TTDs)) - must be ran as root/sudo
usage: monitor.py [-h] [--interface INTERFACE] [--net_size NET_SIZE]
                  [--sample_size SAMPLE_SIZE]
>optional arguments:
  -h, --help            show this help message and exit
  --interface INTERFACE
  --net_size NET_SIZE
  --sample_size SAMPLE_SIZE, --samples SAMPLE_SIZE

**main.py** 
(driver for configuring network)
usage: main.py [-h] [--zkserver ZKSERVER] [--zkpath ZKPATH] [--proxy_mode] [--xin XIN] [--xout XOUT]
               [--pub_count PUB_COUNT] [--proxy_count PROXY_COUNT]

>optional arguments:
  -h, --help            show this help message and exit
  --zkserver ZKSERVER, --zkintf ZKSERVER
  --zkpath ZKPATH, --zk_bin_path ZKPATH
  --proxy_mode
  --xin XIN
  --xout XOUT
  --pub_count PUB_COUNT
  --proxy_count PROXY_COUNT