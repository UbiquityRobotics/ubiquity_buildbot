#!/usr/bin/env python3

import matplotlib
import rospy
from sensor_msgs.msg import Range
import RPi.GPIO as GPIO
from time import sleep
import matplotlib.pyplot as plt
import os


sonars = [0,1,2,3,4]
sonar_ranges = [0,0,0,0,0]
last_sonar_timestamp = [0,0,0,0,0]

buzzing = False
p = None
pin = 22 # this is phisical pin 22, GPIO25
freq = 500
duty_cycle = 5

os.environ['DISPLAY']=':0'

def sonar_callback(data):
    global sonar_ranges
    global last_sonar_timestamp

    i = int(data.header.frame_id.split("_")[-1])
    sonar_ranges[i] = data.range
    last_sonar_timestamp[i] = data.header.stamp
    # print(last_sonar_timestamp)

    for j in range(0, len(last_sonar_timestamp)):
        if last_sonar_timestamp[j] != 0:
            if data.header.stamp - last_sonar_timestamp[j] > rospy.Duration(2):
                sonar_ranges[j] = 0

def buzzer_callback(event):
    global buzzing
    # rospy.loginfo("buzzer " + str(buzzing))
    p.ChangeDutyCycle(int(buzzing)*duty_cycle)
    buzzing = not buzzing

def main():
    global p
    rospy.init_node('sonarboar_checker', anonymous=True)
    
    rospy.Subscriber("sonars", Range, sonar_callback)

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD) # Safer because GPIO numbering might change during board revisions
    GPIO.setup(pin, GPIO.OUT)
    p = GPIO.PWM(pin, freq)
    rospy.loginfo("buzzer node initialized")
    p.start(duty_cycle)

    # enable interactive mode
    plt.ion()
    # creating subplot and figure
    fig = plt.figure()
    plt.bar(sonars, sonar_ranges)
    manager = plt.get_current_fig_manager()
    manager.full_screen_toggle()

    rospy.Timer(rospy.Duration(1), buzzer_callback)

    rate = rospy.Rate(2)
    while not rospy.is_shutdown():
        plt.clf()
        plt.ylim(0, 10.0)
        plt.xlabel('sonars')
        plt.ylabel('range (m)')
        plt.bar(sonars, sonar_ranges, color=('red'))# Displaying the bar plot
        fig.canvas.draw()
        # to flush the GUI events
        fig.canvas.flush_events()
        rate.sleep()
        # print(sonar_ranges)
    
    matplotlib.pyplot.close('all')


if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass