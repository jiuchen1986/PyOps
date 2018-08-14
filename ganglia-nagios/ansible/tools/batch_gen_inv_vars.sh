#!/bin/python

import argparse
import os
import shutil

DEFAULT_SIN_GEN_FILE = "/root/ansible/tools/gen_inv_and_vars.sh"
DEFAULT_OUTPUT_DIR = "/root/ansible/gen_inv_vars"
DEFAULT_BAS_VARS_FILE = "/root/ansible/tools/basic_vars_eccd.yaml"
DEFAULT_PORTS_FILE = "/root/ansible/tools/cluster_gmond_ports"
DEFAULT_ADD_HOSTS_FILE = "/root/ansible/tools/add_hostnames_to_hosts.yaml"
DEFAULT_GROUP_VARS_DIR = "/root/ansible/group_vars"
DEFAULT_INVENTORY_DIR = "/root/ansible/inventory"

parser = argparse.ArgumentParser()
parser.add_argument("-l", "--clusterlist", help="cluster list splitted by comma")
parser.add_argument("-v", "--basicvars", help="path to the basic vars file, default is \"%s\"" % DEFAULT_BAS_VARS_FILE)
parser.add_argument("-o", "--outputdir", help="dir storing the output files, default is \"%s\"" % DEFAULT_OUTPUT_DIR)
parser.add_argument("-s", "--singlegen", help="path to the script file that generate inv and vars for a single cluster, \
                                               default is \"%s\"" % DEFAULT_SIN_GEN_FILE)
parser.add_argument("-a", "--addhosts", help="path to the ansible playbook file that adds host mappings \
                                              to the hosts file on cluster header, default is \"%s\"" % DEFAULT_ADD_HOSTS_FILE)
parser.add_argument("-g", "--gmondportsfile", help="optional path to a file storing the mappings between cluster name and gmond port, \
                                                    if this is set, the value of gmondport will be ignored, and a port is generated from \
                                                    the maximal port indicated in the file plus 1, default is \"%s\"" % DEFAULT_PORTS_FILE)
parser.add_argument("--groupvars", help="dir to ansible playbook group_vars setting up monitoring system, default is \"%s\"" % DEFAULT_GROUP_VARS_DIR)
parser.add_argument("--inventory", help="dir to ansible playbook inventory setting up monitoring system, default is \"%s\"" % DEFAULT_INVENTORY_DIR)


args = parser.parse_args()

cluster_list = args.clusterlist.split(',')

if args.singlegen:
  sin_gen_file = os.path.abspath(args.singlegen)
else:
  sin_gen_file = os.path.abspath(DEFAULT_SIN_GEN_FILE)

if args.outputdir:
  abs_output_dir = os.path.abspath(args.outputdir)
else:
  abs_output_dir = os.path.abspath(DEFAULT_OUTPUT_DIR)

if args.basicvars:
  bas_vars_file = os.path.abspath(args.basicvars)
else:
  bas_vars_file = os.path.abspath(DEFAULT_BAS_VARS_FILE)

if args.gmondportsfile:
  ports_file = os.path.abspath(args.gmondportsfile)
else:
  ports_file = os.path.abspath(DEFAULT_PORTS_FILE)

if args.addhosts:
  add_hosts_file = os.path.abspath(args.addhosts)
else:
  add_hosts_file = os.path.abspath(DEFAULT_ADD_HOSTS_FILE)
  
if args.outputdir:
  ori_inv_file = os.path.abspath(os.path.join(args.outputdir, 'ori_hosts'))
else:
  ori_inv_file = os.path.abspath(os.path.join(DEFAULT_OUTPUT_DIR, 'ori_hosts'))

if args.groupvars:
  group_vars_dir = os.path.abspath(args.groupvars)
else:
  group_vars_dir = os.path.abspath(DEFAULT_GROUP_VARS_DIR)

if args.inventory:
  inventory_dir = os.path.abspath(args.inventory)
else:
  inventory_dir = os.path.abspath(DEFAULT_INVENTORY_DIR)

for c in cluster_list:
  # fetch original inventory file from target cluster lb
  cmd_str = "scp root@%s:/home/raket/inventory/hosts %s" % (c, ori_inv_file)
  if os.system(cmd_str) != 0:
    os._exit(1)

  # generate inventory and vars file for a single cluster
  cmd_str = "%s -n %s -v %s -o %s -i %s -t short -g %s" % (sin_gen_file, c, bas_vars_file, \
                                                           abs_output_dir, ori_inv_file, ports_file)
  if os.system(cmd_str) != 0:
    os._exit(1)

  # add hosts info to the hosts file on the cluster header host
  add_hosts_vars = os.path.join(abs_output_dir, c + "_hosts.yaml")
  cmd_str = "ansible-playbook -e \"@%s\" %s" % (add_hosts_vars, add_hosts_file)
  if os.system(cmd_str) != 0:
    os._exit(1)

  # remove the original inventory file
  if os.system("rm -rf %s" % ori_inv_file) != 0:
    os._exit(1)

  # copy vars file to the group_vars dir used by ansible playbook
  shutil.copyfile(os.path.join(abs_output_dir, c + ".yaml"), os.path.join(group_vars_dir, c + ".yaml"))
  print("copy %s -> %s" % (os.path.join(abs_output_dir, c + ".yaml"), os.path.join(group_vars_dir, c + ".yaml")))
  
  # copy inv file to the inventory dir used by ansible playbook
  shutil.copyfile(os.path.join(abs_output_dir, c), os.path.join(inventory_dir, c))
  print("copy %s -> %s" % (os.path.join(abs_output_dir, c), os.path.join(inventory_dir, c)))
  