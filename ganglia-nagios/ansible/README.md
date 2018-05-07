# Automated Setup of a Ganglia-Nagios System monitoring Kubernetes cluster
This project provides Ansible playbooks to install Ganglia and Nagios to monitor the infrastructure bearing a single or multiple Kubernetes clusters.

## Required Preparations On The Hosts in Monitoring Clusters
Basically, there is only one requirement needs to be fulfilled on the hosts in the monitoring clusters. **The host acting as the header of a cluster must be able to resolve all the hosts' ip addresses from their fqdns in the clusters**. A cluster header is a host from which the ganglia gmetad on the monitoring server gets metric data of the cluster.

Hence, if the connected DNS server can not help, the mapping between the ip address and the fqdn of each host in the monitoring cluster must be added manually to the `/etc/hosts` file on the cluster header.

## Add Monitoring To A Single Erikube Cluster With The Installed Monitoring Server
This project supports add monitoring to the hosts bearing a single erikube cluster, with a prerequisite that the monitoring server, i.e. a host running nagios-core, ganglia-gmetad and ganglia-web, has been setup.

The actions taken for a single cluster are:


- install ganglia-gmond on each host in the cluster with multicast mode
- indicate ganglia-gmetad on the monitoring server to the head host of the cluster
- add host and service definitions to the nagios-core on the monitoring server related to the metrics of hosts in the cluster

### Prepare an erikube-like inventory file

The operations for a single cluster are designed to be applied using an inventory file from the playbook installing erikube with a little modification. An example of the modified inventory file is given in a file named `erikube_test_hosts`:

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
    
    
    [all:vars]
    single_cluster=earth
    ganglia_nagios_server=localhost
    gmond_systemd_check_services=kubelet,docker,etcd_container
    gmond_cluster_head="10.xxx.xxx.30:8662"
    gmond_multicast_port=8662
    cluster_type=erikube

**Notice:**

- Use explicitly defined the `ansible_host` variable with a ip address for each host if the inventory name is not ip address, or
- Directly use ip addresses for the inventory names.

Compared to the original inventory file used by the erikube installation playbook, a section of `[all:vars]` is added required by running the playbook in this project. The variables defined in `[all:vars]` section are explained as follows:

- **single_cluster**: the name of the current cluster
- **ganglia\_nagios\_server**: a resolvable name or a reachable ip address of the installed monitoring server running ganglia-gmetad, ganglia-web and nagios core
- **gmond\_systemd\_check\_services**: the services needed to be monitored by the gmond on the monitoring host which are managed by the systemd 
- **gmond\_cluster\_head**: the endpoint pointing to the head of the cluster to which the ganglia-gmetad on the monitoring server will connect collecting monitoring data. The endpoint is composed as ip address plus port 
- **gmond\_multicast\_port**: the port each ganglia-gmond on the monitored host is listening on. Must be identical to the one used in the **gmond\_cluster\_head**
- **cluster\_type**: the type of the cluster which can be used to distinguish application of different monitoring metrics. Current supports `kubespray` and `erikube`

Note that these variables also can be transferred to the playbook at running time by typing them in the command line, in case modifying the original inventory file for the erikube installation.

### Configure variables used for installation
The varibles used to configure the ganglia and the nagios during the installation are listed at `group_vars/all.yaml` and `group_vars/ganglia-nagios-server.yaml`. Meanings are described in the files with comments.

For usage of the single cluster scenario:

- comment out the variable named `cluster_list` in `group_vars/all.yaml`
- comment out the variable named `cluster_type` in `group_vars/all.yaml`
- comment out the variable named `gmond_systemd_check_services` in `group_vars/all.yaml`
- leave only `group_vars/all.yaml` and `group_vars/ganglia-nagios-server.yaml` in the `group_vars` directory

