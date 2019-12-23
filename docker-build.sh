#!/usr/bin/env bash

date +%Y-%m-%d\ %H:%M | tee /etc/ckan-cloud-operator-build-info
hostname | tee -a /etc/ckan-cloud-operator-build-info

set -o pipefail

(
  echo == system dependencies &&\
  apt-get update && apt-get install -y gnupg bash-completion build-essential jq python-pip postgresql nano dnsutils apache2-utils &&\
  /usr/bin/pip2 install pyopenssl &&\
  echo == kubectl &&\
  wget -q https://dl.k8s.io/v1.16.4/kubernetes-client-linux-amd64.tar.gz &&\
  tar -xzf kubernetes-client-linux-amd64.tar.gz &&\
  mv kubernetes/client/bin/kubectl /usr/local/bin/ && chmod +x /usr/local/bin/kubectl &&\
  echo == helm &&\
  wget -q https://get.helm.sh/helm-v3.0.2-linux-amd64.tar.gz &&\
  tar -xzf helm-v3.0.2-linux-amd64.tar.gz &&\
  mv linux-amd64/helm /usr/local/bin/ && chmod +x /usr/local/bin/helm && rm -rf linux-amd64 &&\
  true
) >/dev/stdout 2>&1 | tee -a /etc/ckan-cloud-operator-build-info

[ "$?" != "0" ] && exit 1
echo Great Success! && exit 0
