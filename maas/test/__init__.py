__all__ = [
    "MaasMachineHandler"
]

try:
    from maas.client import connect as maas_connect
    from maas.client.enum import NodeStatus
    from maas.client.errors import MAASException
    HAS_MAAS_LIB = True
except ImportError:
    HAS_MAAS_LIB = False
    
try:
    import timeout_decorator
    HAS_TIMEOUT = True
except ImportError:
    HAS_TIMEOUT = False

import typing
import repr


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
        
    # clear the current result
    def _clear_result(self):
        self._result = dict(status=None, 
                            error_msg=None, 
                            machine=None)
    
    # get the current result
    def get_clean_machines(self):
        return self._clean_machines
    
    # release the machines in the clean group
    def release_clean_machines(self):
        for machine in self._clean_machines:
            try:
                machine.release()
            except MAASException as e:
                self._error_print("maas error \'{}\' occurs when clean \
                                    the machine \'{}\'", e, machine.hostname)
            except Exception:
                self._error_print("error \'{}\' occurs when clean \
                                    the machine \'{}\'", e, machine.hostname)
    
    # called when an error occurs
    def _handle_error(self, *args, error_msg='unknown error occurs', **kwargs):
        self._error_print(error_msg, *args, **kwargs)
        self._result['status'] = RESULT_ERROR
        self._result['error_msg'] = error_msg
        
    def _add_machine_to_result(self, machine):
        self._result['machine'] = machine
    
    # called when timeout occurs
    def _handle_timeout(self, *args, msg='timeout occurs', **kwargs):
        self._info_print(msg, *args, **kwargs)
        self._result['status'] = RESULT_TIMEOUT
        self._result['error_msg'] = msg
        
    # called when complete
    def _handle_complete(self, *args, msg='process complete', **kwargs):
        self._info_print(msg, *args, **kwargs)
        self._result['status'] = RESULT_COMPLETE
        
    # called when machine is allocated
    def _handle_alloc(self, machine, *args, msg='allocate complete', **kwargs):
        self._info_print(msg, *args, **kwargs)
        self._result['status'] = RESULT_ALLOC
        self._add_machine_to_result(machine)
    
    # connect to the maas api server with the api key
    def api_connect(self):        
        try:
            self.client = maas_connect(self.maas_url, apikey=self.api_key)
        except MAASException as e:
            msg = "maas error \'{}\' occurs when connect \
                            to the maas api server".format(e)
            self._handle_error(error_msg=msg)
        except Exception as e:
            msg = "error \'{}\' occurs when connect \
                            to the maas api server".format(e)
            self._handle_error(error_msg=msg)                                
        else:
            if not self.client.users.whoami().is_admin:
                self._handle_error(error_msg="the current user is not an admin")
            self._info_print("connected to the maas api server")

    # a private func to allocate a machine according to the input params
    # allocation is executed only when no error in current result
    def _allocate_machine(self):
        if not self._result['status'] == RESULT_ERROR:
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
            except MAASException as e:
                msg = "maas error \'{}\' occurs when allocate \
                                    the machine with: \nname: {}, tags: {}, zone: {}".format( 
                                    e, self.name_match, repr(self.tags_match), self.zone_match)
                self._handle_error(error_msg=msg)
            except Exception as e:
                msg = "error \'{}\' occurs when allocate \
                                    the machine with: \nname: {}, tags: {}, zone: {}".format( 
                                    e, self.name_match, repr(self.tags_match), self.zone_match)
                self._handle_error(error_msg=msg)

    # a exception raised when timeout occurs
    class TimeoutException(Exception):
        pass
    
    # a private func to deploy a machine according to the input params
    # deployment is called only when the current result's status is RESULT_ALLOC
    @timeout_decorator.timeout(self.wait_time, timeout_exception=TimeoutException)
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
                self._handle_error(error_msg=msg)
            except Exception as e:
                self._result['machine'].refresh()
                msg = "error \'{}\' occurs when deploy the machine with: \
                                \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                e, self._result['machine'].hostname, 
                                   repr(self._result['machine'].tags), 
                                   self._result['machine'].zone.name,
                                   self._result['machine'].status_name)
                self._handle_error(error_msg=msg)                
    
    # a exception raised when deploying fails in ensure deploy
    class DeployFail(Exception):
        pass
    
    # called when ensure is true that repeats machine deployment until succeed
    # machines that failed to be deployed or encounter the timeout will be
    # added to the _clean_machines
    def _ensure_deploy_machine(self):
        while not self._result['status'] == RESULT_COMPLETE:
            try:
                self._allocate_machine()
                if not self._result['status'] == RESULT_ALLOC:
                    raise DeployFail("machine allocation fails")
                try:
                    self._deploy_machine()
                    if self._result['machine']:
                        self._result['machine'].refresh()
                        if self._result['machine'].status == NodeStatus.DEPLOYED:
                            self._result['status'] = RESULT_COMPLETE
                        else:
                            raise DeployFail("machine deployment fails")
                    else:
                        raise DeployFail("machine deployment fails")
                except TimeoutException:
                    if self._result['machine']:
                        self._result['machine'].refresh()
                        msg = "timeout occurs when deploy the machine with: \
                                        \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                          self._result['machine'].hostname, 
                                          repr(self._result['machine'].tags), 
                                          self._result['machine'].zone.name,
                                          self._result['machine'].status_name)
                    else:
                        msg = "a timeout occurs"
                    self._handle_timeout(msg=msg)
                    raise DeployFail("machine deployment fails")
            except DeployFail:
                if self._result['machine']:
                    self._clean_machines.append(self._result['machine'])
                self._clear_result()
    
    # a public func to deploy a machine according to the input params
    def deploy_machine(self):
        if not self.ensure:
            self._allocate_machine()
            try:
                self._deploy_machine()
                if not self._result['status'] == RESULT_ERROR:
                    msg = "complete the process of deploying the machine with: \
                                \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                   self._result['machine'].hostname, 
                                   repr(self._result['machine'].tags), 
                                   self._result['machine'].zone.name,
                                   self._result['machine'].status_name)
                    self._handle_complete(msg=msg)
            except TimeoutException:
                if self._result['machine']:
                    self._result['machine'].refresh()
                    msg = "timeout occurs when deploy the machine with: \
                                    \nname: {}, tags: {}, zone: {}, status: {}".format( 
                                      self._result['machine'].hostname, 
                                      repr(self._result['machine'].tags), 
                                      self._result['machine'].zone.name,
                                      self._result['machine'].status_name)
                else:
                    msg = "a timeout occurs"
                self._handle_timeout(msg=msg)
        else:
            self._ensure_deploy_machine()
    
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
            if not self._result['status'] == RESULT_ERROR:
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