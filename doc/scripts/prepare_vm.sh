#!/bin/bash

sudo apt-get update
sudo apt-get upgrade
sudo apt-get install python
sudo apt-get install python-pip
pip install -U scikit-learn scipy matplotlib
# python mom-guestd -c doc/mom-balloon.conf
