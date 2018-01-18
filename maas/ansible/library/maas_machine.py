#!/usr/bin/python3.5



ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'Xin Chen'
}

DOCUMENTATION = '''
---
module: maas_machine

short_description: deploy/release a machine via maas

version_added: "2.4"

description:
    - This module is used to deploy/release a machine via maas.
    - Tha maas tag awareness is supported.
    - The module will return the status of the machines involved.

requirements:
    - "python >= 3.5"
    - "python-libmaas >= 0.5.0"    
    
options:
    maas_url:
        description:
            - The url of the maas api server.
        required: true
    api_key:
        description:
            - The key for the authentication to use the maas api.
        required: true
    state:
        description:
            - Should the machine be present or absent.
        choices: [present, absent]
        default: present
    meta_data:
        description:
            - The meta_data for the deployed machine/machines used for recording info.
        default: None
    target_os:
        description:
            - The OS used to deploy the machine.
            - When this is omitted the default OS at maas server
        default: None
    wait:
        description:
            - If the module should wait for the machine to be deployed.
            - Note that the module always wait if the 'ensure' is 'yes' for any value of the 'wait' param
        required: false
        default: 'yes'
    wait_time:
        description:
            - The maximum time in seconds to wait for the machine's deployment.
            - Note that this is for deploying a machine one time.
            - The total waiting time when 'ensure' is 'yes' may up to wait_time * max_try
        required: false
        default: 1200
    wait_interval:
        description:
            - The interval between the checks of whether the machine's deployment succeeds.
        required: false
        default: 5
    ensure:
        description:
            - If the requested machine deployment must be fulfilled.
            - If so, the module will repeat deploying until succeed, and release the machine that fails to be deployed.            
        required: false
        default: 'yes'
    max_try:
        description:
            - The maximum times this module will try to deploy a machine when "ensure" is true.            
        required: false
        default: 5
    batch_deploy:
        description:
            - The number of the machines will be deployed in batch.            
        required: false
        default: 0
    disk_erase:
        description:
            - Whether erase the disk when releas a machine.            
        required: false
        default: 'no'
    target_name:
        description:
            - A new name for the deployed machine.           
        required: false
        default: None
    tags_match:
        description:
            - A list of tags to match the target machines of maas to be deployed or released.             
        required: false
        default: None
    zone_match:
        description:
            - A zone to match the target machines of maas to be deployed/released.             
        required: false
        default: None
    name_match:
        description:
            - The name of the exact machine to be deployed or released.
            - Any the host with the specified name cross zones may match if 'zone_match' is None            
        required: false
        default: None
    id_match:
        description:
            - The id of the exact machine to be released.
            - This param will hide the values specified by 'zone_match' and 'name_match'.
            - Note that this param is only used for release a machine.            
        required: false
        default: None


author:
    - Xin Chen
'''

EXAMPLES = '''
# Pass in the maas api server url and the api key for authentication.
# Deploy a single machine with a matching tag of "REMOTE-MGMT".
- name: deploy a single machine
  maas_machine:
    maas_url: http://maas.adp.gic.ericsson.se/MAAS/
    api_key: ....
    state: present
    tags_match:
    - REMOTE-MGMT
  register: deploy_result

# Release a single machine with a matching host id of "xa4fi".
- name: release a single machine
  maas_machine:
    maas_url: http://maas.adp.gic.ericsson.se/MAAS/
    api_key: ....
    state: absent
    id_match: xarfi

# Deploy a single machine with a matching tag of "REMOTE-MGMT".
# And record the group name of this machine by meta_data
- name: deploy a single machine and record some meta info
  maas_machine:
    maas_url: http://maas.adp.gic.ericsson.se/MAAS/
    api_key: ....
    state: present
    tags_match:
    - REMOTE-MGMT
    meta_data:
      group_name: group1
  register: deploy_result

# Deploy 3 machines with a matching zone of "ggn-420" in batch.
# Target OS of ubuntu will be used.
- name: deploy multiple machines in batch
  maas_machine:
    maas_url: http://maas.adp.gic.ericsson.se/MAAS/
    api_key: ....
    state: present
    batch_deploy: 3
    zone_match: ggn-420
    target_os: ubuntu
  register: batch_result
'''

RETURN = '''
host_name:
    description: The name of the target machine.
    type: str
host_id:
    description: The system id of the target machine in maas.
    type: str
zone_name:
    description: The name of zone the target machine is in.
    type: str
status:
    description: The status of the target machine.
    type: str
ip_addresses:
    description: The list of the ip addresses of the target machine.
    type: list
batch_machines:
    description: The result of the batch deploy.
    type: list
clean_machines:
    description: The list of the system ids of the machines that have to tried to be deployed and failed.
    type: list
meta_data:
    description: Recording the input meta_data.
    type: dict
'''

try:
    from maas.client import connect as maas_connect
    from maas.client.enum import NodeStatus
    from maas.client.errors import MAASException
    from maas.client.viscera.machines import MachineNotFound
    from maas.client.bones import CallError
    HAS_MAAS_LIB = True
except ImportError:
    HAS_MAAS_LIB = False


import time
from copy import deepcopy

from ansible.module_utils.basic import AnsibleModule

#### a handler class used to process the maas machine operations ####

