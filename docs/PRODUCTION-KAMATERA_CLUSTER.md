# Creating a production cluster using Kamatera Cloud

Stable continuous integration and deployment platform from scratch based on Rancher, Kubernetes and Kamatera cloud.

Using this method allows to get a fully operational cluster which you can use to expose services and run complex workloads.

## Prepare a Domain with DNS services

This guide requires a domain name configured on cloudflare which you can set DNS rules on.

Create a free account and add the domains to Cloudflare:  https://www.cloudflare.com/

At this point you should wait a few hours until the site is added to Cloudflare.

We will use the Cloudflare API to set subdomains and register SSL for this domain.

## Prerequisites

* Docker - https://docs.docker.com/get-started/
* Kamatera Cloud account - https://console.kamatera.com/create 

## Create a private network

This is used for secure access to private NFS / storage / DB servers

From the Kamatera console web-ui:

* My Cloud > Networks > Create New Network:
* VLAN Name: my-cluster
* IP Address Scope: 172.16.0.0 / 23
* Gateway: No Gateway
* DNS: leave empty
* Create Network

## Create the management server

The management server will run some central components such as Rancher, Jenkins workloads, load balancer and NFS for storage.
The components can be separated later to different servers if needed.

Pull the Docker image to create the server:

```
CKAN_CLOUD_OPERATOR_MINIMAL_IMAGE="orihoch/ckan-cloud-operator-minimal@sha256:b6ce7590006b6fe7eae8d5914c5e1f2fae91f9fdcb83a2af56b43bd6ff37faf4"
docker pull "${CKAN_CLOUD_OPERATOR_MINIMAL_IMAGE}"
docker tag "${CKAN_CLOUD_OPERATOR_MINIMAL_IMAGE}" ckan-cloud-operator-minimal
```

(Alternatively - build the image from checkout of ckan-cloud-operator: `docker build -t ckan-cloud-operator-minimal -f Dockerfile.minimal .`)

The following ckan-cloud-operator command will start interactive creation of the management server,
follow the instructions on the terminal,
the whole process takes ~15 minutes:

```
docker run -it ckan-cloud-operator-minimal cluster kamatera create-management-server --interactive
```

Store the output of the terminal session securely, it contains all required secrets and installation details which is useful for debugging and recovery.

## Initialize ckan-cloud-operator

The create server output should contain the kubeconfig file used to authenticate with the cluster, it looks like this:

```
apiVersion: v1
clusters:
- cluster:
    server: https://REDACTED/k8s/clusters/REDACTED
  name: REDACTED
contexts:
- context:
    cluster: REDACTED
    user: REDACTED
  name: REDACTED
current-context: REDACTED
kind: Config
preferences: {}
users:
- name: REDACTED
  user:
    token: kubeconfig-user-REDACTED
```

Copy the kubeconfig file and store in a local file

Set the kubeconfig to environment variable:

```
export KUBECONFIG=/path/to/kubeconfig
```

You can now interact with the cluster directly using kubectl:

```
kubectl get nodes
```

Install ckan-cloud-operator-env

```
curl -s https://raw.githubusercontent.com/OriHoch/ckan-cloud-operator/master/ckan-cloud-operator-env.sh \
| sudo tee /usr/local/bin/ckan-cloud-operator-env >/dev/null && sudo chmod +x /usr/local/bin/ckan-cloud-operator-env
```

Pull latest image:

```
ckan-cloud-operator-env pull latest
```

(Or, build, from a checkout of ckan-cloud-operator: `./ckan-cloud-operator-env.sh build`)

Add environment

```
sudo ckan-cloud-operator-env add my-cluster $KUBECONFIG ckan-cloud-operator
```

Get cluster info:

```
ckan-cloud-operator cluster info
```

Initialize the cluster:

```
ckan-cloud-operator cluster initialize --interactive --cluster-provider kamatera --operator-image orihoch/ckan-cloud-operator:latest
```

Start a bash shell to run commands from an operator environment:

```
ckan-cloud-operator bash
```

