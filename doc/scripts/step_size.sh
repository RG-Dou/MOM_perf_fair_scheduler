#!/bin/bash

Save_Root=/data/drg_data/work1/scheduler/data/step_size

config_file=/data/drg_data/work1/scheduler/main/doc/mom-balloon.conf
sizes="10000 5000 1000"

config_file(){
#  new_line="        WEIGHT=\"${1}\""
  # 使用 sed 命令替换文件的第29行
  sed -i "${1}s/.*/${2}/" ${3}
  echo "sed -i ${1}s/.*/${2}/ ${3}"
}

config_step_size(){
  new_line="step_size:${1}"
  line_num=63
  config_file ${line_num} ${new_line} ${config_file}
}

config_policy(){
  new_line="policy-type:${1}"
  line_num=49
  file=/data/drg_data/work1/scheduler/main/doc/mom-balloon.conf
  config_file ${line_num} ${new_line} ${file}
}

create_path(){
    # Check if path is exist
  if [ ! -d "$1" ]; then
    # if doesn't exist, then create
    mkdir -p "$1"
    echo "create path $1"
  fi
}

main(){
  create_path ${Save_Root}

  for size in ${sizes}; do
    config_step_size ${size}

    save_path=${Save_Root}/${size}
    create_path ${save_path}

    bash base.sh ${save_path}
  done
}

config_policy "gradient"
main