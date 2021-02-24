# Distributed Systems Principles - Assignment 2
## Leader Election in Pub/Sub model with ZooKeeper
### Richard White, Max Coursey 

### https://youtu.be/KANdeYaW1_8

PUB/SUB model supported by the ZeroMQ (ZMQ) middleware. Application maintains a broker, well known to the publishers and subscribers. This broker performs matchmaking. Data is disseminated from publishers to subscribers in a globally configurable way using one of the two approaches.
1) Simulated "Flooding" - Publisher’s middleware layer directly send the data to the subscribers who are interested in the topic being published by this publisher. 

2) Centralized -  Publisher’s middleware sends information to the broker, which then sends on to the subscribers for this topic.

The latency is calculated in two ways - First with wireshark sniffing and a second way by utilizing timestamps for the publishers sent time and the subscriber's received time.  The plots of latency are generated with Matplotlib.

The main.py method can take an arugment of the number of pub/subs and whether to utilize the centralized or simulated flooding method.

## Built With
- Ubuntu 20.04 (on VirtualBox)
- Python3 
- Mininet
- ZeroMQ (zmq, pyzmq)
- Wireshark, pyshark, tshark 
- Matplotlib

**What you need to install on Ubuntu:**
- mininet - http://mininet.org/download/
- python3/pip3  - sudo apt install python3-pip
- wireshark - sudo pip install wireshark (also included with mininet)
- pyshark - sudo pip install pyshark
- zmq - sudo -H pip3 install pyzmq
- matplotlib - sudo apt-get install python3-matplotlib

## How to RUN 
- Clone repo - https://github.com/rich-java-dev/cs6381-assignment1.git
- Navigate to cs6381-assignment1 folder
- Run the following commands from main Ubuntu CLI (not any mininet xterm window)
--**replace x and y** with respective number of pub/subs to run 

For centralized:
- >sudo python3 main.py --pub_count=x --sub_count=y
- >sudo python3 monitor.py --interface=any --sample_size=500 

For flooding: 
- >sudo python3 main.py **--flood_mode**  --pub_count=x --sub_count=y
- >sudo python3 monitor.py --interface=any --sample_size=500

Running mininet and commands manually in xterm windows


## App Structure
**publisher.py**
usage: publisher.py [-h] [--interface INTERFACE [INTERFACE ...]] [--port PORT]
                    [--topic_range TOPIC_RANGE [TOPIC_RANGE ...]] [--bind] [--connect]

>optional arguments:
  -h, --help            show this help message and exit
  --interface INTERFACE [INTERFACE ...], --proxy INTERFACE [INTERFACE ...], --device INTERFACE [INTERFACE ...]
  --port PORT
  --topic_range TOPIC_RANGE [TOPIC_RANGE ...]
  --bind
  --connect

**subscriber.py**
usage: subscriber.py [-h] [--interface INTERFACE [INTERFACE ...]] [--port PORT] [--topic TOPIC] [--net_size NET_SIZE]
>optional arguments:
  -h, --help            show this help message and exit
  --interface INTERFACE [INTERFACE ...], --proxy INTERFACE [INTERFACE ...], --device INTERFACE [INTERFACE ...]
  --port PORT
  --topic TOPIC
  --net_size NET_SIZE

**proxy.py**
usage: proxy.py --xin=5555 --xout=5556 [-h] [--xin XIN] [--xout XOUT]
>optional arguments:
  -h, --help            show this help message and exit
  --xin XIN, --in_bound XIN
  --xout XOUT, --out_bound XOUT

**monitor.py** (pyshark api for monitoring TCP packets (TTDs)) - must be ran as root/sudo
usage: monitor.py [-h] [--interface INTERFACE] [--net_size NET_SIZE]
                  [--sample_size SAMPLE_SIZE]
>optional arguments:
  -h, --help            show this help message and exit
  --interface INTERFACE
  --net_size NET_SIZE
  --sample_size SAMPLE_SIZE, --samples SAMPLE_SIZE

**main.py** (driver for configuring network)
usage: main.py [-h] [--flood_mode FLOOD_MODE] [--xin XIN] [--xout XOUT] [--topic TOPIC] [--net_size NET_SIZE] [--pub_count PUB_COUNT]
               [--source_dir SOURCE_DIR]
>optional arguments:
  -h, --help            show this help message and exit
  --flood_mode FLOOD_MODE
  --xin XIN
  --xout XOUT
  --topic TOPIC
  --net_size NET_SIZE
  --pub_count PUB_COUNT
  --source_dir SOURCE_DIR, --src_dir SOURCE_DIR

**zutils.py** (api wrapper)
We went with implementing callbacks vs. a more strict/formal OOP/class structure. The result is that both publishers and subscribers return a lambda which behaves as a 'thunk'.

## Sample Network Configuration:

**Automatic using main.py**:
-   sudo python3 main.py 

    Run the monitor (not on mininet host):
-   sudo python3 monitor.py --interface=any --sample_size=500

**Manual Configuration**
-   sudo mn -c
-   sudo mn -x --topo=linear,10

Proxy/Broker: (in_bound, out_bound)

-   host1: python3 broker.py --xin=5555 --xout=5556

Publishers: (bind|connect, interface, port, topic_range)

-   host2: python3 publisher.py --connect --interface=10.0.0.1 --port=5555 --topic_range 1 49999
-   host3: python3 publisher.py --connect --interface=10.0.0.1 --port=5555 --topic_range 50000 100000

Subscribers: (interface, port, topic)

-   host4: python3 subscriber.py --interface=10.0.0.1 --port=5556 --topic=12345
-   host5: python3 subscriber.py --interface=10.0.0.1 --port=5556 --topic=90210

Monitor: (interface ("s1-eth1",2,3...etc))

-   from localhost: sudo python3 monitor.py --interface=any --sample_size=500

 
