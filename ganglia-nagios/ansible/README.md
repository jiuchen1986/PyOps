# Automated Setup of a Ganglia-Nagios System monitoring Kubernetes cluster
This project provides Ansible playbooks to install Ganglia and Nagios to monitor the infrastructure bearing a single or multiple Kubernetes clusters.

## Add monitoring to a single cluster with the monitoring server installed
This project supports add monitoring to the hosts bearing a single kubernetes cluster, with a prerequisite that the monitoring server, i.e. a host running nagios-core, ganglia-gmetad and ganglia-web, has been setup.

The actions taken for a single cluster are:


- install ganglia-gmond on each host in the cluster with multicast mode
- indicate ganglia-gmetad on the monitoring server to the head host of the cluster
- add host and service definitions to the nagios-core on the monitoring server related to the metrics of hosts in the cluster

### Prepare an erikube-like inventory file

The operations for a single cluster are designed to be applied using an inventory file from the playbook installing erikube with a little modification. A example of the modified inventory file is given in a file named `erikube_test_hosts`:

    node1 ansible_host=10.210.127.30
    node2 ansible_host=10.210.127.31
    node3 ansible_host=10.210.127.32
    node4 ansible_host=10.210.127.33
    node5 ansible_host=10.210.127.34
    
    [master]
    node1
    
    [etcd]
    node1
    
    [worker]
    node2
    node3
    node4
    node5
    
    [ingress_lb]
    
    [ganglia-nagios-server]
    localhost
    
    [all:vars]
    single_cluster=earth
    gmond_cluster_head="10.210.127.30:8662"
    gmond_multicast_port=8662

Insure that explicitly define the `ansible_host` variable for each host using the ip address. 

Compared to the original inventory file used by the erikube installation playbook, sections of `[ganglia-nagios-server]` and `[all:vars]` are added required by running the playbook in this project.

The host in the `ganglia-nagios-server` group points to the monitoring server. And the variables defined in `[all:vars]` section are explained as follows:

- **single_cluster**: the name of the current cluster
- **gmond\_cluster\_head**: the endpoint pointing to the head of the cluster to which the ganglia-gmetad on the monitoring server will connect collecting monitoring data. The endpoint is composed as ip address plus port 
- **gmond\_multicast\_port**: the port each ganglia-gmond on the monitored host is listening on. Must be identical to the one used in the **gmond\_cluster\_head**

### Configure variables used for installation
The varibles used to configure the ganglia and the nagios during the installation are listed at `group_vars/all.yaml` and `group_vars/ganglia-nagios-server.yaml`. Meanings are described in the files with comments.

For usage of the single cluster scenario:

- comment the variable named `cluster_list` in `group_vars/all.yaml`
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


## Add monitoring to multiple clusters with/without installing the monitoring server
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

For current implementations, the variable `cluster_role` is not used.


### Configure variables used for installation
Besides to `group_vars/all.yaml` and `group_vars/ganglia-nagios-server.yaml`, a separate file for each cluster containing the variables for the hosts in the cluster can be defined. For example:
    
    ls group_vars/
    all.yaml  calipso.yaml  earth.yaml  ganglia-nagios-server.yaml  goes.yaml

A file for a cluster is like:

    # the cluster name used for configuration of gmond, recommended to be identical to the ansible host group name
    gmond_cluster_name: calipso   
    
    # the nodes that are connected by gmetad 
    gmond_cluster_head:
    - "10.210.123.90:8663" 
      
    gmond_mode: multicast
    
    gmond_multicast_port: 8663 

For the meanings of variables, please read the comments in the file and refer to the description for the single cluster scenario.

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