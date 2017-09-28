Linode Deployment Tool
======================

Overview
--------
Deploy a node in Linode VPS cloud using simple configuration file `linode.settings`, where you can specify multiple nodes to be deployed by specifying node deployment sections and simply run `python linode.py deploy [deployment-section-name]`. This tool also provides the bootstrap template script, where `%{variable}` will be replaced with your options defined in node section. Currently, Bootstrap template script installed puppet agent, registered to given puppet master and enables puppet agent on boot.

Install required libraries
--------------------------
```shell
# easy_install apache-libcloud
# easy_install paramiko
```

How to use?
-----------
+ Retreive your Linode account API key and assign it to `api_key` option in the `[main]` section.
+ Issue some commands to check your api key `python linode.py listnodes`, `python linode.py help`.
+ Edit `linode.settings` and create a new node section with deployment options. (See `linode.settings.sample`  for deployment options]
+ Edit your bootstrap script or leave it which by default installs puppet agent and registers to given puppet master in the node section.
+ Check your configuration files and settings by issuing `python linode.py configtest` command.
+ To deploy your node issue `python linode.py deploy [section_name]` command, where `[section_name]` will be your node section name defined `linode.settings` configuration file. (eg: devsupport-infra).

Supported template variables
----------------------------
+ `%{hostname}` will be replaced with `hostname` option defined in node deployment section.

**For more info visit:** http://api.linode.com, http://libcloud.apache.org
