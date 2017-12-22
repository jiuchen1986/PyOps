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
    wait:
        description:
            - If the module should wait for the machine to be deployed.
        required: false
        default: 'yes'
    ensure:
        description:
            - If the requested machine deployment must be fulfilled.
            - If so, the module will repeat deploying until succeed, and release the machine that fails to be deployed.            
        required: false
        default: yes
    tags_match:
        description:
            - A list of tags to match the target machines of maas to be deployed or released.             
        required: false
        default: None
    tag_prefix:
        description:
            - The prefix of the tag will be add to the deployed machine in maas.
            - The final tag will be a conjunction of the prefix and the name of the machine, connected by a '-'.
        required: false
        default: 'auto'
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
# Deploy a machine with a matching tag of "REMOTE-MGMT" and a tag prefix of "AUTO".
- name: deploy a test machine
  maas_machine:
    maas_url: http://maas.adp.gic.ericsson.se/MAAS/
    api_key: ....
    state: present
    tags_match:
    - REMOTE-MGMT
    tag_prefix: ezhecnx
    
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
tags:
    description: The list of the tags of the target machine.
    typs: list
ip_addresses:
    description: The list of the ip addresses of the target machine.
    typs: list
'''

from ansible.module_utils.basic import AnsibleModule

def run_module():
    # define the available arguments/parameters that a user can pass to
    # the module
    module_args = dict(
        name=dict(type='str', required=True),
        new=dict(type='bool', required=False, default=False)
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

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

