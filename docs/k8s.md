# Kubernetes

Prerequisite: build and push the Docker image first (see [docker.md](./docker.md)):

```bash
docker build -t my-tw-site:latest .
docker push <your-registry>/my-tw-site:latest
```

Update `image:` in `k8s/deployment.yaml` to point at your pushed image, then apply:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml   # only if you have an Ingress controller set up
```

## What's included

- **`deployment.yaml`** — runs 2 replicas, with CPU/memory requests+limits and readiness/liveness probes hitting `/` (the production server's root route — confirmed to return `200`).
- **`service.yaml`** — a `ClusterIP` service exposing port 80, routed to the container's port 8000.
- **`ingress.yaml`** — routes external traffic in via an Ingress controller (e.g. nginx-ingress). Update `host:` to your real domain, or skip this file if you're exposing the Service another way (e.g. `LoadBalancer` type, or a cloud provider's ingress).

## Check it's running

```bash
kubectl get pods -l app=my-tw-site
kubectl port-forward svc/my-tw-site 8000:80
```

Then visit `http://localhost:8000`.

## Scaling

```bash
kubectl scale deployment my-tw-site --replicas=4
```
