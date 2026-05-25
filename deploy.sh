#!/bin/bash
# Build, push, and deploy the backend to ECS.
# Usage: ./deploy.sh
set -euo pipefail

export DOCKER_HOST=unix://${HOME}/.docker/desktop/docker.sock

REGION=us-east-1
ECR_URI=730558614455.dkr.ecr.us-east-1.amazonaws.com/mbta-casino
CLUSTER=MbtaCasinoAppStack-ClusterEB0386A7-tnRKQNNPKZ8A
API_SERVICE=MbtaCasinoAppStack-ApiServiceC9037CF0-fv9tBfkhehbK
CELERY_SERVICE=MbtaCasinoAppStack-CeleryService4BB6B43F-7aAwzyLggvif

echo "==> Authenticating with ECR..."
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ECR_URI"

echo "==> Building image..."
docker build -t "$ECR_URI:latest" ./backend

echo "==> Pushing image..."
docker push "$ECR_URI:latest"

echo "==> Forcing new deployment..."
aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$API_SERVICE" \
  --force-new-deployment \
  --region "$REGION" \
  --query 'service.deployments[0].{status:status,taskDef:taskDefinition}' \
  --output table

aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$CELERY_SERVICE" \
  --force-new-deployment \
  --region "$REGION" \
  --query 'service.deployments[0].{status:status,taskDef:taskDefinition}' \
  --output table

echo "==> Waiting for API service to stabilise (this takes a few minutes)..."
aws ecs wait services-stable \
  --cluster "$CLUSTER" \
  --services "$API_SERVICE" \
  --region "$REGION"

echo "==> Done. API service is stable."
