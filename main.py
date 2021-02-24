from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topo import SingleSwitchTopo
import time
import pathlib
from random import randrange
import argparse

# sudo python3 main.py --flood_mode=False --pub_count=5 --sub_count=10
parser = argparse.ArgumentParser()
parser.add_argument("--flood_mode", action="store_true", default=False)
parser.add_argument("--xin", default="5555")  # for use with broker
parser.add_argument("--xout", default="5556")  # for use with broker
parser.add_argument("--topic", default="")
parser.add_argument("--pub_count", default=3)
parser.add_argument("--sub_count", default=7)

args = parser.parse_args()
pub_count = int(args.pub_count)
sub_count = int(args.sub_count)  # mxm - added sub count for labeling
flood_mode = args.flood_mode
host_count = pub_count + sub_count if flood_mode else pub_count + sub_count + 1
print(f'hostcount: {host_count}')

src_dir = pathlib.Path(__file__).parent.absolute()

net_topo = LinearTopo(k=host_count)  # feel free to run with other topos
net = Mininet(topo=net_topo)  # create a 10 host net
net.start()


xin = args.xin  # proxy input (pub connection)
xout = args.xout  # proxy output (sub connection)

# set up publishers
topic_size = 1e5 / pub_count


mLabel = f'flood_pub{pub_count}_sub{sub_count}' if flood_mode else f'centralized_pub{pub_count}_sub{sub_count}'
print(mLabel)

if flood_mode:
    # pub.py <proxy_interface> <interface_port (proxy subscrib port)> <publisher_range_min> <publisher_range_max>
    for i in range(0, pub_count):
        cmd_str = f'python3 {src_dir}/publisher.py --bind --port={xin} --topic_range {int(i*topic_size)} {int((i+1)*topic_size)} &'
        print(cmd_str)
        net.hosts[i].cmd(cmd_str)

    # sub.py <proxy_interface> <interface_port (proxy publish port)> <topic>
    for i in range(pub_count, pub_count + sub_count):
        topic = randrange(1e4, 1e5)
        cmd_str = f'python3 {src_dir}/subscriber.py --net_size={host_count} --port={xin} --topic={topic} --label={mLabel} --host=h{i+1} &'
        print(cmd_str)
        net.hosts[i].cmd(cmd_str)

else:  # with Proxy/Broker:
    # broker.py <proxy_input_port> <proxy_output_port>
    x_intf = "10.0.0.1"  # proxy interface
    prox_str = f'python3 {src_dir}/proxy.py &'
    print(prox_str)
    net.hosts[0].cmd(prox_str)

    # pub.py <proxy_interface> <interface_port (proxy subscrib port)> <publisher_range_min> <publisher_range_max>
    for i in range(0, pub_count):
        cmd_str = f'python3 {src_dir}/publisher.py --connect --interface={x_intf} --topic_range {int(i*topic_size)} {int((i+1)*topic_size)} &'
        print(cmd_str)
        net.hosts[i+1].cmd(cmd_str)

    # sub.py <proxy_interface> <interface_port (proxy publish port)> <topic>
    for i in range(pub_count, pub_count + sub_count + 1):
        topic = randrange(1e4, 1e5)
        cmd_str = f'python3 {src_dir}/subscriber.py --interface={x_intf} --port={xout} --topic={topic} --label={mLabel} --host=h{i+1} &'
        print(cmd_str)
        net.hosts[i].cmd(cmd_str)

while(True):
    time.sleep(0.001)
