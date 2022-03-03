#!/bin/bash

function log() {
  logger -s -p user.$1 ${@:2}
}

log info "magni-base: Using workspace setup file /home/ubuntu/catkin_ws/devel/setup.bash"
source /home/ubuntu/catkin_ws/devel/setup.bash

log_path="/tmp"
if [[ ! -d $log_path ]]; then
  CREATED_LOGDIR=true
  trap 'CREATED_LOGDIR=false' ERR
    log warn "magni-base: The log directory you specified \"$log_path\" does not exist. Attempting to create."
    mkdir -p $log_path 2>/dev/null
    chown ubuntu:ubuntu $log_path 2>/dev/null
    chmod ug+wr $log_path 2>/dev/null
  trap - ERR
  # if log_path could not be created, default to tmp
  if [[ $CREATED_LOGDIR == false ]]; then
    log warn "magni-base: The log directory you specified \"$log_path\" cannot be created. Defaulting to \"/tmp\"!"
    log_path="/tmp"
  fi
fi

source /etc/ubiquity/env.sh
log info "magni-base: Launching ROS_HOSTNAME=$ROS_HOSTNAME, ROS_IP=$ROS_IP, ROS_MASTER_URI=$ROS_MASTER_URI, ROS_LOG_DIR=$log_path"

# Punch it.
export ROS_HOME=$(echo ~ubuntu)/.ros
export ROS_LOG_DIR=$log_path
# upgrading firmware still wasnt ported to py3 https://github.com/UbiquityRobotics/ubiquity_motor/issues/149
# untill that is done, we have to do it with python2 and absolute paths
python2 /home/ubuntu/catkin_ws/src/ubiquity_motor/scripts/upgrade_firmware.py --file /home/ubuntu/v43_20210829_enc.cyacd
roslaunch --wait -v magni_bringup base.launch& # launhces base
roslaunch magni_nav move_basic.launch& #launches move basic
./home/ubuntu/production_test.py # sends the goal to the robot
sudo poweroff #turns off the robot

PID=$!

log info "magni-base: Started roslaunch as background process, PID $PID, ROS_LOG_DIR=$ROS_LOG_DIR"
echo "$PID" > $log_path/magni-base.pid
wait "$PID"