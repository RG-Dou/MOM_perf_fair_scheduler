#!/bin/bash

vms_list="ubuntu02 ubuntu03 ubuntu04 ubuntu05 ubuntu06 ubuntu07 ubuntu08 ubuntu09"

scp "drg:"

dir="flink/"
file="run-example.sh"

scp "ubuntu01:${dir}${file} ./"

for i in $vms_list; do
  scp ${file} "${i}:${file}"
done