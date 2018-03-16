# Automated Istio Installation on Kubernetes
This project provides Ansible playbooks to install Istio 0.5.0+ on Kubernetes 1.9+.

## Usage
The usage guide here is assumed the files of this playbook have been downloaded to the local.

### Prepare a inventory file
Before using this playbook, a inventory file is required. A host group named `master`  contains the master nodes of the target Kubernetes cluster. For example:

    [master]
    master01
    master02
    master03

An optional host group named `istioinstaller` can be defined in the inventory file too, which contains only a single host with installed `kubectl` and a config file enabling the kubectl to access to the target Kubernetes cluster's api server. For example:

    [istioinstaller]
    master02 

If the `istioinstaller` group is ignored, the first host in the `master` group will be selected and added to `istioinstaller` group on run-time.

### Configure group variables
Several configurable variables for the installation are listed in `group_vars/istioinstaller.yml` as follows:

    istio_version: 0.5.0
    root_dir: /usr/local
    # do not change this
    istio_dir: "{{ root_dir }}/istio-{{ istio_version }}"
    
    # istio or istio-auth
    istio_choice: istio
    
    # auto or manual
    istio_sidecar_inject: auto
    
    kubectl_path: /usr/local/bin
    kubeconfig_path: /etc/kubernetes/admin.conf

- **istio_version**: The version of Istio wanted. 0.5.0, 0.5.1, 0.6.0 have been tested.
- **root_dir**: The parent directory where the package of Istio wanted to be put in.
- **istio_dir**: The root directory where the Istio's files locate. Do not modify this variable.
- **istio_choice**: If `istio`, the Istio without pod-to-pod authentication will be installed, otherwise, `istio-auth` is required.
- **istio\_sidecar\_inject**: If `auto`, the automated sidecar injection will be enabled, otherwise, `manual` is required.
- **kubectl_path**: The path to the `kubectl` executable on the host as installer for Istio.
- **kubeconfig_path**: The path to a configuration file on the installer host that enables the `kubectl` to access to the api server of the target Kubernetes cluster.

### Install Istio
Completing the above steps, Istio could be installed by running:

    ansible-playbook -i path_to_your_inventory_file install.yml 

### Uninstall Istio
A simple playbook for cleaning the changes applied in `install.yml` is provided. To use it just run:

    ansible-playbook -i path_to_your_inventory_file clean.yml

## Notice
- The task `Install istio core components` in playbook `install.yml` may fail sometimes. Just rerun the playbook again, all the tasks should success.
- Do not label the `default` namespace with `istio-injection` on the target Kubernetes cluster before running the installation.
- Any operation beyond the `install.yml` will not be cleaned by running the `clean.yml` playbook.
- Any cleaning of the steps applied in `install.yml` playbook by manual may cause fails when running `clean.yml` playbook.  