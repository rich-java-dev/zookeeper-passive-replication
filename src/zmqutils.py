import zmq
from zmq.utils.monitor import recv_monitor_message
import threading
import time
import netifaces as ni
from zkutils import (
    create, delete, get_val, set_val,
    start_client,
    await_sucessful_create
)

context = zmq.Context()


def proxy(in_bound=5555, out_bound=5556):
    ip = get_ip()
    print(ip)
    zk = await_sucessful_create("/proxy", ip)

    # many SUB handling
    front_end = context.socket(zmq.XSUB)
    front_end.bind(f"tcp://*:{in_bound}")

    # many PUB handling
    back_end = context.socket(zmq.XPUB)
    back_end.setsockopt(zmq.XPUB_VERBOSE, 1)
    back_end.bind(f"tcp://*:{out_bound}")

    print(f"Proxy started w/ in_bound={in_bound}, out_bound={out_bound}")

    zmq.proxy(front_end, back_end)


def publisher(interface, port=5555, bind=True, connect=False, topic_min=0, topic_max=100000):
    conn_str = f'tcp://{interface}:{port}'

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

    socket = context.socket(zmq.PUB)
    monitor = socket.get_monitor_socket()

    t = threading.Thread(target=evt_monitor, args=(monitor,))
    t.start()

    print(
        f'Publishing to {conn_str} w/ topic range:[{topic_min},{topic_max}]')

    if bind:
        for intf in interface:
            conn_str = f'tcp://{intf}:{port}'
            print(f"binding: {conn_str}")
            socket.bind(conn_str)

    if connect:
        for intf in interface:
            conn_str = f'tcp://{intf}:{port}'
            print(f"connecting: {conn_str}")
            socket.connect(conn_str)

    return lambda topic, msg: socket.send_string(f'{topic} {msg}')


def subscriber(interface='', port=5556, topic='', net_size=0):
    conn_str = f'tcp://{interface}:{port}'
    socket = context.socket(zmq.SUB)

    print(f"Subscribing to '{conn_str}' w/ topic '{topic}'")

    if(net_size > 0):
        for i in range(net_size):
            conn_str = f'tcp://10.0.0.{i}:{port}'
            print(f"connecting: {conn_str}")
            socket.connect(conn_str)
    else:
        for intf in interface:
            conn_str = f'tcp://{intf}:{port}'
            print(f"connecting: {conn_str}")
            socket.connect(conn_str)

    socket.setsockopt_string(zmq.SUBSCRIBE, topic)

    return lambda: socket.recv_string()


def get_ip():
    intf_name = ni.interfaces()[1]
    print(f'interface: {intf_name}')
    return ni.ifaddresses(intf_name)[ni.AF_INET][0]['addr']