class MaasMachineHandler(object):
    """
    A self-contained handler class used to process maas machine operations

    This class providing single machine deploying, batch machines deploying and
    single machine releasing.
    """

    # status definitions of the process result for single machine process
    # RESULT_ERROR, RESULT_COMPLETE, RESULT_TIMEOUT and RESULT_NO_MACHINE
    # are observable outside the class
    #   RESULT_COMPLETE:
    #       when a machine is successfully deployed if wait=True or ensure=True
    #       when a deploy is called without error if wait=False and
    #       ensure=False (no garantee to complete deployment)
    #       when a release action is called (no garantee to complete release)
    #   RESULT_TIMEOUT:
    #       when the last time of deploying timeout if wait=True or
    #       ensure=True (when wait=True and ensure=False, deploying is called only one time)
    #   RESULT_NO_MACHINE:
    #       when no machine is available at the last time of allocating
    #       this implies no concrete action is applied when ensure=False
    #   RESULT_ERROR:
    #       Any result except above ones
    RESULT_ERROR, RESULT_TIMEOUT, RESULT_COMPLETE, RESULT_ALLOC, RESULT_NO_MACHINE = \
    'error', 'timeout', 'complete', 'allocated', 'no available machine'

    ######### for batch #########
    # status definitions of the process result for batch machine process (only for the deployment)
    # All status are observable outside the class
    #   BATCH_RESULT_COMPLETE:
    #       all demanded machines are successfully deployed if wait=True or ensure=True
    #       when deployings of all demanded machine are called without error
    #       if wait=False and ensure=False (no garantee to complete deployment)
    #   RESULT_NO_MACHINE:
    #       when not enough machine for the demanded number are available
    #       at the last time of allocating
    #       this implies no concrete action is applied when ensure=False
    #   BATCH_RESULT_FAIL:
    #       Any result except above ones
    BATCH_RESULT_FAIL, BATCH_RESULT_COMPLETE, BATCH_RESULT_NO_MACHINE = \
    'batch deploy fail', 'batch deploy complete', \
    'not enough available machine for batch deploy'

    DEFAULT_WAIT_TIME = 600
    DEFAULT_MAX_TRY = 5
    DEFAULT_WAIT_INTERVAL = 5

    # a exception raised when timeout occurs
    class TimeoutException(Exception):
        """
        Exception raised when machine deploying timeout
        """
        pass

    # a exception raised when deploying fails in ensure deploy
    class DeployFail(Exception):
        """
        Exception raised when machine deploying failed
        """
        pass

    def __init__(self,
                 maas_url,
                 api_key,
                 target_os=None,
                 wait=True,
                 wait_time=DEFAULT_WAIT_TIME,
                 wait_interval=DEFAULT_WAIT_INTERVAL,
                 ensure=True,
                 max_try=DEFAULT_MAX_TRY,
                 # for batch, the number of batch deploying,
                 # only the zone and the tags will be matched
                 batch_deploy=0,
                 disk_erase=False,
                 target_name=None,
                 tags_match=None,
                 zone_match=None,
                 name_match=None,
                 id_match=None,
                 log=None):

        self.maas_url = maas_url
        self.api_key = api_key
        self.target_os = target_os
        self.wait = wait
        self.wait_time = wait_time
        self.wait_interval = wait_interval
        self.ensure = ensure
        self.max_try = max_try
        self.batch_deploy = batch_deploy ### for batch ###
        self.disk_erase = disk_erase
        self.target_name = target_name
        self.tags_match = tags_match
        self.zone_match = zone_match
        self.name_match = name_match
        self.id_match = id_match
        self.log = log
        
        self.client = None

        # store the current result with a structure as
        # status:
        # error_msg:
        # machine: an object of a machine
        self._result = dict(status=None,
                            error_msg=None,
                            machine=None)

        ######### for batch ############
        # store the current result for batch deploying with a structure as
        # status:
        # error_msg:
        # machines: a dict of the invovled machines with the key as
        # the machine's system id and value of the object of maas machine
        self._batch_result = dict(status=None,
                                  error_msg=None,
                                  machines=dict())

        # store the id of the machines needed to be released
        # when error, timeout or complete
        self._clean_machines = []

    # get the current result
    def get_result(self):
        """
        Get the process result when deploying a single machine or
        releasing a single machine
        """
        return self._result

    # clear the current result
    def clear_result(self):
        """
        Clear the process result of single machine operations
        """
        self._result['status'] = None
        self._result['error_msg'] = None
        self._result['machine'] = None

    ###### for batch #######
    # get the current batch deploy result
    def get_batch_result(self):
        """
        Get the process result when deploying machines in batch
        """
        return self._batch_result

    # clear the current batch deploy result,
    # only the status and the error message will be cleared
    def clear_batch_result(self):
        """
        Clear the process result of batch deploying.
        Note that only the 'status' and 'error_msg' will be cleared.
        """
        self._batch_result['status'] = None
        self._batch_result['error_msg'] = None

    # get the current clean machines
    def get_clean_machines(self):
        """
        Get the machines need to be released after machine/machines deploying.
        These machines come from the deploying failures during deployment.
        """
        return self._clean_machines

    # release the machines in the clean group
    # def release_clean_machines(self, erase: bool=False):
    def release_clean_machines(self, erase=False):
        """
        Release the machines need to be released after machine/machines deploying.

        :param erase: Indicate whether erase the disk when release the machines.
        """
        for i in self._clean_machines:
            try:
                machine = self.client.machines.get(i)
                machine.release(erase=erase)
            except CallError as err:
                msg = "maas call error \'" + \
                      str(err).replace('{', '{{').replace('}', '}}') + \
                      "\' occurs when clean the machine \'{}\'".format(machine.hostname)
                self._error_print(msg)
            except MAASException as err:
                self._error_print("maas error \'{}\' occurs when clean the machine \'{}\'",
                                  err, machine.hostname)
            except Exception as err:
                self._error_print("error \'{}\' occurs when clean the machine \'{}\'",
                                  err, machine.hostname)
        self._clean_machines.clear()

    # called when an error occurs
    def _handle_error(self, *args, **kwargs):
        error_msg = kwargs.setdefault('error_msg', 'unknown error occurs')
        kwargs.pop('error_msg')
        self._error_print(error_msg, *args, **kwargs)
        self._result['status'] = self.RESULT_ERROR
        self._result['error_msg'] = error_msg

    def _add_machine_to_result(self, machine):
        self._result['machine'] = machine

    # called when timeout occurs
    def _handle_timeout(self, *args, **kwargs):
        msg = kwargs.setdefault('msg', 'timeout occurs')
        kwargs.pop('msg')
        self._info_print(msg, *args, **kwargs)
        self._result['status'] = self.RESULT_TIMEOUT
        self._result['error_msg'] = msg

    # called when complete
    def _handle_complete(self, *args, **kwargs):
        msg = kwargs.setdefault('msg', 'process complete')
        kwargs.pop('msg')
        self._info_print(msg, *args, **kwargs)
        self._result['status'] = self.RESULT_COMPLETE

    # called when machine is allocated
    def _handle_alloc(self, machine, *args, **kwargs):
        msg = kwargs.setdefault('msg', 'allocate complete')
        kwargs.pop('msg')
        self._info_print(msg, *args, **kwargs)
        self._result['status'] = self.RESULT_ALLOC
        self._add_machine_to_result(machine)

    # called when not enough machine to be allocated
    def _handle_no_machine(self, *args, **kwargs):
        msg = kwargs.setdefault('msg', 'not enough machine')
        kwargs.pop('msg')
        self._error_print(msg, *args, **kwargs)
        self._result['status'] = self.RESULT_NO_MACHINE
        self._result['error_msg'] = msg


    ####### for batch #######
    # called when a batch fail occurs
    def _handle_batch_fail(self, *args, **kwargs):
        error_msg = kwargs.setdefault('error_msg',
                                      'unknown error occurs for batch deploy')
        kwargs.pop('error_msg')
        self._error_print(error_msg, *args, **kwargs)
        self._batch_result['status'] = self.BATCH_RESULT_FAIL
        self._batch_result['error_msg'] = error_msg

    # called when batch deploy complete
    def _handle_batch_complete(self, *args, **kwargs):
        msg = kwargs.setdefault('msg', 'batch deploy complete')
        kwargs.pop('msg')
        self._info_print(msg, *args, **kwargs)
        self._batch_result['status'] = self.BATCH_RESULT_COMPLETE

    # called when not enough machine to be allocated for batch deploy
    def _handle_batch_no_machine(self, *args, **kwargs):
        msg = kwargs.setdefault('msg', 'not enough machine for batch deploy')
        kwargs.pop('msg')
        self._error_print(msg, *args, **kwargs)
        self._batch_result['status'] = self.BATCH_RESULT_NO_MACHINE
        self._batch_result['error_msg'] = msg

    # connect to the maas api server with the api key
    def api_connect(self):
        """
        Connect to the MAAS API Server with the input parameters.
        """
        try:
            self.client = maas_connect(self.maas_url, apikey=self.api_key)
            if not self.client.users.whoami().is_admin:
                if self.batch_deploy > 0:
                    self._handle_batch_fail(error_msg="the current user is not an admin")
                else:
                    self._handle_error(error_msg="the current user is not an admin")
        except CallError as err:
            msg = "maas call error \'" + \
                  str(err).replace('{', '{{').replace('}', '}}') + \
                  "\' occurs when connect to the maas api server"
            if self.batch_deploy > 0:
                self._handle_batch_fail(error_msg=msg)
            else:
                self._handle_error(error_msg=msg)
        except MAASException as err:
            msg = "maas error \'{}\' occurs when connect to the maas api server".format(err)
            if self.batch_deploy > 0:
                self._handle_batch_fail(error_msg=msg)
            else:
                self._handle_error(error_msg=msg)
        # except Exception as err:
            # msg = "error \'{}\' occurs when connect to the maas api server".format(err)
            # if self.batch_deploy > 0:
                # self._handle_batch_fail(error_msg=msg)
            # else:
                # self._handle_error(error_msg=msg)
        else:
            self._info_print("connected to the maas api server")

    # a private func to allocate a machine according to the input params
    # allocation is executed only when no error in current result
    def _allocate_machine(self):
        if not self._result['status'] == self.RESULT_ERROR:
            try:
                m_a = self.client.machines.allocate(hostname=self.name_match,
                                                    tags=self.tags_match,
                                                    zone=self.zone_match)
                if not m_a.status == NodeStatus.ALLOCATED:
                    raise Exception("fail to allocate machine")
                msg = "allocate the machine with: \nname: {}, tags: {}, zone: {}".format(
                    m_a.hostname,
                    repr(m_a.tags),
                    m_a.zone.name)
                self._handle_alloc(m_a, msg=msg)
            except CallError as err:
                msg = "maas call error \'" + \
                    str(err).replace('{', '{{').replace('}', '}}') + \
                    "\' occurs when allocate the machine with: " + \
                    "\nname: {}, tags: {}, zone: {}".format(
                        self.name_match, repr(self.tags_match), self.zone_match)
                self._handle_error(error_msg=msg)
            except MAASException as err:
                msg = "maas error \'{}\' occurs when allocate the machine with: " + \
                    "\nname: {}, tags: {}, zone: {}"
                msg = msg.format(err, self.name_match, repr(self.tags_match), self.zone_match)
                self._handle_error(error_msg=msg)
            except MachineNotFound as err:
                msg = "maas error \'{}\' occurs when allocate the machine with: " + \
                    "\nname: {}, tags: {}, zone: {}"
                msg = msg.format(err, self.name_match, repr(self.tags_match), self.zone_match)
                self._handle_no_machine(msg=msg)
            # except Exception as err:
                # msg = "error \'{}\' occurs when allocate the machine with: " + \
                    # "\nname: {}, tags: {}, zone: {}"
                # msg = msg.format(err, self.name_match, repr(self.tags_match), self.zone_match)
                # self._handle_error(error_msg=msg)


    # a private func to deploy a machine according to the input params
    # deployment is called only when the current result's status is self.RESULT_ALLOC
    def _deploy_machine(self):
        if self._result['status'] == self.RESULT_ALLOC:
            try:
                self._result['machine'].deploy(distro_series=self.target_os)
                self._result['machine'].refresh()
                if self.wait or self.ensure:
                    wait_count = 0
                    while self._result['machine'].status == NodeStatus.DEPLOYING and \
                        wait_count < self.wait_time:
                        self._result['machine'].refresh()
                        # self._info_print("wait for deploying machine with: " + \
                                           # "\nname: {}, tags: {}, zone: {}, " + \
                                           # "status: {} \ntime passed: {} seconds",
                                           # self._result['machine'].hostname,
                                           # repr(self._result['machine'].tags),
                                           # self._result['machine'].zone.name,
                                           # self._result['machine'].status_name,
                                           # wait_count)
                        time.sleep(self.wait_interval)
                        wait_count = wait_count + self.wait_interval
                    if not self._result['machine'].status == NodeStatus.DEPLOYED:
                        if wait_count >= self.wait_time:
                            raise self.TimeoutException
                        else:
                            raise self.DeployFail
                # self._info_print("end the deployment of machine with: " + \
                                   # "\nname: {}, tags: {}, zone: {}, status: {}",
                                   # self._result['machine'].hostname,
                                   # repr(self._result['machine'].tags),
                                   # self._result['machine'].zone.name,
                                   # self._result['machine'].status_name)
            except CallError as err:
                self._result['machine'].refresh()
                msg = "maas call error \'" + \
                    str(err).replace('{', '{{').replace('}', '}}') + \
                    "\' occurs when deploy the machine with: " + \
                    "\nname: {}, tags: {}, zone: {}, status: {}".format(
                        self._result['machine'].hostname,
                        repr(self._result['machine'].tags),
                        self._result['machine'].zone.name,
                        self._result['machine'].status_name)
            except MAASException as err:
                self._result['machine'].refresh()
                msg = "maas error \'{}\' occurs when deploy the machine with: " + \
                    "\nname: {}, tags: {}, zone: {}, status: {}"
                msg = format(err, self._result['machine'].hostname,
                             repr(self._result['machine'].tags),
                             self._result['machine'].zone.name,
                             self._result['machine'].status_name)
                self._handle_error(error_msg=msg)
            except self.TimeoutException:
                msg = "timeout occurs when deploy the machine with: " + \
                    "\nname: {}, tags: {}, zone: {}, status: {}".format(
                        self._result['machine'].hostname,
                        repr(self._result['machine'].tags),
                        self._result['machine'].zone.name,
                        self._result['machine'].status_name)
                self._handle_timeout(msg=msg)
            except self.DeployFail:
                msg = "Fail to deploy the machine with: " + \
                    "\nname: {}, tags: {}, zone: {}, status: {}".format(
                        self._result['machine'].hostname,
                        repr(self._result['machine'].tags),
                        self._result['machine'].zone.name,
                        self._result['machine'].status_name)
                self._handle_error(error_msg=msg)
            # except Exception as err:
                # self._result['machine'].refresh()
                # msg = "error \'{}\' occurs when deploy the machine with: " +\
                    # "\nname: {}, tags: {}, zone: {}, status: {}"
                # msg = msg.format(err, self._result['machine'].hostname,
                                 # repr(self._result['machine'].tags),
                                 # self._result['machine'].zone.name,
                                 # self._result['machine'].status_name)
                # self._handle_error(error_msg=msg)

    # called when ensure is true that repeats machine deployment until succeed
    # machines that failed to be deployed or encounter the timeout will be
    # added to the _clean_machines
    def _ensure_deploy_machine(self):
        try_count = 0
        flags = [self.RESULT_COMPLETE, self.RESULT_NO_MACHINE]
        while self._result['status'] not in flags and try_count < self.max_try:
            try:
                self._allocate_machine()
                if self._result['status'] == self.RESULT_NO_MACHINE:
                    raise MachineNotFound
                if not self._result['status'] == self.RESULT_ALLOC:
                    raise self.DeployFail("machine allocation fails")

                self._deploy_machine()
                if self._result['status'] == self.RESULT_TIMEOUT:
                    raise self.DeployFail("machine deployment fails due to timeout")
                if self._result['machine']:
                    self._result['machine'].refresh()
                    if self._result['machine'].status == NodeStatus.DEPLOYED:
                        msg = "complete the process of deploying the machine with: " + \
                            "\nname: {}, tags: {}, zone: {}, status: {}".format(
                                self._result['machine'].hostname,
                                repr(self._result['machine'].tags),
                                self._result['machine'].zone.name,
                                self._result['machine'].status_name)
                        self._handle_complete(msg=msg)
                    else:
                        raise self.DeployFail("machine deployment fails")
                else:
                    raise self.DeployFail("machine deployment fails")

            except MachineNotFound:
                msg = "no available machine for allocating the machine with: " + \
                    "\nname: {}, tags: {}, zone: {}".format(
                        self.name_match,
                        repr(self.tags_match),
                        self.zone_match)
                self._handle_no_machine(msg=msg)
            except self.DeployFail as err:
                try_count = try_count + 1
                msg = "error \'{}\' occurs when tring to deploy the machine with: " + \
                    "\nname: {}, tags: {}, zone: {} \ntry times: {}, try another one"
                msg = msg.format(err, self.name_match, repr(self.tags_match),
                                 self.zone_match, try_count)
                # self._info_print(msg)
                if self._result['machine']:
                    m_id = self._result['machine'].system_id
                    if m_id not in self._clean_machines:
                        self._clean_machines.append(m_id)
                if try_count < self.max_try:
                    self.clear_result()

    # a public func to deploy a machine according to the input params
    def deploy_machine(self):
        """
        Deploy a single machine according to the input parameters.
        """
        if not self.ensure:
            self._allocate_machine()
            self._deploy_machine()
            if self._result['status'] == self.RESULT_ALLOC:
                msg = "complete the process of deploying the machine with: " + \
                    "\nname: {}, tags: {}, zone: {}, status: {}".format(
                        self._result['machine'].hostname,
                        repr(self._result['machine'].tags),
                        self._result['machine'].zone.name,
                        self._result['machine'].status_name)
                self._handle_complete(msg=msg)
        else:
            self._ensure_deploy_machine()

    ########## for batch ########

    # a private func to batch deploy machine without ensure
    # note that if an allocation/deploy-calling failure occurs for any machine,
    # the entire batch deploy will fail with an empty machines dict returned in the result
    def _batch_deploy(self):
        # allocate machines for batch deployment
        for _ in range(0, self.batch_deploy):
            try:
                m_a = self.client.machines.allocate(tags=self.tags_match,
                                                    zone=self.zone_match)
                if not m_a.status == NodeStatus.ALLOCATED:
                    if m_a.system_id not in self._clean_machines:
                        self._clean_machines.append(m_a.system_id)
                    raise Exception("allocationg of the machine with name: " + \
                                    "\'{}\' zone: \'{}\' id: \'{}\' failed for batch deploy".format(
                                        m_a.hostname, m_a.zone.name, m_a.system_id))
                self._batch_result['machines'][m_a.system_id] = m_a
                # self._info_print("allocate machine for batch deploy with: " + \
                #                  "\nname: \'{}\' zone: \'{}\' id: \'{}\'",
                #                  m_a.hostname, m_a.zone.name, m_a.system_id)
            except CallError as err:
                msg = "maas call error \'" + \
                    str(err).replace('{', '{{').replace('}', '}}') + \
                    "\' occurs when allocate the machine for batch deploy with: " + \
                    "\ntags: {}, zone: {}".format(repr(self.tags_match), self.zone_match)
                self._handle_batch_fail(error_msg=msg)
                break
            except MAASException as err:
                msg = "maas error \'{}\' occurs when allocate the machine for " + \
                    "batch deploy with: \ntags: {}, zone: {}"
                msg = msg.format(err, repr(self.tags_match), self.zone_match)
                self._handle_batch_fail(error_msg=msg)
                break
            except MachineNotFound as err:
                msg = "maas error \'{}\' occurs when allocate the machine for " + \
                    "batch deploy with: \ntags: {}, zone: {}"
                msg = msg.format(err, repr(self.tags_match), self.zone_match)
                self._handle_batch_no_machine(msg=msg)
                break
            # except Exception as err:
                # msg = "error \'{}\' occurs when allocate the machine for " + \
                    # "batch deploy with: \ntags: {}, zone: {}"
                # msg = msg.format(err, repr(self.tags_match), self.zone_match)
                # self._handle_batch_fail(error_msg=msg)
                # break
        if len(self._batch_result['machines']) < self.batch_deploy:
            _ = [self._clean_machines.append(k) for k in self._batch_result['machines'] \
                                            if k not in self._clean_machines]
            self._batch_result['machines'].clear()
            return

        # deploy the allocated machines
        deploy_fail_machine_id = None
        for k, val in self._batch_result['machines'].items():
            try:
                val.deploy(distro_series=self.target_os)
            except CallError as err:
                msg = "maas call error \'" + \
                    str(err).replace('{', '{{').replace('}', '}}') + \
                    "\' occurs when allocate the machine for " + \
                    " batch deploy with: \ntags: {}, zone: {}".format(
                        repr(self.tags_match), self.zone_match)
                self._handle_batch_fail(error_msg=msg)
                deploy_fail_machine_id = k
                break
            except MAASException as err:
                msg = "maas error \'{}\' occurs when allocate the machine for " + \
                    "batch deploy with: \ntags: {}, zone: {}"
                msg = msg.format(err, repr(self.tags_match), self.zone_match)
                self._handle_batch_fail(error_msg=msg)
                deploy_fail_machine_id = k
                break
            # except Exception as err:
                # msg = "error \'{}\' occurs when allocate the machine for " + \
                    # "batch deploy with: \ntags: {}, zone: {}"
                # msg = msg.format(err, repr(self.tags_match), self.zone_match)
                # self._handle_batch_fail(error_msg=msg)
                # deploy_fail_machine_id = k
                # break
        if deploy_fail_machine_id:
            _ = [self._clean_machines.append(k) for k in self._batch_result['machines'] \
                                            if k not in self._clean_machines]
            self._batch_result['machines'].clear()
            return

        # repeatly check all the machines' status if wait=true
        if self.wait:
            wait_count = 0
            fail_flag = False
            complete_flag = False
            while (not fail_flag) and \
                  (not complete_flag) and \
                  (wait_count < self.wait_time):
                # self._info_print("wait for deploying machines for " + \
                #                  " batch deploy with: tags: {}, zone: {} " + \
                #                  "\ndeploying: {} \ntime passed: {} seconds",
                #                  repr(self.tags_match), self.zone_match,
                #                  repr(self._batch_result['machines']), wait_count)
                complete_flag = True
                for k, val in self._batch_result['machines'].items():
                    try:
                        val.refresh()
                        if val.status == NodeStatus.DEPLOYED:
                            pass
                        elif val.status == NodeStatus.DEPLOYING:
                            complete_flag = False
                        else:
                            raise Exception("deploying of the machine with name: " + \
                                            "\'{}\' zone: \'{}\' id: \'{}\' ".format(
                                                val.hostname, val.zone.name, val.system_id) + \
                                                "failed for batch deploy")
                    except CallError as err:
                        msg = "maas call error \'" + \
                            str(err).replace('{', '{{').replace('}', '}}') + \
                            "\' occurs when deploy the machine for batch " + \
                            "deploy with: \ntags: {}, zone: {}".format(
                                repr(self.tags_match), self.zone_match)
                        self._handle_batch_fail(error_msg=msg)
                        fail_flag = True
                        break
                    except MAASException as err:
                        msg = "maas error \'{}\' occurs when deploy the machine for " + \
                            "batch deploy with: \ntags: {}, zone: {}"
                        msg = msg.format(err, repr(self.tags_match), self.zone_match)
                        self._handle_batch_fail(error_msg=msg)
                        fail_flag = True
                        break
                    # except Exception as err:
                        # msg = "error \'{}\' occurs when deploy the machine for " + \
                            # "batch deploy with: \ntags: {}, zone: {}"
                        # msg = msg.format(err, repr(self.tags_match), self.zone_match)
                        # self._handle_batch_fail(error_msg=msg)
                        # fail_flag = True
                        # break
                time.sleep(self.wait_interval)
                wait_count = wait_count + self.wait_interval
            if complete_flag:
                msg = "complete deploying machines for " + \
                    "batch deploy with: tags: {}, zone: {}".format(
                        repr(self.tags_match), self.zone_match)
                self._handle_batch_complete(msg=msg)
                return
            if wait_count >= self.wait_time:
                msg = "timeout occurs when deploying machines for " + \
                    "batch deploy with: tags: {}, zone: {}".format(
                        repr(self.tags_match), self.zone_match)
                self._handle_batch_fail(error_msg=msg)
            _ = [self._clean_machines.append(k) for k in self._batch_result['machines'] \
                                            if k not in self._clean_machines]
            self._batch_result['machines'].clear()
            return

        msg = "end deploying machines for " + \
            "batch deploy with: tags: {}, zone: {}".format(
                repr(self.tags_match), self.zone_match)
        self._handle_batch_complete(msg=msg)


    # a private func to batch deploy machine with ensure
    # this process fails only when there is no available machines for deploying any more
    # or the maximal time allowed to try is reached
    # and if fails, not a single machine will be returned
    def _ensure_batch_deploy(self):
        on_process = dict() # item in on_process:
                            # 'system_id': {'count': x, 'machine': machine object}
        stop_flag = False
        to_result, kick_off = [], []
        try_allow = self.batch_deploy + self.max_try
        while not stop_flag:
            # self._info_print("wait for deploying machines for batch deploy with: " + \
            #                  "tags: {}, zone: {} \non process: {} \ndeployed: {}",
            #                  repr(self.tags_match), self.zone_match, repr(on_process),
            #                  repr(list(self._batch_result['machines'].keys())))
            gap_number = self.batch_deploy - len(self._batch_result['machines']) - len(on_process)
            try_allow = try_allow - gap_number
            if try_allow < 0:
                _ = [self._clean_machines.append(k) for k in on_process \
                                                if k not in self._clean_machines]
                _ = [self._clean_machines.append(k) for k in self._batch_result['machines'] \
                                                if k not in self._clean_machines]
                on_process.clear()
                self._batch_result['machines'].clear()
                msg = "maximal trying time is reached when deploy machines " + \
                    "for batch deploy with: \ntags: {}, zone: {}".format(
                        repr(self.tags_match), self.zone_match)
                self._handle_batch_fail(error_msg=msg)
                break
            for _ in range(0, gap_number):
                a_m = None
                # try to deploy a machine
                try:
                    a_m = self.client.machines.allocate(tags=self.tags_match,
                                                        zone=self.zone_match)
                    if not a_m.status == NodeStatus.ALLOCATED:
                        raise Exception
                    a_m.deploy(distro_series=self.target_os)
                    on_process.setdefault(a_m.system_id, dict(count=self.wait_time, machine=a_m))
                except MachineNotFound as err:
                    msg = "maas error \'{}\' occurs when allocate the machine for " + \
                        "batch deploy with: \ntags: {}, zone: {}"
                    msg = msg.format(err, repr(self.tags_match), self.zone_match)
                    self._handle_batch_no_machine(msg=msg)
                    _ = [self._clean_machines.append(k) for k in on_process \
                                                    if k not in self._clean_machines]
                    _ = [self._clean_machines.append(k) for k in self._batch_result['machines'] \
                                                    if k not in self._clean_machines]
                    self._batch_result['machines'].clear()
                    stop_flag = True
                    break
                except Exception:
                    if a_m and (a_m.system_id not in self._clean_machines):
                        self._clean_machines.append(a_m.system_id)

            # check the status of the machines on processing
            for k, val in on_process.items():
                try:
                    m_p = val['machine']
                    m_p.refresh()
                    val['count'] = val['count'] - self.wait_interval
                    if m_p.status == NodeStatus.DEPLOYED:
                        to_result.append(k)
                    elif (not m_p.status == NodeStatus.DEPLOYING) or \
                         (val['count'] <= 0):
                        kick_off.append(k)
                    else:
                        pass
                except Exception:
                    kick_off.append(k)

            # check whether continue the loop
            for k in to_result:
                m_p = on_process.pop(k)['machine']
                self._batch_result['machines'].setdefault(k, m_p)
            for k in kick_off:
                on_process.pop(k)
                if k not in self._clean_machines:
                    self._clean_machines.append(k)
            to_result.clear()
            kick_off.clear()
            if self.batch_deploy == len(self._batch_result['machines']):
                msg = "complete deploying machines for batch deploy with: " + \
                    "tags: {}, zone: {} \non process: {} \ndeployed: {}".format(
                        repr(self.tags_match), self.zone_match,
                        repr(list(on_process.keys())),
                        repr(list(self._batch_result['machines'].keys())))
                self._handle_batch_complete(msg=msg)
                stop_flag = True
            time.sleep(self.wait_interval)

    # a public func to batch deploy machines
    def batch_deploy_machines(self):
        """
        Deploy multiple machines in batch.
        """
        if self.ensure:
            self._ensure_batch_deploy()
        else:
            self._batch_deploy()


    # a private func to release a machine specified by the name of the machine
    def _release_machine(self, name, zone, m_id):
        m_found = False
        func = lambda m: m.release(erase=self.disk_erase)
        try:
            if m_id:
                m_r = self.client.machines.get(system_id=m_id)
                if m_r:
                    m_found = True
                    func(m_r)
                    # self._info_print("release the machine with a id of " + \
                    #                  "\'{}\' and a name of \'{}\' in zone of \'{}\'",
                    #                  m_id, m_r.hostname, m_r.zone.name)
            elif zone:
                for m_r in self.client.machines.list():
                    if m_r.hostname == name and m_r.zone.name == zone:
                        m_found = True
                        func(m_r)
                        # self._info_print("release the machine with " + \
                        #                  "a name of \'{}\' in zone of \'{}\'", name, zone)
            else:
                for m_r in self.client.machines.list():
                    if m_r.hostname == name:
                        m_found = True
                        func(m_r)
                        # self._info_print("release the machine with a name of " + \
                        #                  "\'{}\' in zone of \'{}\'", name, m_r.zone.name)
            if not m_found:
                raise Exception("no such machine is found")
        except CallError as err:
            if m_id:
                msg = "maas call error \'" + \
                    str(err).replace('{', '{{').replace('}', '}}') + \
                    "\' occurs when release the machine with id \'{}\'".format(id)
            elif zone:
                msg = "maas call error \'" + \
                str(err).replace('{', '{{').replace('}', '}}') + \
                "\' occurs when release the machine \'{}\' in zone \'{}\'".format(name, zone)
            else:
                msg = "maas call error \'" + \
                str(err).replace('{', '{{').replace('}', '}}') + \
                "\' occurs when release the machine \'{}\'".format(name)
            self._handle_error(error_msg=msg)
        except MAASException as err:
            if m_id:
                msg = "maas error \'{}\' occurs when release " + \
                    "the machine with id \'{}\'"
                msg = msg.format(err, m_id)
            elif zone:
                msg = "maas error \'{}\' occurs when release " + \
                    "the machine \'{}\' in zone \'{}\'"
                msg = msg.format(err, name, zone)
            else:
                msg = "maas error \'{}\' occurs when release " + \
                    "the machine \'{}\'"
                msg = msg.format(err, name)
            self._handle_error(error_msg=msg)
        except Exception as err:
            if m_id:
                msg = "error \'{}\' occurs when release " + \
                    "the machine with id \'{}\'"
                msg = msg.format(err, m_id)
            elif zone:
                msg = "error \'{}\' occurs when release " + \
                    "the machine \'{}\' in zone \'{}\'"
                msg = msg.format(err, name, zone)
            else:
                msg = "error \'{}\' occurs when release " + \
                    "the machine \'{}\'"
                msg = msg.format(err, name)
            self._handle_error(error_msg=msg)

    # a public func to release a machine specified by the name of the machine
    def release_machine(self):
        """
        Release a single machine according to the input parameters.
        """
        if not (self.name_match or self.id_match):
            msg = "error occurs due to that the name or the system " + \
                "id of the released machine must be specified"
            self._handle_error(error_msg=msg)
        else:
            self._release_machine(self.name_match, self.zone_match, self.id_match)
            if not self._result['status'] == self.RESULT_ERROR:
                self._result['status'] = self.RESULT_COMPLETE

    # a printer wrapper for normal messages
    def _info_print(self, msg, *args, **kwargs):
        if self.log:
            self.log.info(msg.format(*args) + '\n', **kwargs)
        else:
            print(msg.format(*args, **kwargs) + '\n')

    # a printer wrapper for error messages
    def _error_print(self, msg, *args, **kwargs):
        if self.log:
            self.log.error(msg.format(*args) + '\n', **kwargs)
        else:
            print(msg.format(*args, **kwargs) + '\n')

