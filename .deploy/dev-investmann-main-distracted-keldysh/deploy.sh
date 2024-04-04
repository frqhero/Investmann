#!/bin/bash
set -e

echo "Updating deployment image and run jobs"
echo

docker build ../../ -t cr.yandex/crppvo9bpgsbl1m4dccq/django:latest -t cr.yandex/crppvo9bpgsbl1m4dccq/django:$(git rev-parse HEAD)
docker push --all-tags cr.yandex/crppvo9bpgsbl1m4dccq/django
sleep 5

export COMMIT_HASH=$(git rev-parse HEAD)
export NAMESPACE=dev-investmann-main-distracted-keldysh

cd `dirname "$0"`
cat configmap.yaml | sed "s/<COMMIT_HASH>/$COMMIT_HASH/" | kubectl apply -f -
kubectl apply -f psql_root_crt.yaml

cat migrate.yaml | sed "s/<COMMIT_HASH>/$COMMIT_HASH/" | kubectl create -f -

echo "Wait till Django migration completion…"
kubectl wait --for=condition=complete -n "$NAMESPACE" --timeout=60s job/django-migrate
echo "Django migration was completed."

cat django.yaml | sed "s/<COMMIT_HASH>/$COMMIT_HASH/" | kubectl apply -f -

echo "Wait till Django deployment rollout…"
kubectl rollout -n "$NAMESPACE" --timeout=60s status deployment django
echo "Django deployment rollout was succeded."

cat clearsessions.yaml | sed "s/<COMMIT_HASH>/$COMMIT_HASH/" | kubectl apply -f -

echo
echo "Project deployed successfully"
echo "Commit hash of deployed version: $COMMIT_HASH"
