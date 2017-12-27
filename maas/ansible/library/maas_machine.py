#!/usr/bin/env python3.5

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
    - "python-libmaas"    
    
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
    os:
        description:
            - The OS used to deploy the machine.
            - When this is omitted the default OS at maas server
        default: None
    wait:
        description:
            - If the module should wait for the machine to be deployed.
        required: false
        default: 'yes'
    wait_time:
        description:
            - The maximam time in seconds to wait for the machine's deployment.
        required: false
        default: 300
    ensure:
        description:
            - If the requested machine deployment must be fulfilled.
            - If so, the module will repeat deploying until succeed, and release the machine that fails to be deployed.            
        required: false
        default: 'yes'
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
        default: 'default'
    name_match:
        description:
            - The name of the exact machine to be deployed or released.             
        required: false
        default: None


author:
    - Xin Chen
'''

EXAMPLES = '''
# Pass in the maas api server url and the api key for authentication.
# Deploy a machine with a matching tag of "REMOTE-MGMT".
- name: deploy a test machine
  maas_machine:
    maas_url: http://maas.adp.gic.ericsson.se/MAAS/
    api_key: ....
    state: present
    tags_match:
    - REMOTE-MGMT
    
# Release a machine with a matching name of "chief-earwig".
- name: release a test machine
  maas_machine:
    maas_url: http://maas.adp.gic.ericsson.se/MAAS/
    api_key: ....
    state: absent
    name_match: chief-earwig
'''

RETURN = '''
host_name:
    description: The name of the target machine.
    type: str
host_id:
    description: The system id of the target machine in maas.
    type: str
status:
    description: The status of the target machine.
    type: str
ip_addresses:
    description: The list of the ip addresses of the target machine.
    typs: list
