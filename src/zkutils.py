import time

from kazoo.client import KazooClient
from kazoo.client import KazooState
from kazoo.exceptions import (
    ConnectionClosedError,
    NoNodeError,
    KazooException
)


def create(url="/test", value="hello!", intf="localhost", port="2181"):
    zk = start_client(intf, port)
    if not zk.exists(path=url):
        zk.create(url, value=value.encode('utf-8'))
    zk.close
    return zk


def await_sucessful_create(url="/test", value="hello!", intf="10.0.0.1", port="2181"):
    zk = start_client(intf, port)
    while(zk.exists(path=url)):
        time.sleep(.250)
        continue
    zk.create(url, value=value.encode('utf-8'), ephemeral=True)
    return zk


def delete(url="/test", intf="127.0.0.1", port="2181"):
    zk = start_client(intf, port)
    if zk.exists(path=url):
        zk.delete(url)
    return zk


def set_val(url="/test", value=b"hello!", intf="localhost", port="2181"):
    zk = start_client(intf, port)
    if(zk.exists(path=url)):
        zk.set(path=url, value=value)
    return zk


def get_val(url="/test", intf="localhost", port="2181"):
    zk = start_client(intf, port)
    return zk.get(path=url)


def start_kazoo_client(intf="localhost", port="2181"):
    url = f'{intf}:{port}'
    print(f"starting ZK client on '{url}'")
    zk = KazooClient(hosts=url)
    zk.start()
    return zk
