#!/bin/bash -ex

curl -X POST -H "Content-Type: application/json" -d "@jupyter.json" https://minikube.lsst.codes:31337/cachemachine/
