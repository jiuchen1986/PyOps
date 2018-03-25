# Automated MAAS Operations via Ansible
This project provides modules, plugins and roles with samples enabling the automation of MAAS operations using Ansible playbook.

## Requirements for Running MAAS related Ansible Modules
### Requirements for python-libmaas
Several Ansible modules for MAAS operations, e.g. the `maas_machine` module, use the `python-libmaas` open source python library provided by the MAAS team which requires `python >= 3.5`, see:[https://github.com/maas/python-libmaas](https://github.com/maas/python-libmaas "python-libmaas on github"), the target hosts running those modules are required to have:

- python >= 3.5
- python-libmaas >= 0.6.0
- set `ansible_python_interpreter=<path to python 3.5 executable script>` for the target host in the inventory file

To avoid the misbehavior of the modules due to update of the `python-libmaas` library, an initiating task for environment setup on the target hosts running the modules is provided with a given package of the `python-libmaas`.

The YAML file of the initiating task locates at `roles/maas_client/tasks/maas_client_init.yaml`, with the required python packages in `roles/maas_client/files/` including:

- pip-9.0.1.tar.gz
- Python-3.5.2.tgz
- python-libmaas-bm-auto.zip
- setuptools-38.4.0.zip

The version of each package could be customized as long as the corresponding packages are put in the `roles/maas_client/files/`. For example, the versions can be indicated in the file `roles/maas_client/defaults/main.yaml` as follows:

    #roles/maas_client/defaults/main.yaml
    
    setuptools_ver: 38.1.0
    pip_ver: 8.0.1
    libmaas_ver: master
    python35_ver: 3.5.4

Then, the packages in `roles/maas_client/files/` should be:

- pip-8.0.1.tar.gz
- Python-3.5.4.tgz
- python-libmaas-master.zip
- setuptools-38.1.0.zip

Please make sure that after being processed by the `unarchive` Ansible module, the name of the archive is in accordance with the name of the package, e.g. the directory unpacked from the package pip-9.0.1.tar.gz should be `pip-9.0.1/`.

It is strongly recommended that keeping the python-libmaas's version and package unchanged.

If there is nothing in the `roles/maas_client/files/`, please manually download the packages from following recommended links:

- pip-9.0.1.tar.gz: [https://pypi.python.org/pypi/pip](https://pypi.python.org/pypi/pip)
- Python-3.5.4.tgz: [https://www.python.org/downloads/release/python-352/](https://www.python.org/downloads/release/python-352/)
- python-libmaas-bm-auto.zip: [https://codeload.github.com/jiuchen1986/python-libmaas/zip/bm-auto](https://codeload.github.com/jiuchen1986/python-libmaas/zip/bm-auto)
- setuptools-38.4.0: [https://pypi.python.org/pypi/setuptools](https://pypi.python.org/pypi/setuptools)

Note that the function of manual installation for python 3.5 in the initiating task hasn't been tested yet. Therefore, python 3.5 needs to be ready and the ansible variable `ansible_python_interpreter` needs to be set correctly to the executable script of python 3.5 for the target host running the MAAS related modules before running any playbook.

The HOWTO of running the initiating task is included in the **Running Sample Ansible Playbook** section.

## Bare Metal Acquire/Deploy/Release on MAAS
To enable the acquisition, the deployment and the releasing of the bare metal machine on MAAS, following staff are given in this repo:


- An Ansible module named `maas_machine` is developed whose code file locates in `library/maas_machine.py` with a webdoc file locates in `webdocs/maas_machine_module.html`.
- Sample tasks for Ansible playbook are provided in the `roles/maas_client/tasks/` including:
  - deploying multiple bare metal machines on MAAS by using `maas_machine` module, with the YAML file of `deploy_machines.yaml`.
  - add the newly deployed machines with group-awareness to the in-memory inventory of the ongoing playbook, with the YAML file of `add_group_machines.yaml`. 
  - release the machines failed during the deployment using `maas_machine` module, with the YAML file of `release_group_clean_machines.yaml`.
  - do somethings on the newly deployed machines.

For the current sample, the task deploying multiple bare metal machines in `deploy_machines.yaml` takes a variable named `deploy_machines` defined in the `roles/maas_client/vars/main.yaml` as follows:


    #roles/maas_client/vars/main.yaml

    deploy_machines:
    - group: group1
      size: 2
      match:
        tags:
        - REMOTE-MGMT
    - group: group2
      size: 2
      match:
        tags:
        - auto-test
      os: ubuntu

The variable indicates that two groups of machines are required to be deployed with sizes of 2 and 3 for respectively. Matching criteria for demanded machines are provided where the tags to be matched are used in this sample. Also the target os for deployed machines could be specified in each group with a default value of 'centos'.

Users can deploy customized groups by modifying the `deploy_machines` variable. Note that the tasks in both `add_group_machines.yaml` and `release_group_clean_machines.yaml` only process the machines in a single group. Therefore, by referring the result of deploying task, a loop going through all groups is needed in the main task, i.e. in the `roles/maas_client/tasks/main.yaml`, and the tasks in above two files are executed in each iteration. 

The HOWTO of running the invovled tasks above is included in the **Running Sample Ansible Playbook** section.

## Running Sample Ansible Playbook
Here is a simple and general guide for running the sample Ansible playbooks in this repo. The HOWTO of using Ansible playbooks is out of the scope, readers can refer to [http://docs.ansible.com/ansible/latest/playbooks.html](http://docs.ansible.com/ansible/latest/playbooks.html "Ansible Playbook Documentation") for fundamental readings.

To run the samples, generally only a host as a client host requesting the MAAS APIs and running MAAS related Ansible modules with a belonged group named `maasclient` is required in the inventory file located in `inventory/inventory` as follows:

    #inventory/inventory

    [maasclient]
    guided-boar ansible_host=10.133.21.190 ansible_user=ubuntu ansible_python_interpreter=/usr/bin/python3.5

Note that the `ansible_python_interpreter` needs to be carefully set to fulfill the requirements of MAAS related Ansible modules.

In addition, to include the developed MAAS related Ansible modules in `library/` into the path searching for modules by Ansible, a configuration file `ansible.cfg` is given as:

    #ansible.cfg
    
    [defaults]
    library = ./library/

In this project, all the needs for MAAS related operations are contained in a single Ansible playbook role named `maas_client` locates in `roles/maas_client/`.
We try best to keep the samples for different subjects, e.g. maas client initiation, bare metal machine deployment and etc., in separate task files. Hence, users can try whatever sample tasks they want by including the demanded tasks in the main task file, i.e. the `roles/maas_client/tasks/main.yaml`, in order. For example, to run the samples of maas client initiation and bare metal machine deployment, the main task file could be organized as:

    #roles/maas_client/tasks/main.yaml

    - name: Init the client host
      include_tasks: maas_client_init.yaml  
      when: init_client
  
    - name: Deploy machines in MAAS
      include_tasks: deploy_machines.yaml

    - name: Add deployed machines to in-memory inventory
      include_tasks: add_group_machines.yaml
      with_items: "{{ deploy_results.results }}"
      loop_control:
        loop_var: deploy_result

    - name: Release clean machines
      include_tasks: release_group_clean_machines.yaml
      with_items: "{{ deploy_results.results }}"
      loop_control:
        loop_var: deploy_result

Conditional variables can also be used to switch on and off an individual task, e.g. the variable `init_client` shown above. These variables can be defined in `roles/maas_client/vars/main.yaml`.

All the variables used in the sample playbooks can be defined in two places, which are `roles/maas_client/default/main.yaml` and `roles/maas_client/vars/main.yaml`. The values in `roles/maas_client/vars/main.yaml` will override the ones in `roles/maas_client/default/main.yaml` when the same variables are defined in the both two files.

Therefore, after finishing the setup of the Ansible environment, the samples can be run by simply following the steps:


1. clone this repo to local
2. setup a proper host as the MAAS client in `inventory/inventory`
3. organize the tasks demanded in the `roles/maas_client/tasks/main.yaml`
4. customize variables with proper values in `roles/maas_client/default/main.yaml` and `roles/maas_client/vars/main.yaml`
5. run `ansible-playbook -i inventory/inventory site.yaml` 