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

The following ckan-cloud-operator command will start interactive creation of the management server,
follow the instructions on the terminal,
the whole process takes ~15 minutes:

```
docker run -it orihoch/ckan-cloud-operator-minimal cluster kamatera create-management-server --interactive
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




Start a bash shell to run commands from an operator environment:

```
ckan-cloud-operator bash
```

Enable Bash completion:

```
eval "$(ckan-cloud-operator bash-completion)"
```

Use Bash completion:

```
ckan-cloud-operator <TAB><TAB>
```

Use available binaries:

```
kubectl get nodes
``` 

```
curl -s https://raw.githubusercontent.com/OriHoch/ckan-cloud-operator/master/ckan-cloud-operator-env.sh \
| sudo tee /usr/local/bin/ckan-cloud-operator-env >/dev/null && sudo chmod +x /usr/local/bin/ckan-cloud-operator-env
```
Add an environment (sudo is required to install the executable):
sudo ckan-cloud-operator-env add my-environment /path/to/kubeconfig
Verify that you are connected to the right cluster
ckan-cloud-operator cluster info



Build the ckan-cloud-operator minimal Dockerfile:

```
docker build -t ckan-cloud-operator-minimal -f Dockerfile.minimal .
```

Start a shell session using the image:

```
docker run -it ckan-cloud-operator-minimal cluster initialize --interactive --cluster-provider kamatera
```