Use kubectl:

```
kubectl get nodes
``` 

## Initialize NFS storage

```
ckan-cloud-operator storage initialize --interactive --provider-id kamatera-nfs
```

## Install nfs-common on all cluster nodes

This is required for proper NFS support, should be done whenever new nodes are added to the cluster

```
ckan-cloud-operator cluster kamatera ssh-rancher-nodes "apt-get update && apt-get install -y nfs-common"
```

## Initialize Private Docker Registry

```
ckan-cloud-operator cluster kamatera initialize-docker-registry
```

## Secure NodePorts

We will be using Node Ports to expose services, to secure this setup, we will restrict Node Ports to only be accessible on the internal network

* Rancher web UI > Edit Cluster > Edit as yaml
* At the bottom of the file, set the following for kubeproxy:

```
kubeproxy:
      extra_args:
        nodeport-addresses: 172.16.0.0/23
```

* Save and wait for cluster to update

## Management Server Firewall

We will setup a simple firewall on the management server

SSH to the management server:

```
ckan-cloud-operator cluster kamatera ssh-management-machine
```

Run from the management server SSH session:

```
ufw allow 22 &&\
ufw allow 443 &&\
ufw allow 80 &&\
ufw allow from 172.16.0.0/23 &&\
ufw --force enable &&\
ufw status numbered
```

This allows access to Ports 22, 443, 80 and to any port from the internal network

You can test by trying to access the NFS port 111 - should should be blocked from an external network

```
telnet `ckan-cloud-operator cluster kamatera management-public-ip` 111
```

But, from the management machine it will work

```
ckan-cloud-operator cluster kamatera ssh-management-machine telnet `ckan-cloud-operator cluster kamatera management-public-ip` 111
```

## Expose docker registry internally

* Rancher web UI > Cluster > Default > Service Discovery > Add Record
* Name: `docker-registry-nodeport`
* Resolves to: One or more workloads
* Target Workload: `docker-registry`
* Advanced Options:
* As A: `NodePort`
* Port Mapping: Name: 5000, Service Port: 5000, Target Port: Same as Service Port, Node Port: Random

Get the node internal IP and node port:

```
ckan-cloud-operator cluster kamatera nodeport-url docker-registry-nodeport
```

To make sure node port is exposed internally, get the external IP and try to access this port

```
curl http://EXTERNAL_IP:NODE_PORT
```

From the management server you can access the internal IP:

```
ckan-cloud-operator cluster kamatera ssh-management-machine curl http://INTERNAL_IP:NODE_PORT
```

## Expose Docker Registry externally

The Docker Registry is protected with a password, so we can expose it externally.

However, it uses HTTP auth which is not encrypted, so to expose publicly we need SSL

Following command adds a route to router `infra-1` which is configured to work using Nginx on the management server

It creates the route from external domain `docker-registry.ROOT_DOMAIN` to INTERNAL_IP:NODE_PORT (internal IP of any node with the node port for the docker-registry-nodeport service)

```
ckan-cloud-operator routers create-backend-url-subdomain-route infra-1 docker-registry http://`ckan-cloud-operator cluster kamatera nodeport-url docker-registry-nodeport` DOCKER_REGISTRY_SUBDOMAIN --client-max-body-size 10240M
```

Login to the Docker Registry from an external IP:

```
docker login https://DOCKER_REGISTRY_SUBDOMAIN.ROOT_DOMAIN
```

Push a test image to the registry:

```
docker pull hello-world && docker tag hello-world DOCKER_REGISTRY_SUBDOMAIN.ROOT_DOMAIN/foobar/hello-world
docker push DOCKER_REGISTRY_SUBDOMAIN.ROOT_DOMAIN/foobar/hello-world
```

Pull from the registry

```
docker pull DOCKER_REGISTRY_SUBDOMAIN.ROOT_DOMAIN/foobar/hello-world
```

Try to pull while logged-out, it should fail:

