import sys
import time
import argparse
from zutils import Subscriber
import datetime
import uuid


parser = argparse.ArgumentParser()
parser.add_argument("--proxy", action="store_true", default=False)
parser.add_argument("--port", default="5556")
parser.add_argument("--topic", default="12345")
parser.add_argument("--sample_size", "--samples", default=5000)
parser.add_argument("--label", default="default")
args = parser.parse_args()

proxy = args.proxy
port = args.port
topic = args.topic
sample_size = int(args.sample_size)
label = args.label
sub_id = uuid.uuid4()

# mxm - returns topic temp humid timestamp

subscriber = Subscriber(port, topic, proxy)
notify = subscriber.start()

plot_data_set = []
while len(plot_data_set) < sample_size:

    msg = notify()
    zipcode, pub_id, temp, humid, sent_time = msg.split()

    recv_time = time.time()

    #msg_time = float(msg.split(" ")[-1])
    delta = recv_time - float(sent_time)
    plot_data_set.append(delta)
    print(msg)
    with open(f'../logs/{label}.log', 'a+') as session_data:
        session_data.write(
            f'{pub_id} {sub_id} {topic} {temp} {humid} {delta}\n')

subscriber.plot_data(plot_data_set)
