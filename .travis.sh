#!/usr/bin/env bash

TAG="${TRAVIS_TAG:-${TRAVIS_COMMIT}}"

if [ "${1}" == "install" ]; then
    ! docker pull orihoch/ckan-cloud-operator:latest && echo Failed to pull image && exit 1
    ! docker pull orihoch/ckan-cloud-operator:jnlp-latest && echo Failed to pull jnlp image && exit 1
    echo Great Success! && exit 0

elif [ "${1}" == "install-tools" ]; then
    if [ "${K8_PROVIDER}" == "minikube" ]; then
      # Install Minikube
      echo Installing Minikube
      curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
      sudo install minikube-linux-amd64 /usr/local/bin/minikube
      rm minikube-linux-amd64 && minikube version
      echo Minikube Installed Successfully!
    fi

    curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
    chmod +x ./kubectl && sudo mv ./kubectl /usr/local/bin/kubectl
    echo Kubectl Installed Successfully!

    curl https://raw.githubusercontent.com/kubernetes/helm/master/scripts/get > get_helm.sh &&\
     chmod 700 get_helm.sh &&\
     ./get_helm.sh --version "${HELM_VERSION}" &&\
     helm version --client && rm ./get_helm.sh
    echo Helm Installed Successfully!

    sudo apt-get update && sudo apt-get install socat

    echo Instalation Complete && exit 0

elif [ "${1}" == "script" ]; then
    ! docker build --build-arg "CKAN_CLOUD_OPERATOR_IMAGE_TAG=${TAG}" --cache-from orihoch/ckan-cloud-operator:latest -t ckan-cloud-operator . && echo Failed to build image && exit 1
    ! docker build --build-arg "CKAN_CLOUD_OPERATOR_IMAGE_TAG=${TAG}" --cache-from orihoch/ckan-cloud-operator:jnlp-latest -t ckan-cloud-operator-jnlp -f Dockerfile.jenkins-jnlp . && echo Failed to build jnlp image && exit 1
    echo Great Success! && exit 0

elif [ "${1}" == "test" ]; then
    echo Run tests
    docker run --env NO_KUBE_CONFIG=1 --rm --entrypoint '/bin/bash' ckan-cloud-operator -lc 'cd /usr/src/ckan-cloud-operator && ckan-cloud-operator test'
    echo Great Success! && exit 0

elif [ "${1}" == "deploy" ]; then
    docker tag ckan-cloud-operator "orihoch/ckan-cloud-operator:${TAG}" &&\
    echo && echo "orihoch/ckan-cloud-operator:${TAG}" && echo &&\
    docker push "orihoch/ckan-cloud-operator:${TAG}"
    [ "$?" != "0" ] && echo Failed to tag and push && exit 1
    docker tag ckan-cloud-operator-jnlp "orihoch/ckan-cloud-operator:jnlp-${TAG}" &&\
    echo && echo "orihoch/ckan-cloud-operator:jnlp-${TAG}" && echo &&\
    docker push "orihoch/ckan-cloud-operator:jnlp-${TAG}"
    [ "$?" != "0" ] && echo Failed to tag and push jnlp image && exit 1
    if [ "${TRAVIS_BRANCH}" == "master" ]; then
        docker tag ckan-cloud-operator orihoch/ckan-cloud-operator:latest &&\
        echo && echo orihoch/ckan-cloud-operator:latest && echo &&\
        docker push orihoch/ckan-cloud-operator:latest
        [ "$?" != "0" ] && echo Failed to tag and push latest image && exit 1
        docker tag ckan-cloud-operator-jnlp orihoch/ckan-cloud-operator:jnlp-latest &&\
        echo && echo orihoch/ckan-cloud-operator:jnlp-latest && echo &&\
        docker push orihoch/ckan-cloud-operator:jnlp-latest
        [ "$?" != "0" ] && echo Failed to tag and push jnlp latest image && exit 1
    fi
    if [ "${TRAVIS_TAG}" != "" ]; then
        export DEPLOY_JNLP_IMAGE="orihoch/ckan-cloud-operator:jnlp-${TAG}"
        echo "Running Jenkins deploy jnlp job (JNLP_IMAGE=${DEPLOY_JNLP_IMAGE})"
        STATUS_CODE=$(curl -X POST "${JENKINS_JNLP_DEPLOY_URL}" --user "${JENKINS_USER}:${JENKINS_TOKEN}" --data "JNLP_IMAGE=${DEPLOY_JNLP_IMAGE}" -s -o /dev/stderr -w "%{http_code}")
        echo "jenkins jnlp deploy job status code: ${STATUS_CODE}"
        [ "${STATUS_CODE}" != "200" ] && [ "${STATUS_CODE}" != "201" ] && echo Deploy failed && exit 1
    fi
    echo Great Success! && exit 0

else
    echo invalid arguments && exit 1

fi