```
docker logout DOCKER_REGISTRY_SUBDOMAIN.ROOT_DOMAIN
docker pull DOCKER_REGISTRY_SUBDOMAIN.ROOT_DOMAIN/foobar/hello-world
```

## Deploy Jenkins

Create a persistent volume in the management server:

```
ckan-cloud-operator cluster kamatera ssh-management-machine "mkdir -p /srv/default/jenkins && chown 1000:1000 /srv/default/jenkins"
```

Using Rancher Web UI, deploy a new workload:

* Name: `jenkins`
* Scalable deployment of 1 pods
* Docker Image: `jenkins/jenkins:lts`
* Namespace: `default`
* Port Mapping: Add Port:
  * Name: `web`, container port: `8080`, As a: NodePort, listening port: random
* Add Volume: Add persistent volume claim:
  * Name: `jenkins`
  * provision a new volume
  * storage class: `nfs-client`
  * Capacity: 100 GiB
  * Mount Point: `/var/jenkins_home`

Get the internal node port url:

```
ckan-cloud-operator cluster kamatera nodeport-url jenkins-nodeport
```

Add a route:

```
ckan-cloud-operator routers create-backend-url-subdomain-route infra-1 jenkins http://INTERNAL_NODE_IP:JENKINS_NODE_PORT JENKINS_SUBDOMAIN
```

Access Jenkins at https://JENKINS_SUBDOMAIN.ROOT_DOMAIN and install with suggested plugins

To get the Jenkins initial admin password:

```
ckan-cloud-operator cluster kamatera ssh-management-machine

cd /srv/default/default-jenkins-<TAB><TAB>
cat secrets/initialAdminPassword
```

Install Jenkins Agent on the management machine:

```
ckan-cloud-operator cluster kamatera ssh-management-machine -- mkdir -p /var/jenkins_agent &&\
ckan-cloud-operator cluster kamatera ssh-management-machine -- add-apt-repository ppa:openjdk-r/ppa -y &&\
ckan-cloud-operator cluster kamatera ssh-management-machine -- apt-get install openjdk-8-jdk -y
```

From Jenkins web UI > Nodes > Add New Node:

* Node name: `management`
* Permanent Agent
* Remote root directory: `/var/jenkins_agent`
* Labels: `management`
* Only build jobs matching label expression
* Launch agent via SSH - 
  * host: the Rancher domain
  * using the private SSH key for the management machine
    * `ckan-cloud-operator cluster kamatera print-management-machine-secrets --key id_rsa`

Nodes > Master > Configure:

  * Usage: Only build jobs matching label expression

Set an environment variable with a config path for the cluster:

```
export CLUSTER_CONFIG_PATH=/etc/my-cluster-id
```

Copy the cluster KUBECONFIG file to the config path on the management server:

```
ckan-cloud-operator cluster kamatera ssh-management-machine -- mkdir -p $CLUSTER_CONFIG_PATH &&\
ckan-cloud-operator cluster kamatera scp-to-management-machine $KUBECONFIG $CLUSTER_CONFIG_PATH/.kubeconfig
```

Setup the management server to run ckan-cloud-operator using this config path:

```
ckan-cloud-operator cluster kamatera ssh-management-machine -- curl -s https://raw.githubusercontent.com/OriHoch/ckan-cloud-operator/kamatera-cluster-rc1/ckan-cloud-operator-env.sh -o /usr/local/bin/ckan-cloud-operator-env &&\
ckan-cloud-operator cluster kamatera ssh-management-machine -- chmod +x /usr/local/bin/ckan-cloud-operator-env &&\
ckan-cloud-operator cluster kamatera ssh-management-machine -- ckan-cloud-operator-env pull latest &&\
ckan-cloud-operator cluster kamatera ssh-management-machine -- ckan-cloud-operator-env add default $CLUSTER_CONFIG_PATH/.kubeconfig ckan-cloud-operator
```

## Add a route with an external domain

Register the DNS to point to the management server public IP

Add the route:

