#!/bin/sh
# wait-for-it.sh

set -e

host="$1"
port="$2"
shift 2

# Remove the -- separator if present
if [ "$1" = "--" ]; then
    shift
fi

cmd="$@"

until nc -z "$host" "$port"; do
  >&2 echo "Agent is unavailable - sleeping"
  sleep 2
done

>&2 echo "Agent is up - executing command"
exec $cmd
