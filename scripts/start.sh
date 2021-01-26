#!/bin/bash -ex

curl --insecure -X POST -H "Content-Type: application/json" -d "@jupyter.json" https://minikube.lsst.codes/cachemachine/
curl --insecure -X POST -H "Content-Type: application/json" -d "@simple.json" https://minikube.lsst.codes/cachemachine/
