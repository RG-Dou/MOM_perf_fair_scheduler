#!/bin/bash

#ubuntu01: SM
#ubuntu02: TSM
#ubuntu03: WJ

Save_Root=/data/drg_data/work1/scheduler/data/compare
#ubuntu01 && ubuntu02
Sub=SM+TSM

Weight_file=/data/drg_data/work1/scheduler/main/doc/name-to-weight
weights="50 67 100 150 200"

config_weight(){
  new_line="        WEIGHT=\"${1}\""
  # 使用 sed 命令替换文件的第29行
  sed -i "29s/.*/$new_line/" "${Weight_file}"
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
  create_path ${Save_Root}/${Sub}

  for w in ${weights}; do
    config_weight $w

    save_path=${Save_Root}/${Sub}/${w}
    create_path ${save_path}

    bash base.sh ${save_path}
  done
}

main