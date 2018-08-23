#!/bin/python

# scripts used to help to modify group_vars file for clusters in batch

import yaml
import argparse
import os

DEFAULT_VARS_DIR = "/root/ansible/group_vars"

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--varsdir", help="dir of the group_vars file for each cluster, \
                                            default is %s" % DEFAULT_VARS_DIR)
parser.add_argument("-f", "--filelist", help="optional name list of the files need to be modified, \
                                              seperated by comma, \
                                              if not set, all files in the dir will be modified")

args = parser.parse_args()

if args.varsdir:
  vars_dir = os.path.abspath(args.varsdir)
else:
  vars_dir = os.path.abspath(DEFAULT_VARS_DIR)

file_list = []
if args.filelist:
  file_list = args.filelist.split(',')

