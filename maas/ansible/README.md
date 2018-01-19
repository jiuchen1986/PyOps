#Automated MAAS Operations via Ansible
This project provides modules, plugins and roles with samples enabling the automation of MAAS operations using Ansible playbook.

##Requirements for Running MAAS related Ansible Modules
As the current developed and developing Ansible modules for MAAS operations all use the `python-libmaas` open source python library provided by the MAAS team which requires `python >= 3.5`, see:[https://github.com/maas/python-libmaas](https://github.com/maas/python-libmaas "python-libmaas on github"), the target hosts running the MAAS related Ansible modules are required to have:

- python >= 3.5
- python-libmaas >= 0.5.0
- set `ansible_python_interpreter=<path to python 3.5 executable script>` for the target host in the inventory file

To avoid the misbehavior of the modules due to update of the `python-libmaas` library, an initiating task for environment setup on the target hosts running the modules is provided with a given package of the `python-libmaas`.

The YAML file of the initiating task locates at `roles/maas_client/tasks/maas_client_init.yml`, with the required python packages in `roles/maas_client/files/` including:

- pip-9.0.1.tar.gz
- Python-3.5.2.tgz
- python-libmaas-bm-auto.zip
- setuptools-38.4.0.zip

The version of each package could be customized as long as the corresponding packages are put in the `roles/maas_client/files/`. For example, the versions can be indicated in the file `roles/maas_client/defaults/main.yml` as follows:

    #roles/maas_client/defaults/main.yml
    
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

Note that the function of manual installation for python 3.5 in the initiating task hasn't been tested yet. Therefore, python 3.5 needs to be ready and the ansible variable `ansible_python_interpreter` needs to be set correctly to the executable script of python 3.5 for the target host running the MAAS related modules before running any playbook.

The HOWTO of running the initiating task is included in the **Running Sample Ansible Playbook** section.

##Bare Metal Acquire/Deploy/Release on MAAS
To enable the acquisition, the deployment and the releasing of the bare metal machine on MAAS, following staff are given in this repo:


- An Ansible module named `maas_machine` is developed whose code file locates in `library/maas_machine.py` with a webdoc file locates in `webdocs/maas_machine_module.html`.
- Sample tasks for Ansible playbook are provided in the `roles/maas_client/tasks/` including:
  - deploying multiple bare metal machines on MAAS by using `maas_machine` module, with the YAML file of `deploy_machines.yml`.
  - add the newly deployed machines with group-awareness to the in-memory inventory of the ongoing playbook, with the YAML file of `add_group_machines.yml`. 
  - release the machines failed during the deployment using `maas_machine` module, with the YAML file of `release_group_clean_machines.yml`.
  - do somethings on the newly deployed machines.

The HOWTO of running the invovled tasks above is included in the **Running Sample Ansible Playbook** section.

##Running Sample Ansible Playbook