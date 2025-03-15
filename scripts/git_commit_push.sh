#!/bin/bash

cd /config 

git add -u

git commit -m "Automated commit $(date)"

git push