#### a handler class used to process the maas machine operations ####

WAIT_TIME = 1200
WAIT_INTERVAL = 5
MAX_TRY = 5

def validate_params(params, error_handler, warn_handler):
    """
    Validate the input parameters for this module.

    :param params: The input parameters for this module.
    :param error_handler: The error handling method of the ansible module.
    :param warn_handler: The warning method of the ansible module.
    """
    # validate the input params
    # present_ex_par = ('target_os', 'wait', 'wait_time', 'wait_interval',
                      # 'ensure', 'max_try', 'batch_deploy', 'target_name',
                      # 'tags_match')
    # absent_ex_par = ('disk_erase', 'id_match')
    actual_input = set([k for k, v in params.items() if v])
    if params['state'] == 'present':
        if params['disk_erase'] or params['id_match']:
            error_handler(msg="params 'disk_erase' and " + \
                          "'id_match' can only be used for 'state'='absent'")
        if params['target_os']:
            if params['target_os'] not in ['centos', 'ubuntu']:
                error_handler(msg="param 'target_os' must be eigher 'centos' or 'ubuntu'")
    if len(set(('name_match', 'zone_match')).intersection(actual_input)) == 1:
        error_handler(msg="params 'name_match' and 'zone_match' must be used together")
    if params['state'] == 'absent':
        # if len(set(present_ex_par).intersection(actual_input)) > 0:
            # error_handler(msg="params {} ".format(repr(present_ex_par)) + \
            #                  "can only be used for 'state'='present')
        if 'id_match' in actual_input:
            warn_handler("'id_match' is applied, the 'name_match' " + \
                         "and 'zone_match' will be ignored'")

