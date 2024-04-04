#!/bin/bash
set -e

echo "Restart deployment"

export NAMESPACE=dev-investmann-main-distracted-keldysh

echo "Turning off…"
kubectl scale -n "${NAMESPACE}" --replicas=0 deployment/django
kubectl rollout -n "${NAMESPACE}" --timeout=1m status deployment django
echo "Turned off."

echo "Turning on…"
kubectl scale -n "${NAMESPACE}" --replicas=1 deployment/django
kubectl rollout -n "${NAMESPACE}" --timeout=1m status deployment django
echo "Turned on."
