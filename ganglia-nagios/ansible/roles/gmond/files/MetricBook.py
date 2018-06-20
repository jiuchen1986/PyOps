import commands
import requests_unixsocket

class MetricBook(object):
    def __init__(self):
        self.metrics =  {
            'node_ready': {
                            'call_back'   : 'getNodeStatus',
                            'time_max'    : 10,
                            'value_type'  : 'uint',
                            'format'      : '%u',
                            'units'       : 'STATUS',
                            'slope'       : 'both',  # zero|positive|negative|both
                            'description' : 'XXX',
            },
            'docker_ps': {
                            'call_back'   : 'getDockerPs',
                            'time_max'    : 10,
                            'value_type'  : 'uint',
                            'format'      : '%d',
                            'units'       : 'XXX',
                            'slope'       : 'both',  # zero|positive|negative|both
                            'description' : 'XXX',
                            'groups'      : 'testgroup',    
            },
        }

    def getNodeStatus(self):
        metric_value = 2    # '2' as defined by Chen Xin, indicating a success (node status is good)

        # check all nodes, see it as failed if any one node failed
        cmd = 'for node in $(kubectl --kubeconfig=\'/etc/kubernetes/admin.conf\' get nodes|grep -v NAME|awk \'{print $1}\'|grep -v master);do kubectl describe node $node;done|egrep -q \"\s+Ready\s+[False|Unknown]\";echo $?'
        if commands.getoutput(cmd) == '0':
            metric_value = 0
        return metric_value

    def getDockerPs(self):
        metric_value = 2
        url = 'http+unix://%2Fvar%2Frun%2Fdocker.sock/containers/json'  # requirement: chmod a+rw /var/run/docker.sock
        s = requests_unixsocket.Session()
        r = s.get(url)
        # requests_unixsocket.monkeypatch()
        # r = requests.get(url)
        # docker_ps_status = r.status_code        
        # return int(docker_ps_status)
        if r.status_code != 200:
            metric_value = 0
        return metric_value