import commands

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
            }
        }

    def getNodeStatus(self):
        metric_value = 2    # '2' as defined by Chen Xin, indicating a success (node status is good)

        # check all nodes, see it as failed if any one node failed
        cmd = 'for node in $(kubectl get nodes|grep -v NAME|awk \'{print $1}\'|grep -v master);do kubectl describe node $node;done|egrep -q \"\s+Ready\s+False\";echo $?'
        if commands.getoutput(cmd) == '0':
            metric_value = 0
        return metric_value