### Setup monitoring for the cluster
Completing the above steps, monitoring for the single cluster can be setup by executing:

    ansible-playbook -i path_to_your_erikube-like_inventory_file -e "act=cluster_install" site.yaml

### Update monitoring configuration for the cluster
Updating configurations for a single cluster also is supported, running:

    ansible-playbook -i path_to_your_erikube-like_inventory_file -e "act=cluster_update" site.yaml


### Remove monitoring for the cluster
Actions applied in the installation for a single cluster could be removed by running:

    ansible-playbook -i path_to_your_erikube-like_inventory_file -e "act=cluster_uninstall" site.yaml

or

    ansible-playbook -i path_to_your_erikube-like_inventory_file -e "act=cluster_delete" site.yaml

**Notice**: The `cluster_uninstall` removes the gmond process and related files, including configuration and plugins, from each monitoring host in the cluster, while the `cluster_delete` only removes monitoring actions on the cluster from the monitoring server side. The `cluster_delete` can be used for the scenarios such as that all hosts of a cluster are shutdown, which the following parts in the `site.yaml` needs to be commented out before using:

    # - hosts: clusters
      # gather_facts: yes
      # become: yes
      # pre_tasks:
      # - name: Prepare packages
        # include_tasks: packages_prepare.yaml
        # tags:
        # - gmond
        # when: act == 'install' or act == 'cluster_install'
      # roles:
      # - { role: gmond, tags: ['gmond'] }
      # - { role: ganglia-nagios-client, tags: ['ganglia_nagios'] }

## Add Monitoring To Multiple Clusters With/Without Installing The Monitoring Server
This project supports add monitoring to the hosts bearing multiple kubernetes clusters, with or without the monitoring server has been setup.

The actions taken for multiple clusters are:


- install ganglia-gmetad, rrdtool, ganglia-web, and nagios-core to the monitoring server. If monitoring server has been setup, the former actions will be automatically ignored
- install ganglia-gmond on each host in the clusters with multicast mode
- indicate ganglia-gmetad on the monitoring server to the head hosts of each cluster
- add host and service definitions to the nagios-core on the monitoring server related to the metrics of hosts in the clusters

### List all the cluster names in a variable
Inform the names of all the clusters in a variable named `cluster_list` in `group_vars/all.yaml` as follows:

    # a variable to list all clusters to be monitored, the name of cluster must be identical to the corresponding ansible host group name
    cluster_list:
    - goes
    - earth
    - calipso

Note that the cluster's name must be identical to the name used for the ansible host group related to the cluster.

### Prepare inventory files for the monitoring server and all the clusters
Recommend that inventory files include one file for the monitoring server, with the group name as `ganglia-nagios-server`, and a separate inventory file for each cluster with the group name same to the cluster's name. For example:

    $ ls inventory/
    calipso  earth  ganglia-nagios-server  goes 

An inventory file for a cluster is like:
    
    [calipso]
    10.210.123.[90:92] cluster_role=master
    10.210.123.[93:99] cluster_role=worker

The variable `cluster_role` is used to support cluster role aware nagios service definitions.


### Configure variables used for installation
Besides to `group_vars/all.yaml` and `group_vars/ganglia-nagios-server.yaml`, a separate file for each cluster containing the variables for the hosts in the cluster can be defined. For example:
    
    ls group_vars/
    all.yaml  calipso.yaml  earth.yaml  ganglia-nagios-server.yaml  goes.yaml

A file for a cluster is like:

    # the cluster name used for configuration of gmond, recommended to be identical to the ansible host group name
    gmond_cluster_name: calipso   
    
    # the nodes that are connected by gmetad 
    gmond_cluster_head:
    - "xxx.xxx.xxx.xxx:8663" 
      
    gmond_mode: multicast
    
    gmond_multicast_port: 8663 

For the meanings of variables, please read the comments in the file and refer to the description for the single cluster scenario. **Note that** a variable named `cluster_type` could be indicated if the type of cluster is not `kubespray`.

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