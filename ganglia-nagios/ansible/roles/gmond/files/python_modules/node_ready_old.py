# node_ready.py
from MetricBook import MetricBook

mf = MetricBook()
def metric_handler(name):
    metricValue = None
    callback = getattr(mf,mf.metrics[name]['call_back'])
    rt = callback()   
    metricValue = rt
    return metricValue

def metric_init(params):
    global metricList
    metricList = []
    d = {}
        
    # node_ready metric
    meta = mf.metrics['node_ready']
    d = dict(meta)
    d['name'] = 'node_ready'
    d['call_back'] = metric_handler
    metricList.append(d)
    return metricList

    
def metric_cleanup():
    pass
    
    
if __name__ == '__main__':
    myparams = {'hello': 'world'}
    metric_init(myparams)
    for m in metricList:
        v = metric_handler(m['name'])
        print 'value of %s is %s' % (m['name'], v)
        
        
