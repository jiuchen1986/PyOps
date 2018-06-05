# Automated Istio Installation on Kubernetes
This project provides Ansible playbooks to install Istio 0.5.0+ on Kubernetes 1.9+.
The current supported version of Istio:

- 0.5.0
- 0.5.1
- 0.6.0
- 0.7.0
- 0.7.1
- 0.8.0

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

If the `istioinstaller` group is ignored or empty, the first host in the `master` group will be selected and added to `istioinstaller` group on run-time.

For **specific user names and passwords related to ssh connections and sudo**, using `ansible_user`, `ansible_ssh_pass`, `ansible_become_pass` as group variables to specify in the inventory file. For example:

    [master]
    master01
    master02
    
    [master:vars]
    ansible_user=centos
    ansible_become_pass=password

### Configure group variables
Several configurable variables for the installation are listed in `group_vars/all.yaml` as follows:

    istio_version: 0.7.1
    root_dir: /usr/local
    # do not change this
    istio_dir: "{{ root_dir }}/istio-{{ istio_version }}"
    
    # istio or istio-auth
    istio_choice: istio
    
    # auto or manual
    istio_sidecar_inject: auto
    
    # indicate how to get the kubectl script and the kubeconfig file
    # local: files are on istio installer locating at to where the kubectl_path and kubeconfig_path indicate
    # fetch: files are on a remote host locating at to where the remote_kubectl_path and remote_kubeconfig_path indicate, and will be copyed to the istio installer
    # url:   files can be downloaded from urls, which are descirbed by the url_kubectl and the url_kubeconfig, and saved to the istio installer
    file_get: local
    
    # path to the directory where the kubectl executable script locates or to be saved when it is fetched from remote
    kubectl_path: /usr/local/bin
    # path to the kubeconfig file for the kubectl locates or to be saved when it is fetched from remote
    kubeconfig_path: /etc/kubernetes/admin.conf
    
    # a remote host keeping the kubectl and the kubeconfig files
    remote_file_host: c01-h01-master.maas
    # user name to login to the remote host with ssh
    remote_file_host_user: centos
    # path to the directory where the kubectl executable script locates at a remote host
    remote_kubectl_path: /usr/local/bin
    # path to the kubeconfig file for the kubectl locates at a remote host
    remote_kubeconfig_path: /etc/kubernetes/admin.conf
    
    # url where the kubectl executable script can be downloaded
    url_kubectl: http://example.com/kubectl
    # url where the kubeconfig file for the kubectl can be downloaded
    url_kubeconfig: http://example.com/kubeconfig
    
    # path to the manifest file of API server on the master nodes
    api_server_manifest: /etc/kubernetes/manifests/kube-apiserver.yaml

- **istio_version**: The version of Istio wanted. 0.5.0, 0.5.1, 0.6.0, 0.7.1 have been tested.
- **root_dir**: The parent directory where the package of Istio wanted to be put in.
- **istio_dir**: The root directory where the Istio's files locate. Do not modify this variable.
- **istio_choice**: If `istio`, the Istio without pod-to-pod authentication will be installed, otherwise, `istio-auth` is required.
- **istio\_sidecar\_inject**: If `auto`, the automated sidecar injection will be enabled, otherwise, `manual` is required.
- **file_get**: Indicate where to get the `kubectl` and the `kubeconfig` file, including `local` that the files locate on the host running as `istioisntaller`, `fetch` which indicates fetching files from a remote host, and `url` indicating downloading files from a url. **Currently only `local` is fully tested, don't use others.**
- **kubectl_path**: The path to the directory containing the `kubectl` executable on the host as installer for Istio when `file_get` is `local`.
- **kubeconfig_path**: The path to a configuration file on the installer host when `file_get` is `local`, that enables the `kubectl` to access to the api server of the target Kubernetes cluster.
- **api\_server\_manifest**: The path to the manifest file of apiserver on the master hosts.

**Notice: please ensure that the group variables of `kubectl_path`, `kubeconfig_path`, and `api_server_manifest` are correctly configured.**

### Install Istio
Completing the above steps, Istio could be installed by running:

    ansible-playbook -i path_to_your_inventory_file install.yaml 

### Uninstall Istio
A simple playbook for cleaning the changes applied in `install.yaml` is provided. To use it just run:

    ansible-playbook -i path_to_your_inventory_file clean.yaml
Note that the `clean.yaml` will remove the 'MutatingAdmissionWebhook' and the 'ValidatingAdmissionWebhook' from the admission control flags of the api server by default. If these two flags are needed to be kept, set the variables below in `clean_vars.yaml` to 'no':

    remove_mut_flag: yes
    remove_val_flag: yes

## Cautions
- The task `Install istio core components` in playbook `install.yaml` may fail sometimes. Just rerun the playbook again, all the tasks should success.
- Do not label the `default` namespace with `istio-injection` on the target Kubernetes cluster before running the installation.
- Any operation beyond the `install.yaml` will not be cleaned by running the `clean.yaml` playbook.
- Any cleaning of the steps applied in `install.yaml` playbook by manual may cause fails when running `clean.yaml` playbook.  