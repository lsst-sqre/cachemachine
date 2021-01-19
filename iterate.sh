#!/bin/bash -ex
if [ -f dev-chart.tgz ]
then
  CHART=dev-chart.tgz
else
  CHART=cachemachine
fi

helm delete cachemachine-dev -n cachemachine-dev || true
docker build -t lsstsqre/cachemachine:dev .
helm upgrade --install cachemachine-dev $CHART --create-namespace --namespace cachemachine-dev --values dev-values.yaml