def run_module():
    """
    Run this ansible module.
    """
    # define the available arguments/parameters that a user can pass to
    # the module
    module_args = dict(
        maas_url=dict(type='str', required=True),
        api_key=dict(type='str', required=True),
        state=dict(choices=['absent', 'present'], default='present'),
        meta_data=dict(type='dict', default=None),
        target_os=dict(type='str', default=None),
        wait=dict(type='bool', default=True),
        wait_time=dict(type='int', default=WAIT_TIME),
        wait_interval=dict(type='int', default=WAIT_INTERVAL),
        ensure=dict(type='bool', default=True),
        max_try=dict(type='int', default=MAX_TRY),
        batch_deploy=dict(type='int', default=0),
        disk_erase=dict(type='bool', default=False),
        target_name=dict(type='str', default=None),
        tags_match=dict(type='list', default=None),
        zone_match=dict(type='str', default=None),
        name_match=dict(type='str', default=None),
        id_match=dict(type='str', default=None)
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        host_name=None,
        host_id=None,
        zone_name=None,
        status=None,
        ip_addresses=[],
        batch_machines=[],
        clean_machines=[],
        meta_data={}
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # the current version dosen't support check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )

    if not HAS_MAAS_LIB:
        module.fail_json(msg='python_libmaas is required for this module')

    validate_params(module.params, module.fail_json, module.warn)

    handler_args = deepcopy(module.params)
    handler_args.pop('state')
    handler_args.pop('meta_data')
    maas_handler = MaasMachineHandler(**handler_args)
    handler_batch_result = maas_handler.get_batch_result()
    handler_result = maas_handler.get_result()

    maas_handler.api_connect()
    if handler_result['error_msg']:
        module.fail_json(msg=handler_result['error_msg'])
    if handler_batch_result['error_msg']:
        module.fail_json(msg=handler_batch_result['error_msg'])

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    # if module.check_mode:
        # return result

    ###### deploy a single machine ######
    if module.params['state'] == 'present' and \
       module.params['batch_deploy'] == 0:
        maas_handler.deploy_machine()
        result['clean_machines'] = maas_handler.get_clean_machines()
        result['changed'] = True
        result.pop('batch_machines')
        if handler_result['status'] == MaasMachineHandler.RESULT_COMPLETE:
            m_r = handler_result['machine']
            result['host_name'], result['host_id'], result['zone_name'], \
            result['status'], result['ip_addresses'] = \
            m_r.hostname, m_r.system_id, m_r.zone.name, m_r.status_name, m_r.ip_addresses
            if module.params['meta_data']:
                result['meta_data'] = module.params['meta_data']
            module.exit_json(msg='a machine is deployed', **result)
        else:
            if not (handler_result['machine'] or len(result['clean_machines'])):
                result['changed'] = False
            module.fail_json(msg=handler_result['error_msg'])
    ###### deploy machines in batch ######
    elif module.params['state'] == 'present':
        maas_handler.batch_deploy_machines()
        result['clean_machines'] = maas_handler.get_clean_machines()
        result['changed'] = True
        if handler_batch_result['status'] == MaasMachineHandler.BATCH_RESULT_COMPLETE:
            for m_r in handler_batch_result['machines'].values():
                result['batch_machines'].append(dict(host_name=m_r.hostname,
                                                     host_id=m_r.system_id,
                                                     zone_name=m_r.zone.name,
                                                     status=m_r.status_name,
                                                     ip_addresses=m_r.ip_addresses))

            if module.params['meta_data']:
                result['meta_data'] = module.params['meta_data']
            module.exit_json(msg='%d machines are deployed' % module.params['batch_deploy'],
                             batch_machines=result['batch_machines'],
                             clean_machines=result['clean_machines'],
                             meta_data=result['meta_data'],
                             changed=True)
        else:
            if not (len(handler_batch_result['machines']) or len(result['clean_machines'])):
                result['changed'] = False
            module.fail_json(msg=handler_batch_result['error_msg'])
    ###### release a single machine ######
    else:
        maas_handler.release_machine()
        result['changed'] = True
        if handler_result['status'] == MaasMachineHandler.RESULT_COMPLETE:
            module.exit_json(msg='release the machine')
        else:
            result['changed'] = False
            module.fail_json(msg=handler_result['error_msg'])

def main():
    '''
    Main entry of the module
    '''
    run_module()

if __name__ == '__main__':
    main()
