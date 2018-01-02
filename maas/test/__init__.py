__all__ = [
    "MaasMachineHandler"
]

try:
    from maas.client import connect as maas_connect
    from maas.client.enum import NodeStatus
    from maas.client.errors import MAASException
    from maas.client.viscera.machines import MachineNotFound
    from maas.client.bones import CallError
    HAS_MAAS_LIB = True
except ImportError:
    HAS_MAAS_LIB = False

import typing
import time


#### a handler class used to process the maas machine operations ####

class MaasMachineHandler(object):
        
    # status definitions of the process result
    # RESULT_ERROR, RESULT_COMPLETE, RESULT_TIMEOUT and RESULT_NO_MACHINE are observable outside the class
    #   RESULT_COMPLETE: 
    #       when a machine is successfully deployed if wait=True or ensure=True
    #       when a deploy is called without error if wait=False and ensure=False (no garantee to complete deploying)
    #       when a release action is called (no garantee to complete release)
    #   RESULT_TIMEOUT: 
    #       when the last time of deploying timeout if wait=True or ensure=True (when wait=True and ensure=False, deploying is called only one time)
    #   RESULT_NO_MACHINE: 
    #       when no machine is available at the last time of allocating
    #       this implies no concrete action is applied when ensure=False
    RESULT_ERROR, RESULT_TIMEOUT, RESULT_COMPLETE, RESULT_ALLOC, RESULT_NO_MACHINE = \
    'error', 'timeout', 'complete', 'allocated', 'no available machine'
    
    DEFAULT_WAIT_TIME = 600
    DEFAULT_MAX_TRY = 5
    DEFAULT_WAIT_INTERVAL = 5
    
    # a exception raised when timeout occurs
    class TimeoutException(Exception):
        pass
    
    # a exception raised when deploying fails in ensure deploy
    class DeployFail(Exception):
        pass
    
    def __init__(self, 
                maas_url: str, 
                api_key: str, 
                os: str=None,
                wait: bool=True, 
                wait_time: int=DEFAULT_WAIT_TIME,
                wait_interval: int=DEFAULT_WAIT_INTERVAL,
                ensure: bool=True,
                max_try: int=DEFAULT_MAX_TRY,
                disk_erase: bool=False,
                target_name: str=None,
                tags_match: typing.Sequence[str]=None, 
                zone_match: str=None, 
                name_match: str=None,
                id_match: str=None,                
                log=None):
    
        self.maas_url = maas_url
        self.api_key = api_key
        self.os = os
        self.wait = wait
        self.wait_time = wait_time
        self.wait_interval = wait_interval
        self.ensure = ensure
        self.max_try = max_try
        self.disk_erase = disk_erase
        self.target_name = target_name
        self.tags_match = tags_match
        self.zone_match = zone_match
        self.name_match = name_match
        self.id_match = id_match
        self.log = log
        
        # store the current result with a structure as
        # status: 'error', 'timeout', 'complete', 'allocated'
        # error_msg:
        # machine: an object of a machine
        
        self._result = dict(status=None, 
                            error_msg=None, 
                            machine=None)
        # store the id of the machines needed to be released
        # when error, timeout or complete
        self._clean_machines = []
    
    # get the current result
    def get_result(self):
        return self._result
        
    # clear the current result
    def clear_result(self):
        self._result['status'] = None
        self._result['error_msg'] = None
        self._result['machine'] = None
    
    # get the current result
    def get_clean_machines(self):
        return self._clean_machines
    
    # release the machines in the clean group
    def release_clean_machines(self, erase: bool=False):
        for i in self._clean_machines:
            try:
                machine = self.client.machines.get(i)
                machine.release(erase=erase)                
            except CallError as e:
                msg = "maas call error \'" + str(e).replace('{', '{{').replace('}', '}}') + "\' occurs when clean the machine \'{}\'".format(machine.hostname)
                self._error_print(msg)
            except MAASException as e:
                self._error_print("maas error \'{}\' occurs when clean the machine \'{}\'", e, machine.hostname)
            except Exception as e:
                self._error_print("error \'{}\' occurs when clean the machine \'{}\'", e, machine.hostname)
        self._clean_machines = []
    
    # called when an error occurs
    def _handle_error(self, *args, error_msg='unknown error occurs', **kwargs):
        self._error_print(error_msg, *args, **kwargs)
        self._result['status'] = self.RESULT_ERROR
        self._result['error_msg'] = error_msg
        
    def _add_machine_to_result(self, machine):
        self._result['machine'] = machine
    
    # called when timeout occurs
    def _handle_timeout(self, *args, msg='timeout occurs', **kwargs):
        self._info_print(msg, *args, **kwargs)
        self._result['status'] = self.RESULT_TIMEOUT
        self._result['error_msg'] = msg
        
    # called when complete
    def _handle_complete(self, *args, msg='process complete', **kwargs):
        self._info_print(msg, *args, **kwargs)
        self._result['status'] = self.RESULT_COMPLETE
        
    # called when machine is allocated
    def _handle_alloc(self, machine, *args, msg='allocate complete', **kwargs):
        self._info_print(msg, *args, **kwargs)
        self._result['status'] = self.RESULT_ALLOC
        self._add_machine_to_result(machine)
        
    # called when not enough machine to be allocated
    def _handle_no_machine(self, *args, msg='not enough machine', **kwargs):
        self._error_print(msg, *args, **kwargs)
        self._result['status'] = self.RESULT_NO_MACHINE
        self._result['error_msg'] = msg
    
    # connect to the maas api server with the api key
    def api_connect(self):        
        try:
            self.client = maas_connect(self.maas_url, apikey=self.api_key)
        except CallError as e:
            msg = "maas call error \'" + str(e).replace('{', '{{').replace('}', '}}') + "\' occurs when connect to the maas api server"
            self._handle_error(error_msg=msg)
        except MAASException as e:
            msg = "maas error \'{}\' occurs when connect to the maas api server".format(e)
            self._handle_error(error_msg=msg)
        except Exception as e:
            msg = "error \'{}\' occurs when connect to the maas api server".format(e)
            self._handle_error(error_msg=msg)                                
        else:
            if not self.client.users.whoami().is_admin:
                self._handle_error(error_msg="the current user is not an admin")
            self._info_print("connected to the maas api server")

    # a private func to allocate a machine according to the input params
    # allocation is executed only when no error in current result
    def _allocate_machine(self):
        if not self._result['status'] == self.RESULT_ERROR:
            try:
                m = self.client.machines.allocate(hostname=self.name_match, 
                                                  tags=self.tags_match, 
                                                  zone=self.zone_match)
                if not m.status == NodeStatus.ALLOCATED:
                    raise Exception("fail to allocate machine")
                msg="allocate the machine with: \nname: {}, tags: {}, zone: {}".format( 
                                 m.hostname, 
                                 repr(m.tags), 
                                 m.zone.name)
                self._handle_alloc(m, msg=msg)
            except CallError as e:
                msg = "maas call error \'" + str(e).replace('{', '{{').replace('}', '}}') + "\' occurs when allocate the machine with: \nname: {}, tags: {}, zone: {}".format( 
                                    self.name_match, repr(self.tags_match), self.zone_match)
                self._handle_error(error_msg=msg)
            except MAASException as e:
                msg = "maas error \'{}\' occurs when allocate the machine with: \nname: {}, tags: {}, zone: {}".format( 
                                    e, self.name_match, repr(self.tags_match), self.zone_match)
                self._handle_error(error_msg=msg)
            except MachineNotFound as e:
                msg = "maas error \'{}\' occurs when allocate the machine with: \nname: {}, tags: {}, zone: {}".format( 
                                    e, self.name_match, repr(self.tags_match), self.zone_match)
                self._handle_no_machine(msg=msg)
            except Exception as e:
                msg = "error \'{}\' occurs when allocate the machine with: \nname: {}, tags: {}, zone: {}".format( 
                                    e, self.name_match, repr(self.tags_match), self.zone_match)
                self._handle_error(error_msg=msg)

    
    # a private func to deploy a machine according to the input params
    # deployment is called only when the current result's status is self.RESULT_ALLOC
    def _deploy_machine(self):
        if self._result['status'] == self.RESULT_ALLOC:
            try:
                self._result['machine'].deploy(distro_series=self.os)
                self._result['machine'].refresh()
                if self.wait or self.ensure:
                    wait_count = 0
                    while self._result['machine'].status == NodeStatus.DEPLOYING and \
                          wait_count < self.wait_time:
                        self._result['machine'].refresh()
                        time.sleep(self.wait_interval)
                        wait_count = wait_count + self.wait_interval
                        self._info_print("wait for deploying machine with: \nname: {}, tags: {}, zone: {}, status: {} \ntime passed: {} seconds", 
                                         self._result['machine'].hostname, 
                                         repr(self._result['machine'].tags), 
                                         self._result['machine'].zone.name, 
                                         self._result['machine'].status_name, 
                                         wait_count)
                    if not self._result['machine'].status == NodeStatus.DEPLOYED:
                        if wait_count >= self.wait_time:
                            raise self.TimeoutException
                        else:
                            raise self.DeployFail
                self._info_print("end the deployment of machine with: \nname: {}, tags: {}, zone: {}, status: {}", 
                                 self._result['machine'].hostname, 
                                 repr(self._result['machine'].tags), 
                                 self._result['machine'].zone.name, 
                                 self._result['machine'].status_name)
            except CallError as e:
                self._result['machine'].refresh()
                msg = "maas call error \'" + str(e).replace('{', '{{').replace('}', '}}') + "\' occurs when deploy the machine with: \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                   self._result['machine'].hostname, 
                                   repr(self._result['machine'].tags), 
                                   self._result['machine'].zone.name,
                                   self._result['machine'].status_name)
            except MAASException as e:
                self._result['machine'].refresh()
                msg = "maas error \'{}\' occurs when deploy the machine with: \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                e, self._result['machine'].hostname, 
                                   repr(self._result['machine'].tags), 
                                   self._result['machine'].zone.name,
                                   self._result['machine'].status_name)
                self._handle_error(error_msg=msg)
            except self.TimeoutException:
                msg = "timeout occurs when deploy the machine with: \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                  self._result['machine'].hostname, 
                                  repr(self._result['machine'].tags), 
                                  self._result['machine'].zone.name,
                                  self._result['machine'].status_name)
                self._handle_timeout(msg=msg)
            except self.DeployFail:
                msg = "Fail to deploy the machine with: \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                   self._result['machine'].hostname, 
                                   repr(self._result['machine'].tags), 
                                   self._result['machine'].zone.name,
                                   self._result['machine'].status_name)
                self._handle_error(error_msg=msg)
            except Exception as e:
                self._result['machine'].refresh()
                msg = "error \'{}\' occurs when deploy the machine with: \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                e, self._result['machine'].hostname, 
                                   repr(self._result['machine'].tags), 
                                   self._result['machine'].zone.name,
                                   self._result['machine'].status_name)
                self._handle_error(error_msg=msg)                
    
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
                        msg = "complete the process of deploying the machine with: \nname: {}, tags: {}, zone: {}, status: {}".format( 
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
                msg = "no available machine for allocating the machine with: \nname: {}, tags: {}, zone: {}".format( 
                                    self.name_match, repr(self.tags_match), self.zone_match)
                self._handle_no_machine(msg=msg)
            except self.DeployFail as e:
                try_count = try_count + 1
                msg = "error \'{}\' occurs when tring to deploy the machine with: \nname: {}, tags: {}, zone: {} \ntry times: {}, try another one".format( 
                                    e, self.name_match, repr(self.tags_match), self.zone_match, try_count)
                self._info_print(msg)
                if self._result['machine']:
                    m_id = self._result['machine'].system_id
                    if m_id not in self._clean_machines:
                        self._clean_machines.append(m_id)
                if try_count < self.max_try:
                    self.clear_result()
    
    # a public func to deploy a machine according to the input params
    def deploy_machine(self):
        if not self.ensure:
            self._allocate_machine()
            self._deploy_machine()
            if self._result['status'] == self.RESULT_ALLOC:
                msg = "complete the process of deploying the machine with: \nname: {}, tags: {}, zone: {}, status: {}".format( 
                               self._result['machine'].hostname, 
                               repr(self._result['machine'].tags), 
                               self._result['machine'].zone.name,
                               self._result['machine'].status_name)
                self._handle_complete(msg=msg)
        else:
            self._ensure_deploy_machine()
    
    # a private func to release a machine specified by the name of the machine
    def _release_machine(self, name, zone, id):        
        m_found = False
        func = lambda m: m.release(erase=self.disk_erase)
        try:
            if id:
                m = self.client.machines.get(system_id=id)
                if m:
                    m_found = True
                    func(m)
                    self._info_print("release the machine with a id of \'{}\' and a name of \'{}\' in zone of \'{}\'", id, m.hostname, m.zone.name)
            elif zone:
                for m in self.client.machines.list():
                    if m.hostname == name and m.zone.name == zone:
                        m_found = True
                        func(m)
                        self._info_print("release the machine with a name of \'{}\' in zone of \'{}\'", name, zone)
            else:
                for m in self.client.machines.list():
                    if m.hostname == name:
                        m_found = True
                        func(m)
                        self._info_print("release the machine with a name of \'{}\' in zone of \'{}\'", name, m.zone.name)
            if not m_found:
                    raise Exception("no such machine is found")
        except CallError as e:
            if id:
                msg = "maas call error \'" + str(e).replace('{', '{{').replace('}', '}}') + "\' occurs when release the machine with id \'{}\'".format(id)
            elif zone:
                msg = "maas call error \'" + str(e).replace('{', '{{').replace('}', '}}') + "\' occurs when release the machine \'{}\' in zone \'{}\'".format(name, zone)
            else:
                msg = "maas call error \'" + str(e).replace('{', '{{').replace('}', '}}') + "\' occurs when release the machine \'{}\'".format(name)
            self._handle_error(error_msg=msg)
        except MAASException as e:
            if id:
                msg = "maas error \'{}\' occurs when release the machine with id \'{}\'".format(e, id)
            elif zone:
                msg = "maas error \'{}\' occurs when release the machine \'{}\' in zone \'{}\'".format(e, name, zone)
            else:
                msg = "maas error \'{}\' occurs when release the machine \'{}\'".format(e, name)
            self._handle_error(error_msg=msg)
        except Exception as e:
            if id:
                msg = "error \'{}\' occurs when release the machine with id \'{}\'".format(e, id)
            elif zone:
                msg = "error \'{}\' occurs when release the machine \'{}\' in zone \'{}\'".format(e, name, zone)
            else:
                msg = "error \'{}\' occurs when release the machine \'{}\'".format(e, name)
            self._handle_error(error_msg=msg)

    # a public func to release a machine specified by the name of the machine
    def release_machine(self):        
        if not (self.name_match or self.id_match):
            msg = "error occurs due to that the name or the system id of the released machine must be specified"
            self._handle_error(error_msg=msg)
        else:
            self._release_machine(self.name_match, self.zone_match, self.id_match)
            if not self._result['status'] == self.RESULT_ERROR:
                self._result['status'] = self.RESULT_COMPLETE
        
        
        
    # a printer wrapper for normal messages
    def _info_print(self, m, *args, **kwargs):     
        if self.log:
            self.log.info(m.format(*args) + '\n', **kwargs)
        else:
            print(m.format(*args, **kwargs) + '\n')

    # a printer wrapper for error messages
    def _error_print(self, m, *args, **kwargs):
        if self.log:
            self.log.error(m.format(*args) + '\n', **kwargs)
        else:
            print(m.format(*args, **kwargs) + '\n')
 