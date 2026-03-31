#!/bin/sh
set -eu

CERT_DIR="/etc/nginx/certs"
CERT_FILE="$CERT_DIR/charles.crt"
KEY_FILE="$CERT_DIR/charles.key"
TLS_MODE="${CHARLES_TLS_MODE:-selfsigned}"

mkdir -p "$CERT_DIR"

if [ "$TLS_MODE" = "provided" ]; then
  if [ ! -s "$CERT_FILE" ] || [ ! -s "$KEY_FILE" ]; then
    echo "[charles-frontend] provided TLS mode selected but cert/key are missing"
    exit 1
  fi
  echo "[charles-frontend] using provided TLS certificate"
  exit 0
fi

if [ ! -s "$CERT_FILE" ] || [ ! -s "$KEY_FILE" ]; then
  echo "[charles-frontend] generating local TLS certificate for localhost"
  openssl req \
    -x509 \
    -nodes \
    -days 3650 \
    -newkey rsa:4096 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
fi
