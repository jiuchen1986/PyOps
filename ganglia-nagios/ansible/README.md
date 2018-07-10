# Automated Setup of a Ganglia-Nagios System monitoring Kubernetes cluster
This project provides Ansible playbooks to install Ganglia and Nagios to monitor the infrastructure bearing a single or multiple Kubernetes clusters.

## Cautions
The playbooks in this project work under **ansible 2.4** and **python 2.7.5**, but break down under **ansible 2.5** due to ansible issue [https://github.com/ansible/ansible/issues/14166](https://github.com/ansible/ansible/issues/14166). So far the issue seams to not be fixed yet, Therefore, please ensure that running this project with ansible 2.4 before the ansible issue is fixed.

## Required Preparations On The Hosts in Monitoring Clusters
Basically, there is only one requirement needs to be fulfilled on the hosts in the monitoring clusters. **The host acting as the header of a cluster must be able to resolve all the hosts' ip addresses from their fqdns in the clusters**. A cluster header is a host from which the ganglia gmetad on the monitoring server gets metric data of the cluster.

Hence, if the connected DNS server can not help, the mapping between the ip address and the fqdn of each host in the monitoring cluster must be added manually to the `/etc/hosts` file on the cluster header.

## Add Monitoring To A Single Cluster With The Installed Monitoring Server
This project supports add monitoring to the hosts belonging to a single cluster, with an installed monitoring server, i.e. the host running nagios-core, ganglia-gmetad and ganglia-web, using a single inventory file along with several required variables input via commands line.

Those operations targeting on a single cluster support 3 different types of the cluster, including the **kubespray**, the **erikube** and the **devenv** in which hosts running ubuntu.

The actions taken for a single cluster are:


- install ganglia-gmond on each host in the cluster with multicast mode, several preparations on the host maybe taken places on depends, e.g. add EPEL yum repo
- indicate ganglia-gmetad on the monitoring server to the head host of the cluster
- add host and service definitions to the nagios-core on the monitoring server related to the metrics of hosts in the cluster

### Prepare an inventory file for a single cluster

An example of the modified inventory file is given in a file named `single_cluster_test_hosts`:

    node1 ansible_host=10.xxx.xxx.30
    node2 ansible_host=10.xxx.xxx.31
    # 10.xxx.xxx.30
    # 10.xxx.xxx.31
    
    [master]
    node1
    # 10.xxx.xxx.30
    
    [etcd]
    node1
    # 10.xxx.xxx.30
    
    [worker]
    node2
    # 10.xxx.xxx.31
    
    [ingress_lb]
    

**Notice:**

- Use explicitly defined the `ansible_host` variable with a ip address for each host if the inventory name is not ip address, or
- Directly use ip addresses for the inventory names.
- The groups without any hosts, e.g. the `ingress_lb` group, could just be omitted in the inventory file.
- SSH parameters required to connect to the hosts in the cluster, e.g. `ansible_user`, `ansible_ssh_pass`, or `ansible_become_pass`, add them into this inventory file too.

### Plan extra vars for the playbook
In order to overwrite the variables' values in `group_vars/all.yaml`, variables for operations on the single cluster must be input using `-e` or `--extra-vars` when calling the playbook. Some recognized variables for the current implementation are listed below:

- **single_cluster**: the name of the current cluster
- **ganglia\_nagios\_server**: a resolvable name or a reachable ip address of the installed monitoring server running ganglia-gmetad, ganglia-web and nagios core. **Note** that if ssh parameters, such as `ansible_user`, `ansible_ssh_pass`, or `ansible_become_pass`, are required to connect to the server from the host running the playbooks, add these parameters into `group_vars/ganglia-nagios-server.yaml`
- **gmond\_systemd\_check\_services**: the services needed to be monitored by the gmond on the monitoring host which are managed by the systemd 
- **gmond\_cluster\_head**: the list of endpoints pointing to the heads of the cluster to which the ganglia-gmetad on the monitoring server will connect collecting monitoring data. The endpoints are composed as ip address plus port. **The heads MUST be also master nodes in the cluster**
- **gmond\_multicast\_port**: the port each ganglia-gmond on the monitored host is listening on. Must be identical to the one used in the **gmond\_cluster\_head**
- **gmond\_systemd\_check\_services**: the list of systemd managing services whose status need to be collected by the ganglia gmond on the monitoring hosts
- **cluster\_type**: the type of the cluster which can be used to distinguish application of different monitoring metrics. 
- **cluster\_contacts**: the list of contacts only receiving cluster-specific notifications. The contacts need to add to the nagios core previously. See the `Manage Nagios Contacts` section.

Here gives an example of how to input the required variables using `-e` when calling the playbook to operate on a single cluster of type `erikube` in which hosts will be checked with the status of systemd services named `kubelet`, `docker` and `etcd_container`:

    ansible-playbook -i path_to_your_erikube-like_inventory_file \
        -e "single_cluster=erikube_cluster_name" \
        -e "ganglia_nagios_server=localhost" \
        -e "{'gmond_systemd_check_services': ['kubelet', 'docker', 'etcd_container']}" \
        -e "{'gmond_cluster_head': ['xxx.xxx.xxx.xxx:8661']}" \
        -e "gmond_multicast_port=8661" \
        -e "{'cluster_contacts': ['xxx']}"
        -e "cluster_type=erikube" \
        -e "act=cluster_install" \
        site.yaml

And an example to operate on a single cluster of type `devenv` in which hosts will be checked with the status of systemd services named `docker`, is given as:

    ansible-playbook -i ubuntu_hosts \
        -e "single_cluster=devenv_cluster_name" \
        -e "ganglia_nagios_server=xxx.xxx.xxx.xxx" \
        -e "{'gmond_systemd_check_services': ['docker']}" \
        -e "{'gmond_cluster_head': ['xxx.xxx.xxx.xxx:8662']}" \
        -e "gmond_multicast_port=8662" \
        -e "{'cluster_contacts': ['xxx']}"
        -e "cluster_type=devenv" \
        -e "act=cluster_install" \
        site.yaml

Then the example for a single cluster of type `kubespray` using default systemd services checking configurations in `group_vars/all.yaml`:

    ansible-playbook -i ubuntu_hosts \
        -e "single_cluster=kubespray_cluster_name" \
        -e "ganglia_nagios_server=xxx.xxx.xxx.xxx" \
        -e "{'gmond_cluster_head': ['xxx.xxx.xxx.xxx:8663']}" \
        -e "gmond_multicast_port=8663" \
        -e "{'cluster_contacts': ['xxx']}"
        -e "cluster_type=kubespray" \
        -e "act=cluster_install" \
        site.yaml

**Notice:**

- Notice the differences on the input variables of `gmond_systemd_check_services` and `cluster_type` between above examples for different cluster types.
- Actually all the variables defined in `group_vars/all.yaml` and `group_vars/ganglia-nagios-server.yaml` could be overwritten by setting via `-e` flags in the command line.
- In case too much inputs at command line, a yaml/json file containing the extra variables could be used by `-e "@extra_vars_file.yaml/json"`. See `single_host_vars.yaml` for example. Then, the playbook can be run as

        ansible-playbook -i path_to_your_inventory_file -e "act=cluster_cluster" -e "@extra_vars_file.yaml" site.yaml

- The meaning of `-e "act=cluster_install"` will be described later.

### Setup monitoring for the cluster
Completing the above steps, monitoring for the single cluster can be setup by executing:

    ansible-playbook -i path_to_your_inventory_file -e "act=cluster_install" -e .... site.yaml

where `-e ....` is short for all the variables specified for the cluster operation.

### Update monitoring configuration for the cluster
Updating configurations for a single cluster also is supported, running:

    ansible-playbook -i path_to_your_inventory_file -e "act=cluster_update" -e .... site.yaml


### Remove monitoring for the cluster
Actions applied in the installation for a single cluster could be removed by running:

    ansible-playbook -i path_to_your_inventory_file -e "act=cluster_uninstall" -e "single_cluster=cluster_name" -e "ganglia_nagios_server=xxx.xxx.xxx.xxx" site.yaml

or

    ansible-playbook -i path_to_your_inventory_file -e "act=cluster_delete" -e "single_cluster=cluster_name" -e "ganglia_nagios_server=xxx.xxx.xxx.xxx" site.yaml

**Notice**: The `cluster_uninstall` removes the gmond process and related files, including configuration and plugins, from each monitoring host in the cluster, while the `cluster_delete` only removes monitoring actions on the cluster from the monitoring server side. The `cluster_delete` can be used for the scenarios such as that all hosts of a cluster are shutdown.

## Add Monitoring To Multiple Clusters With/Without Installing The Monitoring Server
This project supports add monitoring to the hosts bearing multiple kubernetes clusters, with or without the monitoring server has been setup.

The actions taken for multiple clusters are:


- install ganglia-gmetad, rrdtool, ganglia-web, and nagios-core to the monitoring server. If monitoring server has been setup, the former actions will be automatically ignored
- install ganglia-gmond on each host in the clusters with multicast mode, several preparations on the host maybe taken places on depends, e.g. add EPEL yum repo
- indicate ganglia-gmetad on the monitoring server to the head hosts of each cluster
- add host and service definitions to the nagios-core on the monitoring server related to the metrics of hosts in the clusters

### List all the cluster names in a variable
Inform the names of all the clusters in a variable named `cluster_list` in `group_vars/all.yaml` as follows:

    # a variable to list all clusters to be monitored, the name of cluster must be identical to the corresponding ansible host group name
    cluster_list:
    - goes

Note that the cluster's name must be identical to the name used for the ansible host group related to the cluster.

### Prepare inventory files for the monitoring server and all the clusters
Recommend that inventory files include one file for the monitoring server, with the group name as `ganglia-nagios-server`, and a separate inventory file for each cluster with the group name same to the cluster's name. For example:

    $ ls inventory/
    ganglia-nagios-server  goes 

An inventory file for a cluster is like:
    
    [goes]
    10.xxx.xxx.[40:42] cluster_role=master
    10.xxx.xxx.[43:50] cluster_role=worker

The variable `cluster_role` is used to support cluster role aware nagios service definitions.


### Configure variables used for installation
Besides to `group_vars/all.yaml` and `group_vars/ganglia-nagios-server.yaml`, a separate file for each cluster containing the variables for the hosts in the cluster can be defined. For example:
    
    ls group_vars/
    all.yaml  ganglia-nagios-server.yaml  goes.yaml

A file for a cluster is like:   
    
    # the nodes that are connected by gmetad 
    gmond_cluster_head:
    - "xxx.xxx.xxx.xxx:8663"
    
    gmond_multicast_port: 8663 

For the meanings of variables, please read the comments in the file and refer to the description for the single cluster scenario. 

**Note that**, with above group_vars file, the target cluster will be treated as a `kubespray` cluster. For other types of clusters, such as `erikube` or `devenv`, more variables are required to overwrite the default settings. For example of an `erikube` cluster, the vars file should be like:

    # the nodes that are connected by gmetad 
    gmond_cluster_head:
    - "xxx.xxx.xxx.xxx:8664"
    
    gmond_multicast_port: 8664  
    
    gmond_systemd_check_services:
    - kubelet
    - docker
    - etcd_container
    
    cluster_type: erikube

And for a `devenv` cluster:

    # the nodes that are connected by gmetad 
    gmond_cluster_head:
    - "xxx.xxx.xxx.xxx:8665"
    
    gmond_multicast_port: 8665  
    
    gmond_systemd_check_services:
    - docker
    
    cluster_type: devenv

**Note** that all the variables defined in `group_vars/all.yaml` could be overwritten by redefining their values in the cluster-specific variable file.

### Installation on multiple clusters and the monitoring server
Completing the above steps, monitoring for multiple clusters and the monitoring server can be setup by executing:

    ansible-playbook -i inventory/ -e "act=install" site.yaml

### Update configuration for monitoring on multiple clusters and the monitoring server
To update configurations for multiple clusters, along with the monitoring server, run:

    ansible-playbook -i inventory/ -e "act=update" site.yaml


### Remove installations on clusters and the monitoring server
Actions applied in the installation for multiple clusters and the monitoring server could be removed by running:

    ansible-playbook -i inventory/ -e "act=uninstall" site.yaml

### Installation on multiple clusters only
To only setup monitoring for multiple clusters, execute:

    ansible-playbook -i inventory/ -e "act=cluster_install" site.yaml

### Update monitoring configuration on multiple clusters only
To only update monitoring configurations for multiple clusters, run:

    ansible-playbook -i inventory/ -e "act=cluster_update" site.yaml

### Remove installations on clusters only
To only remove actions applied in the installation for multiple clusters, running:

    ansible-playbook -i inventory/ -e "act=cluster_uninstall" site.yaml

### Remove monitoring actions on clusters only from the monitoring server side

    ansible-playbook -i inventory/ -e "act=cluster_delete" site.yaml

Refer to the contents in the single cluster section for the differences between the `cluster_uninstall` and the `cluster_delete`.

## Add New Gmond Python Modules To Monitoring Hosts
This project supports add customized gmond python modules to monitoring hosts during installations and updates. To do this, follow the steps below:

- Put the python module file, which is a python file with the suffix of `.py`, `<moudle_name>.py` in `roles/gmond/files/python_modules/`.
- Put the Jinja2 template of the corresponding configuration file, with the suffix of `.pyconf.j2`, `<module_name>.pyconf.j2` in `roles/gmond/templates/conf.d/`.
- Add the module's name `<module_name>` to the list variable `gmond_python_modules` in `group_vars/all.yaml`.
- Run `ansible-playbook -i path_to_your_erikube-like_inventory_file -e "act=cluster_update" site.yaml` for a single erikube cluster, or `ansible-playbook -i inventory/ -e "act=cluster_update" site.yaml` for multiple target clusters.

## Add New Nagios Checking Services Against Ganglia Metrics
This project supports updating the nagios checking services against ganglia metrics multiple times. And with cluster only operations, e.g. `cluster_install`, `cluster_update`, `cluster_uninstall` and `cluster_delete`, there will be no impact on the old services set up for the non-target clusters.

To do this, simply append a complex element to a list variable named `nagios_check_ganglia_metrics` at `group_vars/ganglia-nagios-server.yaml` file. For example:

    nagios_check_ganglia_metrics:
    - name: new_checking_metric
      oper: more
      warn_val: 5
      crit_val: 7
      notify: yes
      cluster_notify: no
      cluster_role: 
      - master
      - etcd
      cluster_type:
      - kubespray
      - erikube

The meanings of members in the element are:

- **name**: Name of the target metric observed in ganglia. The name of the corresponding checking service in nagios will be `<cluster_name>-check-ganglia-<metric_name>`. If the pointed metric is missing in ganglia, the nagios checking service will return an `unkown` status.
- **oper**: Operator for the service to decide triggering alerts on the metric. Current implementations support `more` and `less`.
- **warn_val**: Threshold value for triggering warning alerts on the metric. For `oper` equals `more`/`less`, a warning alert will be triggered if the value of the metric is larger/less than the value of `warn_val`. 
- **crit_val**: Threshold value for triggering critical alerts on the metric. For `oper` equals `more`/`less`, a critical alert will be triggered if the value of the metric is larger/less than the value of `warn_val`. 
- **notify**: Used to disable/enable the notification of alerts raised by the checking service. It can be omitted with a default value of `yes`.
- **cluster_notify**: Used to disable/enable the notification of alerts to the cluster-specific contacts raised by the checking service. When `cluster_notify` is `no` and `notify` is `yes`, notifications will only be sent to the admin contacts.
- **cluster_role**: If this is set, the metric will only be checked on the hosts with at least one of the cluster roles contained in this list, otherwise, the metric will be checked on all the hosts.
- **cluster_type**: If this is set, the metric will only be checked on the clusters with a cluster type contained in this list variable, otherwise, the metric will be checked on all types of cluster.

To cancel a checking on a metric, just remove the related element from the `nagios_check_ganglia_metrics` variable.

After updating the `nagios_check_ganglia_metrics` variable, run the playbook with `act=cluster_install` or `act=cluster_update` if only to apply the updated checking service list on the target clusters, while leave the services unchanged on the non-target clusters, or with `act=update` to apply update on all existing clusters.

## Add Cluster Scope Gmond Python modules and Nagios Service checks
For monitoring against clusters, cluster-scope metrics imply status of the cluster as a whole are crucial. Sometimes such metrics are obtained via cluster provisioning APIs from a single host having access to the APIs, e.g. one master host. This brings several gmond python modules deployed on only one host per-cluster, along with nagios service checks against the deployed host.

This project explicitly provides configurations to setup monitoring for the cluster-scope metrics through variables such as `gmond_head_python_modules` and `nagios_check_ganglia_head_metrics` in `group_vars/all.yaml`.

Similar to the description in the former two sections, customized gmond python modules and nagios checking services can be included by adding relevant elements in those two list variables. However, the modules listed in `gmond_head_python_modules` will only be deployed on one of the host as the cluster head, which is assigned by `gmond_cluster_head`, while the services included in `nagios_check_ganglia_head_metrics` will be checked against that host.

## Cluster Scale-Out
When a cluster needs a scale-out, i.e. add new nodes to the cluster, do the following steps:

- Prepare an inventory file containing both the old hosts and the newly added hosts
- Run the playbook with `act=cluster_install` and the prepared inventory file

After executions, monitoring for the newly added hosts will be setup, while configurations on the old hosts will be updated according to the values of configurable variables of the playbook.

Make sure the **cluster's name is unchanged**.

These work for both the single cluster and the multiple clusters cases with proper inventory files.

## Cluster Scale-In
When a cluster needs a scale-in, i.e. remove nodes from the cluster, do the following steps:

- Prepare an inventory file containing the remaining hosts
- Run the playbook with `act=cluster_delete` and the prepared inventory file
- Run the playbook with `act=cluster_update` and the prepared inventory file

After executions, monitoring for the removed hosts will be absent, while configurations on the remain hosts will be updated according to the values of configurable variables of the playbook.

Make sure the **variable `gmond_cluster_head` is correctly pointed to one of the remaining hosts when run the playbook with `act=cluster_update`**.

These work for both the single cluster and the multiple clusters cases with proper inventory files.

**Note that** the removed nodes maybe treated as being offline in Ganglia, while in Nagios just being removed without alerts.


## Manage Nagios Contacts
This project also provides simple mechanisms managing nagios contacts, including add/delete/update contacts, add/delete/update contacts in admin group, and add/delete/update contacts in cluster-specific group.

### Update all nagios contacts
Follow the below steps to update the whole settings for nagios contacts.

- Set all the contacts' information by modifying the list variable `nagios_contacts` in `group_vars/ganglia-nagios-server.yaml`.
- Run the playbook with `-e "act=update"` and `-t "nagios_core"`, with the inventory file indicating to the host of `ganglia-nagios-server` group.

**Cautions:** Besides the contacts, other configurations for the nagios core may be updated.


### Add nagios contacts
Follow the below steps to add multiple nagios contacts.

- Add the information of the contacts to be added to the list variable `nagios_contacts` in `group_vars/ganglia-nagios-server.yaml`.
- Run the playbook with `-e "act=contacts_add"` and `-t "nagios_core"`, with the inventory file indicating to the host of `ganglia-nagios-server` group.


### Delete nagios contacts
Follow the below steps to delete multiple nagios contacts.

- Add the information of the contacts to be deleted to the list variable `nagios_contacts` in `group_vars/ganglia-nagios-server.yaml`.
- Run the playbook with `-e "act=contacts_delete"` and `-t "nagios_core"`, with the inventory file indicating to the host of `ganglia-nagios-server` group.


### Update all contacts in admin group
Follow the below steps to update the whole settings for nagios contacts in the admin group.

- Make sure the target contacts have been added via either updating all contacts or adding contacts as described above.
- Set all the contacts' information by modifying the list variable `nagios_admin_contacts` in `group_vars/ganglia-nagios-server.yaml`.
- Run the playbook with `-e "act=update"` and `-t "nagios_core"`, with the inventory file indicating to the host of `ganglia-nagios-server` group.

**Cautions:** Besides the contacts in the admin group, other configurations for the nagios core may be updated.


### Add nagios contacts in admin group
Follow the below steps to add multiple nagios contacts into the admin group.

- Make sure the target contacts have been added via either updating all contacts or adding contacts as described above.
- Add the names of the contacts to be added to the list variable `nagios_admin_contacts` in `group_vars/ganglia-nagios-server.yaml`.
- Run the playbook with `-e "act=admin_group_add"` and `-t "nagios_core"`, with the inventory file indicating to the host of `ganglia-nagios-server` group.


### Delete nagios contacts in admin group
Follow the below steps to delete multiple nagios contacts from the admin group.

- Add the information of the contacts to be deleted to the list variable `nagios_admin_contacts` in `group_vars/ganglia-nagios-server.yaml`.
- Run the playbook with `-e "act=admin_group_delete"` and `-t "nagios_core"`, with the inventory file indicating to the host of `ganglia-nagios-server` group.


### Update all contacts in cluster-specific group
Follow the below steps to update the nagios contacts in the cluster-specific group(s).

- Make sure the target contacts have been added via either updating all contacts or adding contacts as described above.
- Set the contacts' information by defining a list variable `cluster_contacts` in the cluster-specific variable file, e.g. `group_vars/goes.yaml`, or via `-e {'cluster_contacts': ['xxx']}` at command line for the single cluster operation.
- Run the playbook with `-e "act=cluster_update"` and `-t "ganglia_nagios_server"`, with the inventory files indicating to the hosts of `ganglia-nagios-server` group **along with all the related clusters' groups**.

**Cautions:** Besides the cluster-specific contacts, other cluster-specific configurations at the nagios server may be updated.


### Add nagios contacts in cluster-specific group
Follow the below steps to add multiple nagios contacts in the cluster-specific group(s).

- Make sure the target contacts have been added via either updating all contacts or adding contacts as described above.
- Add the names of the contacts to be added to the list variable `cluster_contacts` in the cluster-specific variable file, e.g. `group_vars/goes.yaml`, or via `-e {'cluster_contacts': ['xxx']}` at command line for the single cluster operation.
- Run the playbook with `-e "act=cluster_contacts_add"` and and `-t "ganglia_nagios_server"`, with the inventory files indicating to the hosts of `ganglia-nagios-server` group **along with the related clusters' groups**.


### Delete nagios contacts in cluster-specific group
Follow the below steps to delete multiple nagios contacts from the cluster-specific group(s).

- Add the information of the contacts to be deleted to the list variable `cluster_contacts` in the cluster-specific variable file, e.g. `group_vars/goes.yaml`, or via `-e {'cluster_contacts': ['xxx']}` at command line for the single cluster operation.
- Run the playbook with `-e "act=cluster_contacts_delete"` and and `-t "ganglia_nagios_server"`, with the inventory files indicating to the hosts of `ganglia-nagios-server` group **along with the related clusters' groups**.


## Cert/Key Generation Accessing To Kubernetes API-Server
For monitoring hosts running a kubernetes cluster, sometimes accessing to the apiserver to gather information of the kuberentes cluster maybe needed. This project has been integrated a procedure generating the necessary certificates and keys used to access to kubernetes api.

For now, only the authorization for getting node information of kubernetes cluster is granted. See `roles/kube_certs`.


## Default Checking Rules of Nagios
There some checking rules by nagios in this project:

- The `check_ssh` plugin is used to check alive of the hosts. Change the `check_command` field in `check_ganglia_hostgroup_servicegroup.cfg.j2` at `roles/ganglia_nagios_server/templates/` if the other command want to be used.
- The `check_hearteat.sh` provided by ganglia for integrating with nagios is used as a `check_ganglia_heartbeat` checking service to measure the liveness of the gmond agent on the target host, which is added to each host by default.
- All the other checking services on each host depends on the `check_ganglia_heartbeat` to mitigate massive alerts when the monitoring server itself becomes unstable.