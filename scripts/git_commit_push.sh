#!/bin/bash
set -x  # Debugläge

LOGFILE="/config/git_push_log.txt"
{
  echo "--- Git push script run: $(date) ---"

  eval $(ssh-agent -s)
  ssh-add /config/.ssh_keys/id_rsa

export GIT_SSH_COMMAND="ssh -o UserKnownHostsFile=/config/.ssh_keys/known_hosts -i /config/.ssh_keys/id_rsa"

  cd /config

  git status
  git add -u
  git commit -m "Automated commit $(date)"
  git push origin main
} >> "$LOGFILE" 2>&1