```
ckan-cloud-operator routers create-backend-url-subdomain-route infra-1 ROUTE_NAME `ckan-cloud-operator cluster kamatera nodeport-url SERVICE_NAME --namespace SERVICE_NAMESPACE` SUB_DOMAIN EXTERNAL_ROOT_DOMAIN
```

## Create Jenkins Jobs

### ckan-cloud-operator-build

This job update the ckan-cloud-operator image which is used locally form the management server

* Restrict where this project can run: Label Expression: `management`
* Source code management: `git`
* Repository URL: `https://github.com/OriHoch/ckan-cloud-operator.git`
* Execute shell: `docker build -t ckan-cloud-operator .`

### build app

An example job to build and push an app to the private registry

* Restrict where this project can run: Label Expression: `management`
* Source code management: `git`
* Repository URL: `repository URL of the app to deploy` 
* Use secret text or file: add binding: secret text
  * Variable: `DOCKER_REGISTRY_SECRETS`
  * Specific Credentials: Add a Secret text, description: `docker-registry-secrets` with the following secret:
```
export DOCKER_DOMAIN=(The domain name to the docker registry, e.g. docker-registry.my-domain.com)
export DOCKER_USERNAME=(Docker registry username)
export DOCKER_PASSWORD=(Docker registry password)
```
* Execute shell:

```
#!/usr/bin/env bash
eval "${DOCKER_REGISTRY_SECRETS}"
echo $DOCKER_PASSWORD | docker login --password-stdin --username $DOCKER_USERNAME $DOCKER_DOMAIN
```

### Run ckan-cloud-operator commands

Add the CLUSTER_CONFIG_PATH you set previously as a Jenkins global env var:

* Jenkins > Manage Jenkins > System > add global environment variable
  * `CLUSTER_CONFIG_PATH` = `/etc/my-cluster-id`

Add a job:

```
docker run \
    -v "${CLUSTER_CONFIG_PATH}/.kubeconfig:/etc/ckan-cloud/.kube-config" \
    -v "`pwd`/.data:/etc/ckan-cloud/data" \
    -e CKAN_CLOUD_OPERATOR_SRC=/usr/src/ckan-cloud-operator/ckan_cloud_operator \
    -e DATA_PATH=/etc/ckan-cloud/data \
    --entrypoint bash ckan-cloud-operator -c 'source ~/.bashrc;
ckan-cloud-operator cluster info &&\
kubectl get nodes
'
```

### scripts

the scripts/ directory contains high-level scripts which can run on Jenkins

Create a job for each script:

* Name: same as script name (without extension)
* Restrict to run on: `management`
* Check script source for args and define in job parameters
* Execute shell:

(Replace the FOO/BAR env vars with the actual arg names defined in the script / job parameters)

For .py scripts:

```
docker run \
    -v "${CLUSTER_CONFIG_PATH}/.kubeconfig:/etc/ckan-cloud/.kube-config" \
    -v "`pwd`/.data:/etc/ckan-cloud/data" \
    -e CKAN_CLOUD_OPERATOR_SRC=/usr/src/ckan-cloud-operator/ckan_cloud_operator \
    -e DATA_PATH=/etc/ckan-cloud/data \
    -e FOO -e BAR \
    --entrypoint bash ckan-cloud-operator -c "source ~/.bashrc; python3 \"/usr/src/ckan-cloud-operator/scripts/${JOB_NAME}.py\""
```

For .sh scripts:

```
docker run \
    -v "${CLUSTER_CONFIG_PATH}/.kubeconfig:/etc/ckan-cloud/.kube-config" \
    -v "`pwd`/.data:/etc/ckan-cloud/data" \
    -e CKAN_CLOUD_OPERATOR_SRC=/usr/src/ckan-cloud-operator/ckan_cloud_operator \
    -e DATA_PATH=/etc/ckan-cloud/data \
    -e FOO -e BAR \
    --entrypoint bash ckan-cloud-operator -c "source ~/.bashrc; bash \"/usr/src/ckan-cloud-operator/scripts/${JOB_NAME}.sh\""
```

Check the script for any output data and add a post build archive artifacts action:

* files to archive: `.data/**/*`
