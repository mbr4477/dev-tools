# Hatchet Software Factory

Built around a local `hatchet-lite` server.

## Hatchet Server

```shell
docker compose up -d
```

## Worker Environment

```shell
export HATCHET_CLIENT_TOKEN="..."
export HATCHET_CLIENT_TLS_STRATEGY=none
export HATCHET_CLIENT_HOST_PORT="127.0.0.1:7077"
```