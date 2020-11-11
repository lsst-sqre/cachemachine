#!/bin/bash -ex
helm delete --purge cachemachine-dev || true
docker build -t lsstsqre/cachemachine:dev .
helm upgrade --install cachemachine-dev cachemachine-0.1.0.tgz --namespace cachemachine-dev --values dev-values.yaml
