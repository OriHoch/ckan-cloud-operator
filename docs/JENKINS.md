# ckan-cloud-operator UI using Jenkins


## Prerequisites

* Jenkins server
* ckan-cloud-operator kubeconfig file


## Deploy a Jenkins JNLP Node

This method can be used to add additional nodes as well, just increment the number suffix

Manage Jenkins > Manage Nodes > New Node:

* name: `jenkins-jnlp-node-1`
* Remote root directory: `/home/jenkins/agent`
* Number of executors: `1` It's recommended to keep this at `1` and add more nodes if you need more scale
* Use as much as possible (this will be the default node for all Jenkins jobs)
* Launch agent by connecting it to the master

Manage Jenkins > Manage Nodes > jenkins-jnlp-node-1

* Copy the secret token from the commands displayed on the page

In Rancher: Create a secret named `jenkins-jnlp-node-1` in namespace `default`:

* JENKINS_AGENT_NAME: `jenkins-jnlp-node-1`
* JENKINS_SECRET: The secret token copied from the Jenkins node
* JENKINS_URL: `http://JENKINS_JNLP_IP:JENKINS_JNLP_NODE_PORT` (Internal IP for the master Jenkins instance which serves port 80 for the web endpoint and port 50000 for the JNLP endpoint)

In Rancher: Deploy the JNLP node:

* Name: `jenkins-jnlp-node-1`
* image: `uumpa/ckan-cloud-operator-jenkins-jnlp:bd9db3753d168284330646e0259002ac93293eaa`
* envFrom: secret `jenkins-jnlp-node-1`
* volumes: Add from secret:
  * Should have a secret containing the ckan-cloud-operator kubeconfig file
  * The secret should be mounted in container at `/etc/ckan-cloud/.kube-config`
  * File mode should be set to `444`


## Using Jenkins

Label the jnlp node accordingly and target jobs on it

The jobs can execute shell using either Bash or Python3

Example Bash job:

```
#!/usr/bin/env bash
ckan-cloud-operator routers list
```

Example Python3 job:

```
#!/usr/bin/env python3
from ckan_cloud_operator import kubectl
print(kubectl.get('ckancloudckancinstance'))
```

## Scripts

See [scripts/README.md](../scripts/README.md)
