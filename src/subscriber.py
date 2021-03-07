import sys
import time
import argparse
from zmqutils import subscriber
import datetime
import matplotlib.pyplot as plt
import uuid


parser = argparse.ArgumentParser()
parser.add_argument("--interface", "--proxy",
                    "--device", nargs="+", default="*")
parser.add_argument("--port", default="5556")
parser.add_argument("--topic", default="")
parser.add_argument("--net_size", default=0)
parser.add_argument("--sample_size", "--samples", default=50)
parser.add_argument("--host", default="")
parser.add_argument("--label", default="default")

args = parser.parse_args()

intf = args.interface
port = args.port
topic = args.topic
net_size = int(args.net_size)
sample_size = int(args.sample_size)
label = args.label
sub_id = uuid.uuid4()
host = args.host

# mxm - returns topic temp humid timestamp
notify = subscriber(intf, port, topic, net_size)

delta_time_set = []
while len(delta_time_set) < sample_size:
    msg = notify()
    zipcode, pub_id, temp, humid, sent_time = msg.split()
    recv_time = time.time()
    #msg_time = float(msg.split(" ")[-1])
    delta = recv_time - float(sent_time)
    delta_time_set.append(delta)
    print(msg)
    with open(f'../logs/{label}.log', 'a+') as session_data:
        session_data.write(
            f'{pub_id} {sub_id} {topic} {temp} {humid} {delta}\n')

print(f'testing - {pub_id} {sub_id} {topic} {temp} {humid} {delta}\n')
# plot the time deltas
fig, axs = plt.subplots(1)
axs.plot(range(len(delta_time_set)), delta_time_set)
axs.set_title(f"RTTs '{label}' - topic '{topic}' - host '{host}'")
axs.set_ylabel("Delta Time (Pub - Sub)")
axs.set_xlabel("Number of Samples")
plt.show()
