#!/bin/python

import yaml
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("-n", "--clustername", help="name of the cluster")
parser.add_argument("-p", "--gmondport", type=int, help="port the gmond listens on the host")
parser.add_argument("-c", "--contacts", help="optional cluster contact list splitted by comma, default is Ting Yan,Wei Wang ")
parser.add_argument("-v", "--basicvars", help="path to the basic vars file")
parser.add_argument("-o", "--outputdir", help="dir storing the output files")
parser.add_argument("-i", "--invfile", help="path to the original inventory file")
parser.add_argument("-t", "--hosttype", help="optional type of hostname appearing in gangali, short or fqdn, default is fqdn")
args = parser.parse_args()

header_host = '' # ip of the host as the header of the cluster, default points to master 1
host_map = {} # ip:hostname

# parse the inventory file
with open(os.path.abspath(args.invfile), 'r') as inv_ori:
  for l in inv_ori.readlines():
    data = l.split()
    if len(data) >= 3:
      if 'ansible_host' in data[1]:
        host_ip = data[1].split('=')[1]
        host_name = data[2].split('=')[1]
        host_map[host_ip] = host_name
        if header_host == '':
          if ('master1' in host_name) or ((args.clustername + '-1') in host_name):
            header_host = host_ip
            print("select %s as header host" % host_name)
  inv_ori.close()

# generate the new inventory file
inv_output_file = os.path.join(args.outputdir, args.clustername)
with open(os.path.abspath(inv_output_file), 'w') as inv_output:
  inv_output.write("[" + args.clustername + "]\n")
  for k, v in host_map.items():
    if 'lb' not in v:
      if 'node' not in v:
        inv_output.write(k + "  cluster_role=master\n")
      else:
        inv_output.write(k + "  cluster_role=worker\n")
  inv_output.close()

# generate the data may need to fill the hosts file at header host
hosts_output_file = os.path.join(args.outputdir, args.clustername + '_hosts')
with open(os.path.abspath(hosts_output_file), 'w') as hosts_output:
  for k, v in host_map.items():
    if k != header_host:
      hosts_output.write(k + " " + v + "\n")
  hosts_output.close()
  
# generate the vars file
vars = {}
with open(os.path.abspath(args.basicvars), 'r') as basic_vars:
  vars = yaml.load(basic_vars)
  basic_vars.close()
vars_output_file = os.path.join(args.outputdir, args.clustername + '.yaml')
with open(os.path.abspath(vars_output_file), 'w') as vars_output:
  vars['gmond_multicast_port'] = args.gmondport
  vars['gmond_cluster_head'] = [header_host + ':{{ gmond_multicast_port }}']
  vars['nagios_check_ganglia_hostname_type'] = 'fqdn'
  if args.contacts:
    vars['cluster_contacts'] = args.contacts.split(',')
  if args.hosttype:
    vars['nagios_check_ganglia_hostname_type'] = 'short'
  yaml.dump(vars, vars_output, default_flow_style=False)
  vars_output.close()