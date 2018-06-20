# docker_ps.py
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
    
    # for name,meta in mf.metrics.iteritems():
        # d = dict(meta)
        # d['name'] = name
        # d['call_back'] = metric_handler
        # metricList.append(d)
        
    # docker_ps metric
    meta = mf.metrics['docker_ps']
    d = dict(meta)
    d['name'] = 'docker_ps'
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
        
        
