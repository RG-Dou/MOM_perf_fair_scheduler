#!/bin/bash

sudo apt-get install maven
sudo apt install openjdk-8-jdk-headless
git clone git clone https://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@github.com/RG-Dou/flink-original.git
cd flink
git checkout work1-example
mvn clean install -DskipTests -Dcheckstyle.skip -Drat.skip=true

# conf/flink-conf.yaml
taskmanager.memory.process.size: 8192m
taskmanager.numberOfTaskSlots: 5
parallelism.default: 5