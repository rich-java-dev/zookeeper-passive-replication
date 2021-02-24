import sys
from random import randrange
import argparse
from zutils import publisher
import time
import uuid

parser = argparse.ArgumentParser()
parser.add_argument("--interface", "--proxy",
                    "--device", nargs="+", default="*")
parser.add_argument("--port", default="5555")
parser.add_argument("--topic_range", nargs="+")
parser.add_argument("--bind", action="store_true", default=False)
parser.add_argument("--connect", action="store_true", default=False)
args = parser.parse_args()

intf = args.interface
port = args.port
bind = args.bind
connect = args.connect
topic_min = args.topic_range[0] if args.topic_range else 0
topic_max = args.topic_range[1] if args.topic_range else 100000
pub_id = uuid.uuid4()

publish = publisher(intf, port, bind, connect, topic_min, topic_max)

while True:
    zipcode = randrange(int(topic_min), int(topic_max))
    temperature = randrange(-80, 135)
    relhumidity = randrange(10, 60)
    sent_time = time.time()
    msg = f'{pub_id} {temperature} {relhumidity} {sent_time}'

    publish(zipcode, msg)
    # time.sleep(0.00000001)
