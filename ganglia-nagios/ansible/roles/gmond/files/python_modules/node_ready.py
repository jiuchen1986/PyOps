#!/usr/bin/python
# ganglia python module checking kubernetes node ready status

import yaml
import urllib2
import ssl
import json
import socket
import logging

KUBELET_CONF = '/etc/kubernetes/node-kubeconfig.yaml'
KUBE_SERVER = ''
CLIENT_CERT = '/etc/ganglia/ganglia-kube-cert/ganglia-nodes-reader.pem'
CLIENT_KEY = '/etc/ganglia/ganglia-kube-cert/ganglia-nodes-reader-key.pem'
HOSTNAME = ''
KUBE_NODES_URL = '/api/v1/nodes/'
METRIC_NAME = 'node_ready'

STATUS_READY = 2
STATUS_NOT_READY = 1

TIME_MAX = 60
VALUE_TYPE = 'uint'
UNITS = 'NODE READY'
SLOPE = 'both'
FORMAT = '%d'

CHECK_ERROR = 0


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('node_ready_new')
# log.setLevel(logging.DEBUG)
# fh = logging.FileHandler("/root/ezhecnx/plugin.log")
# fh.setLevel(logging.DEBUG)
# formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# fh.setFormatter(formatter)
# log.addHandler(fh)

def check_handler(name):
    '''Handler to check service'''

    global CLIENT_CERT, CLIENT_KEY, KUBE_SERVER, HOSTNAME, KUBE_NODES_URL
    ssl_ctx = ssl._create_unverified_context()
    try:
        ssl_ctx.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
    except Exception, e:
        log.debug('error %s occurs', e)
        return CHECK_ERROR
    req_url = KUBE_SERVER + KUBE_NODES_URL + HOSTNAME
    req = urllib2.Request(req_url)
    try:
        resp = urllib2.urlopen(req, context=ssl_ctx)
        if resp.getcode() != 200:
            log.debug('fail to connect to api server with bad code: %d' % resp.getcode())
            return CHECK_ERROR
        json_str = ''
        for l in resp.readlines():
            json_str = json_str + l
        node_info = json.loads(json_str.replace('\n', ''))
        status_ready = [c for c in node_info['status']['conditions'] if c['type'] == 'Ready'][0]['status']
        if status_ready == 'True':
            log.debug('node is ready')
            return STATUS_READY
        log.debug('node is not ready')
        return STATUS_NOT_READY
    except Exception, e:
        log.debug('error %s occurs', e)
        return CHECK_ERROR

    return CHECK_ERROR

# def generate_desc(name,
                  # check_target,
                  # time_max=TIME_MAX,
                  # value_type=VALUE_TYPE,
                  # slope=SLOPE,
                  # format=FORMAT):
    # '''Generat a descriptor'''

    # info_list = name.split('-')
    # d = dict(name=name,
                # call_back=check_handler,
                # time_max=time_max,
                # value_type=value_type,
                # slope=slope,
                # format=format,
                # description='{0} of {1} {2}'.format(info_list[1], info_list[0], info_list[2]),
                # groups='systemd managed ' + info_list[0])
    # log.debug('return a descriptor %r' % d)
    # return d

def metric_init(params):
    '''Initiate metrics'''

    global descriptors, \
           KUBELET_CONF, CLIENT_CERT, CLIENT_KEY, KUBE_SERVER, HOSTNAME, KUBE_NODES_URL, \
           METRIC_NAME, \
           STATUS_READY, STATUS_NOT_READY, \
           TIME_MAX, VALUE_TYPE, UNITS, SLOPE, FORMAT, \
           CHECK_ERROR

    descriptors = []

    KUBELET_CONF = params.get('kubelet_conf', KUBELET_CONF)
    CLIENT_CERT = params.get('client_cert', CLIENT_CERT)
    CLIENT_KEY = params.get('client_key', CLIENT_KEY)
    with open(KUBELET_CONF, 'r') as f:
        kube_conf = yaml.load(f)
        KUBE_SERVER = kube_conf['clusters'][0]['cluster']['server']
        # CLIENT_CERT = kube_conf['users'][0]['user']['client-certificate']
        # CLIENT_KEY = kube_conf['users'][0]['user']['client-key']
        log.debug('kube_server: %s, client_cert: %s, client_key: %s', KUBE_SERVER, CLIENT_CERT, CLIENT_KEY)
    HOSTNAME = socket.gethostname().split('.')[0]

    d = dict(name=METRIC_NAME,
             call_back=check_handler,
             time_max=TIME_MAX,
             value_type=VALUE_TYPE,
             slope=SLOPE,
             format=FORMAT,
             units=UNITS,
             description='kube node ready status of ' + HOSTNAME,
             groups='kube status')
    descriptors.append(d)
    log.debug('build a descriptor %r' % d)

    return descriptors

def metric_cleanup():
    '''Clean up the metric module.'''
    pass

#This code is for debugging and unit testing
if __name__ == '__main__':
    metric_init({})
    for d in descriptors:
        v = d['call_back'](d['name'])
        log.debug('value for %s is %u' % (d['name'],  v))