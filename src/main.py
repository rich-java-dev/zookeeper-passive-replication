from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topo import SingleSwitchTopo
import time
import pathlib
from random import randrange
import argparse

# sudo python3 main.py --flood_mode=False --pub_count=5 --sub_count=10
parser = argparse.ArgumentParser()
parser.add_argument("--zkserver", "--zkintf", default="10.0.0.1")
parser.add_argument("--zkpath", "--zk_bin_path",
                    default="/home/rw/zookeeper/bin")
parser.add_argument("--proxy_mode", action="store_true", default=False)
parser.add_argument("--xin", default="5555")  # for use with broker
parser.add_argument("--xout", default="5556")  # for use with broker
parser.add_argument("--pub_count", default=5)
parser.add_argument("--proxy_count", default=3)
args = parser.parse_args()

# gets reference to directory of this project to launch scripts
src_dir = pathlib.Path(__file__).parent.absolute()

# zookeeper params: need to know where zookeeper is running/installed
zkserver = args.zkserver  # IP of host running Zookeeper
zkpath = args.zkpath  # try to start zookeeper server inside mininet

# run configuration and network size
proxy_mode = args.proxy_mode
proxy_count = args.proxy_count
pub_count = int(args.pub_count)

# total net size: +1 indicates host for zookeeper server to start on
host_count = 1 + 2 * pub_count
if proxy_mode:
    host_count = host_count + proxy_count
print(f'host count: {host_count}')

# mininet specific set-up
net_topo = LinearTopo(k=host_count)  # feel free to run with other topos
net = Mininet(topo=net_topo)  # create the Mininet network w/ given topo and size
net.start()

# ports used by the proxy for listening and broadcasting
xin = args.xin  # proxy input (pub connection)
xout = args.xout  # proxy output (sub connection)

# print label for the graphs
label = f'proxy_pub_sub{pub_count}' if proxy_mode else f'flood_pub_sub{pub_count}'
print(label)

# set up publishers

# generate some random topics
pub_topics = [randrange(1e4, 1e5) for x in range(pub_count)]

print("Random Topics for this run:")
print(pub_topics)

print("Starting zookeeper server on host 0 (10.0.0.1)")
zk_script = f'{zkpath}/zkServer.sh start &'
print(zk_script)
net.hosts[0].cmd(zk_script)

#Give zookeeper a few seconds to start before running components which need zk up
time.sleep(2)

if proxy_mode:  # PROXY MODE

    for i in range(0, proxy_count):  # run proxies
        host_idx = 1 + i
        cmd_str = f'python3 {src_dir}/proxy.py &'
        print(cmd_str)
        net.hosts[host_idx].cmd(cmd_str)

    for i in range(0, pub_count):  # run publishers
        topic = pub_topics[i]
        host_idx = 1 + proxy_count + i
        cmd_str = f'python3 {src_dir}/publisher.py --zkserver={zkserver} --port={xin} --topic {int(topic)} &'
        print(cmd_str)
        net.hosts[host_idx].cmd(cmd_str)

    for i in range(0, pub_count):  # run subscribers
        topic = pub_topics[i]
        host_idx = 1 + pub_count + i
        cmd_str = f'python3 {src_dir}/subscriber.py --zkserver={zkserver} --port={xin} --topic {topic} --label={label} &'
        print(cmd_str)
        net.hosts[host_idx].cmd(cmd_str)

else:  # FLOOD MODE/NO PROXIES

    for i in range(0, pub_count):  # run publishers
        topic = pub_topics[i]
        host_idx = 1 + i
        cmd_str = f'python3 {src_dir}/publisher.py --zkserver={zkserver} --port={xin} --topic {int(topic)} &'
        print(cmd_str)
        net.hosts[host_idx].cmd(cmd_str)

    for i in range(0, pub_count):  # run subscribers
        topic = pub_topics[i]
        host_idx = 1 + pub_count + i
        cmd_str = f'python3 {src_dir}/subscriber.py --zkserver={zkserver} --port={xin} --topic {topic} --label={label} &'
        print(cmd_str)
        net.hosts[host_idx].cmd(cmd_str)

while(True):
    time.sleep(0.001)
