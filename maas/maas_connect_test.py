#!/usr/bin/env python3.5

import argparse
import logging
import time

from maas.client import connect as maas_connect
from maas.client.enum import NodeStatus

DEFAULT_IP = '150.132.115.79'
DEFAULT_PORT = '5240'
DEFAULT_KEY = 'EP2QFqr9RhYBHEpvgd:WfwgyKek6xhYHXRQBn:K6ftkVYLnMLaesm2phgtqnEjtDULKjkW'

DEFAULT_LOGLEVEL = 'DEBUG'
FORMAT = '%(levelname)s %(asctime)-15s %(module_name)s: %(message)s'
logging.basicConfig(format=FORMAT)
log = logging.getLogger(__name__)
LOG_DICT = {'module_name': __name__}

DEFAULT_MACHINE_TAG = 'REMOTE-MGMT'

parser = argparse.ArgumentParser(description='Testing connection to the maas server.')
parser.add_argument('-d', '--deploy', dest='deploy', default=argparse.SUPPRESS, nargs='?', const='true', 
                              help='Deploy a server in maas.')
parser.add_argument('-c', '--check', dest='check', default=argparse.SUPPRESS, nargs='?', const='true', 
                              help='Check a server in maas.')
parser.add_argument('-r', '--release', dest='release', default=argparse.SUPPRESS, nargs='?', const='true', 
                              help='release a server in maas.')

parser.add_argument('-n', '--machinename', dest='machinename', nargs='?', default=argparse.SUPPRESS, 
                              help='The name of the node to be operated on.')
parser.add_argument('-t', '--machinetags', dest='machinetags', nargs='*', default=[DEFAULT_MACHINE_TAG], 
                              help='The tags of the node to be operated on.')

parser.add_argument('-i', '--ip', dest='maas_ip', default=DEFAULT_IP, nargs='?', 
                              help='The ip address of the maas api server.')
parser.add_argument('-p', '--port', dest='maas_port', default=DEFAULT_PORT, nargs='?', 
                              help='The exposed port of the maas api server.')
parser.add_argument('--host', dest='maas_host', nargs='?', 
                              help='The host name of the maas api server.')
parser.add_argument('-k', '--key', dest='maas_apikey', default=DEFAULT_KEY, nargs='?', 
                              help='The apikey for the user to connect to the maas api server.')

parser.add_argument('-l', '--log', dest='log_level', default=DEFAULT_LOGLEVEL, nargs='?', 
                              help='The log level.')

args = parser.parse_args()
log.setLevel(args.log_level.upper())

maas_endpoint = args.maas_ip + ':' + args.maas_port
if(getattr(args, 'maas_host', None) != None):
  client = maas_connect("http://%s/MAAS/" % args.maas_host, apikey=args.maas_apikey)
  log.info("connect to the maas api server with hostname of %s and apikey of %s", args.maas_host, args.maas_apikey, extra=LOG_DICT)
else:  
  client = maas_connect("http://%s/MAAS/" % maas_endpoint, apikey=args.maas_apikey)
  log.info("connect to the maas api server with endpoint of %s and apikey of %s", maas_endpoint, args.maas_apikey, extra=LOG_DICT)

# Get a reference to self.
myself = client.users.whoami()
assert myself.is_admin, log.warning("the current user %s of the providing api key is not an admin", myself.username)

# Check for a MAAS server capability.
version = client.version.get()
assert "devices-management" in version.capabilities, log.warning("devices-management is not in the maas server's capabilities")

# Check the default OS and distro series for deployments.
log.info("the default OS of maas is %s", client.maas.get_default_os(), extra=LOG_DICT)
log.info("the default distro series for deployments is %s", client.maas.get_default_distro_series(), extra=LOG_DICT)

def maas_deploy_machine():
  if getattr(args, 'machinename', None) != None:
    machine = client.machines.allocate(hostname=args.machinename)
    log.info("allocate a machine with name of %s", args.machinename, extra=LOG_DICT)
  else:
    if DEFAULT_MACHINE_TAG not in args.machinetags:
      args.machinetags.append(DEFAULT_MACHINE_TAG)
    machine = client.machines.allocate(tags=args.machinetags)
    log.info("allocate a machine with tags of %s", repr(args.machinetags), extra=LOG_DICT)
  machine.deploy()
  log.info("deploying a machine with the name of %s", machine.hostname, extra=LOG_DICT)
  while machine.status == NodeStatus.DEPLOYING:
    machine.refresh()
    log.info("wating for the machine %s to be deployed", machine.hostname, extra=LOG_DICT)
    time.sleep(5)
  else:
    log.info("the deployment of the machine %s completes with the final status of %s", machine.hostname, machine.status_name, extra=LOG_DICT)

def maas_check_machine():
  out_format = "hostname: %s, systemid: %s, cpus: %d, status: %s, ipaddresses: %s"
  log.info("check the machine with the name of %s", args.machinename, extra=LOG_DICT)
  for machine in client.machines.list():
    if machine.hostname == args.machinename:
      print(out_format % (machine.hostname, machine.system_id, machine.cpus, machine.status_name, machine.ip_addresses))

def maas_release_machine():
  for machine in client.machines.list():
    if machine.hostname == args.machinename:
      log.info("release the machine with name of %s", args.machinename, extra=LOG_DICT)
      machine.release()

if __name__ == '__main__':

  if (getattr(args, 'deploy', None) != None):
    maas_deploy_machine()

  if (getattr(args, 'check', None) != None):
    maas_check_machine()

  if (getattr(args, 'release', None) != None):
    maas_release_machine()
