#!/usr/bin/python
# ganglia python module checking status of specific services managed by systemd

import commands as cmd
import logging
import re

CHECK_ERROR = 0
TARGET_SERVICES = ['docker', 'kubelet']
CHECK_TARGETS = ['status']
METRIC_PREFIX = 'service'

STATUS_ACTIVE = 2
STATUS_INACTIVE = 1

TIME_MAX = 60
VALUE_TYPE = 'uint'
UNITS = 'STATUS'
SLOPE = 'both'
FORMAT = '%d'


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('systemd_stats')
# log.setLevel(logging.DEBUG)
# fh = logging.FileHandler("/root/ezhecnx/plugin.log")
# fh.setLevel(logging.DEBUG)
# formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# fh.setFormatter(formatter)
# log.addHandler(fh)

def check_handler(name):
    '''Handler to check service'''

    info_list = name.split('-')
    check_target = info_list[1]
    svc_name = info_list[2]
    try:
        (exe_code, output) = cmd.getstatusoutput('systemctl status ' + svc_name)    
    except Exception, e:
        log.debug('error %s occurs', e)
        return CHECK_ERROR
    else:
        if check_target == 'status':
            if exe_code == 0:
                log.debug('service %s is active', svc_name)
                return STATUS_ACTIVE
            else:
                log.debug('service %s is not active', svc_name)
                return STATUS_INACTIVE

    return CHECK_ERROR

def generate_desc(name,
                  check_target,
                  time_max=TIME_MAX,
                  value_type=VALUE_TYPE,
                  slope=SLOPE,
                  format=FORMAT):
    '''Generat a descriptor'''

    info_list = name.split('-')
    d = dict(name=name,
                call_back=check_handler,
                time_max=time_max,
                value_type=value_type,
                slope=slope,
                format=format,
                description='{0} of {1} {2}'.format(info_list[1], info_list[0], info_list[2]),
                groups='systemd managed ' + info_list[0])
    log.debug('return a descriptor %r' % d)
    return d

def metric_init(params):
    '''Initiate metrics'''

    global descriptors, \
           CHECK_ERROR, TARGET_SERVICES, CHECK_TARGETS, METRIC_PREFIX, \
           STATUS_ACTIVE, STATUS_INACTIVE, \
           TIME_MAX, VALUE_TYPE, UNITS, SLOPE, FORMAT

    descriptors = []

    if 'target_services' in params:
        TARGET_SERVICES = [svc for svc in \
                           re.split(r'[,\s]', params['target_services']) \
                           if svc != '']

    for svc in TARGET_SERVICES:
        for target in CHECK_TARGETS:
            descriptors.append(generate_desc('-'.join([METRIC_PREFIX, target, svc]),
                                             target))

    return descriptors

def metric_cleanup():
    '''Clean up the metric module.'''
    pass

#This code is for debugging and unit testing
if __name__ == '__main__':
    metric_init({'target_services': 'docker, kubelet'})
    for d in descriptors:
        v = d['call_back'](d['name'])
        log.debug('value for %s is %u' % (d['name'],  v))