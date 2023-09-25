#!/bin/bash

Run_Time=1800
Data_ROOT=/data/drg_data/work1/scheduler/data
Log_Path=${Data_ROOT}/test1
Save_Path=$1

pre_process(){
  cd ../../
  rm nohup.out
  echo "remove all logs in: " ${Log_Path}
  rm -rf ${Log_Path}/*
}

# kill the momd
kill_momd(){
  if ps -p $1 > /dev/null; then
    echo "killing the process $1"
    kill $1
  else
    echo "process $1 doesn't exist"
  fi
}

mv_log(){
  mv ${Log_Path}/momplot-000/* ${Save_Path}
}

main(){
  pre_process

  # running momd background
  nohup python momd -c doc/mom-balloon.conf &
  # get the pid
  pid=$!

  # waiting for
  sleep ${Run_Time}

  kill_momd ${pid}
  mv_log
}

main