'''

try:
    from maas.client import connect as maas_connect
    from maas.client.enum import NodeStatus
    from maas.client.errors import MAASException
    HAS_MAAS_LIB = True
except ImportError:
    HAS_MAAS_LIB = False
    
try:
    import timeout_decorator as timeout
    HAS_TIMEOUT = True
except ImportError:
    HAS_TIMEOUT = False

import typing
import repr
from ansible.module_utils.basic import AnsibleModule

DEFAULT_WAIT_TIME = 300

def run_module():
    # define the available arguments/parameters that a user can pass to
    # the module
    module_args = dict(
        maas_url=dict(type='str', required=True),
        api_key=dict(type='str', required=True), 
        state=dict(choices=['absent', 'present'], default='present'), 
        os=dict(type='str', default=None), 
        wait=dict(type='bool', default=True), 
        wait_time=dict(type='int', default=DEFAULT_WAIT_TIME), 
        ensure=dict(type='bool', default=True),
        target_name=dict(type='str', default=None),         
        tags_match=dict(type='list', default=None), 
        zone_match=dict(type='str', default='default'), 
        name_match=dict(type='str', default=None) 
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        host_name='',
        host_id='', 
        status='', 
        ip_addresses=[]
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )
    
    if not HAS_MAAS_LIB:
        module.fail_json(msg='python_libmaas is required for this module')
    if not HAS_TIMEOUT:
        module.fail_json(msg='timeout_decorator is required for this module')


    #### a handler class used to process the maas machine operations ####
    class MaasMachineHandler(object):

        try:
            DEFAULT_WAIT_TIME
        except Exception:
            DEFAULT_WAIT_TIME = 300
            
        (RESULT_ERROR, RESULT_TIMEOUT, RESULT_COMPLETE, RESULT_ALLOC) = \
        ('error', 'timeout', 'complete', 'allocated')
        
        def __init__(self, 
                    maas_url: str, 
                    api_key: str, 
                    os: str=None
                    wait: bool=True, 
                    wait_time: int=DEFAULT_WAIT_TIME, 
                    ensure: bool=True, 
                    target_name: str=None
                    tags_match: typing.Sequence[str]=None, 
                    zone_match: str='default', 
                    name_match: str=None,  
                    log=None):
        
            self.maas_url = maas_url
            self.api_key = api_key
            self.os = os
            self.wait = wait
            self.wait_time = wait_time
            self.ensure = ensure
            self.target_name = target_name
            self.tags_match = tags_match
            self.zone_match = zone_match
            self.name_match = name_match
            self.log = log
            
            # store the current result with a structure as
            # status: 'error', 'timeout', 'complete', 'allocated'
            # error_msg:
            # machine: an object of a machine
            
            self._result = dict(status=None, 
                                error_msg=None, 
                                machine=None)
            # store the name of the machines needed to be released
            # when error, timeout or complete
            self._clean_machines = []
        
        # get the current result
        def get_result(self):
            return self._result
        
        # called when an error occurs
        def _handle_error(self, error_msg, **kwargs):
            self._error_print(error_msg, **kwargs)
            self._result['status'] = RESULT_ERROR
            self._result['error_msg'] = error_msg
            
        def _add_machine_to_result(self, machine):
            self._result['machine'] = machine
        
        # called when timeout occurs
        def _handle_timeout(self, machine):
            self._result['status'] = RESULT_TIMEOUT
            self._add_machine_to_result(machine)
            
        # called when complete
        def _handle_complete(self, machine):
            self._result['status'] = RESULT_COMPLETE
            self._add_machine_to_result(machine)
            
        # called when machine is allocated
        def _handle_alloc(self, machine):
            self._result['status'] = RESULT_ALLOC
            self._add_machine_to_result(machine)
        
        # connect to the maas api server with the api key
        def api_connect(self):        
            try:
                self.client = maas_connect(self.maas_url, apikey=self.api_key)
            except MAASException as e:
                msg = "maas error \'{}\' occurs when connect \
                                to the maas api server".format(e)
                self._handle_error(msg)
            except Exception as e:
                msg = "error \'{}\' occurs when connect \
                                to the maas api server".format(e)
                self._handle_error(msg)                                
            else:
                if not self.client.users.whoami().is_admin:
                    self._handle_error("the current user is not an admin")
                self._info_print("connected to the maas api server")
    
        # a private func to allocate a machine according to the input params
        # allocation is executed only when no error in current result
        def _allocate_machine(self):
            if not self._result['error_msg']:
                try:
                    m = self.client.machines.allocate(hostname=self.name_match, 
                                                      tags=self.tags_match, 
                                                      zone=self.zone_match)
                    self._info_print("allocate the machine with: ")
                    self._info_print("name: {}, tags: {}, zone: {}", 
                                     m.hostname, 
                                     repr(m.tags), 
                                     m.zone.name)
                    self._handle_alloc(m)
                except MAASException as e:
                    msg = "maas error \'{}\' occurs when allocate \
                                        the machine with: \nname: {}, tags: {}, zone: {}".format( 
                                        e, self.name_match, repr(self.tags_match), self.zone_match)
                    self._handle_error(msg)
                except Exception as e:
                    msg = "error \'{}\' occurs when allocate \
                                        the machine with: \nname: {}, tags: {}, zone: {}".format( 
                                        e, self.name_match, repr(self.tags_match), self.zone_match)
                    self._handle_error(msg)
    
        # a private func to deploy a machine according to the input params
        # deployment is called only when the current result's status is RESULT_ALLOC
        def _deploy_machine(self):
            if self._result['status'] == RESULT_ALLOC:
                try:
                    self._result['machine'].deploy(distro_series=self.os, 
                                                   wait=self.wait)
                    self._result['machine'].refresh()
                    self._info_print("end the deployment of machine with: ")
                    self._info_print("name: {}, tags: {}, zone: {}, status: {}", 
                                     self._result['machine'].hostname, 
                                     repr(self._result['machine'].tags), 
                                     self._result['machine'].zone.name, 
                                     self._result['machine'].status_name)
                except MAASException as e:
                    self._result['machine'].refresh()
                    msg = "maas error \'{}\' occurs when deploy the machine with: \
                                    \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                    e, self._result['machine'].hostname, 
                                       repr(self._result['machine'].tags), 
                                       self._result['machine'].zone.name,
                                       self._result['machine'].status_name)
                    self._handle_error(msg)
                except Exception as e:
                    self._result['machine'].refresh()
                    msg = "error \'{}\' occurs when deploy the machine with: \
                                    \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                    e, self._result['machine'].hostname, 
                                       repr(self._result['machine'].tags), 
                                       self._result['machine'].zone.name,
                                       self._result['machine'].status_name)
                    self._handle_error(msg)
        
        # a private func to release a machine specified by the name of the machine
        def _release_machine(self, name, zone):        
            func = lambda m: m.release()
            try:
                [func(m) for m in client.machines.list() \
                            if m.hostname == name and m.zone.name == zone]
                self._info_print("release the machine \
                                  with a name of \'{}\' in zone of \'{}\'", name, zone)
            except MAASException as e:
                msg = "maas error \'{}\' occurs when release \
                                    the machine \'{}\' in zone \'{}\'".format(e, name, zone)
                self._handle_error(msg)
            except Exception as e:
                msg = "error \'{}\' occurs when release \
                                    the machine \'{}\' in zone \'{}\'".format(e, name, zone)
                self._handle_error(msg)
    
        # a public func to release a machine specified by the name of the machine
        def release_machine(self):        
            if not self.name_match:
                msg = "the name of the released machine must \
                                be specified"
                self._handle_error(msg)
            else:
                self._release_machine(self.name_match, self.zone_match)
                if not self._result['error_msg']:
                    self._result['status'] = RESULT_COMPLETE
            
            
            
        # a printer wrapper for normal messages
        def _info_print(self, m, *args, **kwargs):     
            if self.log:
                self.log.info(m.format(*args), **kwargs)
            else:
                print(m.format(*args, **kwargs))
    
        # a printer wrapper for error messages
        def _error_print(self, m, *args, **kwargs):
            if self.log:
                self.log.error(m.format(*args), **kwargs)
            else:
                print(m.format(*args, **kwargs))

    ### the handler class for maas machine operations ###                
        
    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        return result

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)
    result['original_message'] = module.params['name']
    result['message'] = 'goodbye'

    # use whatever logic you need to determine whether or not this module
    # made any modifications to your target
    if module.params['new']:
        result['changed'] = True

    # during the execution of the module, if there is an exception or a
    # conditional state that effectively causes a failure, run
    # AnsibleModule.fail_json() to pass in the message and the result
    if module.params['name'] == 'fail me':
        module.fail_json(msg='You requested this to fail', **result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()

