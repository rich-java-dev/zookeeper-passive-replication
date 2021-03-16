import sys
import argparse
from zutils import Proxy

parser = argparse.ArgumentParser("proxy.py --xin=5555 --xout=5556 --zkserver=10.0.0.1")
parser.add_argument("--zkserver","--zkintf", default="10.0.0.1")
parser.add_argument("--xin", "--in_bound", default="5555")
parser.add_argument("--xout", "--out_bound", default="5556")
args = parser.parse_args()

zkserver = args.zkserver
in_bound = args.xin
out_bound = args.xout

Proxy(zkserver, in_bound, out_bound).start()
