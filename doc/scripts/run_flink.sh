#!/bin/bash

### ### ###  		   ### ### ###

### ### ### INITIALIZATION ### ### ###

### ### ###  		   ### ### ###


init() {
  # app level
  ROOT_DIR="$(pwd)"
  FLINK_DIR="${ROOT_DIR}/build-target/"
  FLINK_APP_DIR="${ROOT_DIR}/flink-examples/flink-examples-streaming/target/"
  #!/bin/sh
  if [ "$1" = "SM" ]; then
#    JAR_SUFFIX="StateMachineExample.jar"
    JOB_SUFFIX="statemachine.StateMachineExample"
  elif [ "$1" = "TSW" ]; then
#    JAR_SUFFIX="TopSpeedWindowing.jar"
    JOB_SUFFIX="windowing.TopSpeedWindowing"
  elif [ "$1" = "WJ" ]; then
#    JAR_SUFFIX="WindowJoin.jar"
    JOB_SUFFIX="join.WindowJoin"
  else
    echo "Invalid input"
  fi

  JAR=${FLINK_APP_DIR}"flink-examples-streaming-1.18-SNAPSHOT.jar"
  ### paths configuration ###
  FLINK=$FLINK_DIR$"bin/flink"
  JOB="org.apache.flink.streaming.examples."${JOB_SUFFIX}

  partitions=128
  parallelism=$2
  rate=500
  runtime=3000
  blockCacheSize=$1
}

# config block cache size
function configApp() {
#  config the slot number, the default parallelism, the memory size
    echo "INFO: config app block cache size: ${blockCacheSize}m"
#    sed -ri "s|(state.backend.rocksdb.block.cache-size: )[0-9]*|state.backend.rocksdb.block.cache-size: $blockCacheSize|" ${FLINK_DIR}conf/flink-conf.yaml
#    sed -ri "s|(taskmanager.memory.managed.fraction: 0.)[0-9]*|taskmanager.memory.managed.fraction: 0.$blockCacheSize|" ${FLINK_DIR}conf/flink-conf.yaml
}

# run flink clsuter
function runFlink() {
    echo "INFO: starting the cluster"
    if [[ -d ${FLINK_DIR}log ]]; then
        rm -rf ${FLINK_DIR}log
    fi
    mkdir ${FLINK_DIR}log
    ${FLINK_DIR}/bin/start-cluster.sh
}

# clsoe flink clsuter
function stopFlink() {
    echo "INFO: experiment finished, stopping the cluster"
    PID=`jps | grep CliFrontend | awk '{print $1}'`
    if [[ ! -z $PID ]]; then
      kill -9 ${PID}
    fi
    PID=`jps | grep StockGenerator | awk '{print $1}'`
    if [[ ! -z $PID ]]; then
      kill -9 ${PID}
    fi
    ${FLINK_DIR}bin/stop-cluster.sh
    echo "close finished"
#    cleanEnv
}

# run applications
function runApp() {
  echo "INFO: $FLINK run -c ${JOB} ${JAR} -p1 ${parallelism} -mp2 ${partitions} -rate ${rate} -sleep 0 &"
  rm nohup.out
  nohup $FLINK run -c ${JOB} ${JAR} -p1 ${parallelism} -mp2 ${partitions} -rate ${rate} -sleep 0 &
}

# run one flink demo exp, which is a word count job
run_one_exp() {
  configApp

  echo "INFO: run Flink"
  runFlink
  python3 -c 'import time; time.sleep(5)'

  echo "INFO: run app "$1
  runApp

#  SCRIPTS_RUNTIME=`expr ${runtime} - 50 + 10`
  SCRIPTS_RUNTIME=${runtime}
  python3 -c 'import time; time.sleep('"${SCRIPTS_RUNTIME}"')'

  stopFlink
}

init $1 $2
run_one_exp $1
#test
