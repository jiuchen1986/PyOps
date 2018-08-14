#!/bin/python

import yaml
import argparse
import os

global parser, args, header_host, host_map

parser = argparse.ArgumentParser()
parser.add_argument("-n", "--clustername", help="name of the cluster")
parser.add_argument("-p", "--gmondport", type=int, help="port the gmond listens on the host")
parser.add_argument("-c", "--contacts", help="optional cluster contact list splitted by comma, default is Ting Yan")
parser.add_argument("-v", "--basicvars", help="path to the basic vars file")
parser.add_argument("-o", "--outputdir", help="dir storing the output files")
parser.add_argument("-i", "--invfile", help="path to the original inventory file")
parser.add_argument("-t", "--hosttype", help="optional type of hostname appearing in gangali, short or fqdn, default is fqdn")
parser.add_argument("-g", "--gmondportsfile", help="optional path to a file storing the mappings between cluster name and gmond port, \
                                                    if this is set, the value of gmondport will be ignored, and a port is generated from \
                                                    the maximal port indicated in the file plus 1")
args = parser.parse_args()

header_host = '' # ip of the host as the header of the cluster, default points to master 1
host_map = {} # ip:hostname

# parse the inventory file
def parse_inv():
  global header_host, host_map, args
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
def gen_new_inv():
  global header_host, host_map, args
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

# generate the vars file used by add_hostnames_to_hosts.yaml
def gen_hosts_map():
  global header_host, host_map, args
  add_hosts = {}
  hosts_output_file = os.path.join(args.outputdir, args.clustername + '_hosts.yaml')
  add_hosts['target'] = header_host
  add_hosts['host_maps'] = host_map
  with open(os.path.abspath(hosts_output_file), 'w') as hosts_output:
    yaml.dump(add_hosts, hosts_output, default_flow_style=False)
    hosts_output.close()
  
# generate the vars file
def gen_vars():
  global header_host, host_map, args
  vars = {}
  ports = []
  port_maps = {}
  with open(os.path.abspath(args.basicvars), 'r') as basic_vars:
    vars = yaml.load(basic_vars)
    basic_vars.close()
  if args.gmondportsfile:
    with open(os.path.abspath(args.gmondportsfile), 'r') as gmond_ports:
      for l in gmond_ports.readlines():
        ports.append(int(l.split()[1]))
        port_maps[l.split()[0]] = int(l.split()[1])
      gmond_ports.close()
  vars_output_file = os.path.join(args.outputdir, args.clustername + '.yaml')
  with open(os.path.abspath(vars_output_file), 'w') as vars_output:
    if len(ports) == 0:
      vars['gmond_multicast_port'] = args.gmondport
    elif args.clustername in port_maps:
      vars['gmond_multicast_port'] = port_maps[args.clustername]
    else:
      vars['gmond_multicast_port'] = max(ports) + 1
    print("select %d as gmond port" % vars['gmond_multicast_port'])
    vars['gmond_cluster_head'] = [header_host + ':{{ gmond_multicast_port }}']
    vars['nagios_check_ganglia_hostname_type'] = 'fqdn'
    if args.contacts:
      vars['cluster_contacts'] = args.contacts.split(',')
    if args.hosttype:
      vars['nagios_check_ganglia_hostname_type'] = args.hosttype
    yaml.dump(vars, vars_output, default_flow_style=False)
    vars_output.close()
  
  # record the mapping between the cluster name and the gmond port
  if args.gmondportsfile:
    with open(os.path.abspath(args.gmondportsfile), 'a') as gmond_ports:
      if args.clustername not in port_maps:
        gmond_ports.write("%s                  %d\n" % (args.clustername, vars['gmond_multicast_port']))
      gmond_ports.close()

if __name__ == '__main__':

  parse_inv()
  gen_new_inv()
  gen_hosts_map()
  gen_vars()