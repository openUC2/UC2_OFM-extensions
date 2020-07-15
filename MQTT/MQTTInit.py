import datetime
import logging
import logging.config
import platform
import os
#import serial
import socket
import time
#import yaml

from MQTTDevice import *
import paho.mqtt.client as mqtt

# MQTT Functions ------------------------------------------------------------------------------
mqtt_device_id_prefix = 'RASPI_'
mqtt_keepalive = 60
mqtt_port = 1883
mqtt_client_name = 'raspi1'
mqtt_client_pass = '1ipsar'
mqtt_device_LEDS = 'LAR01'
mqtt_device_MOTORS = 'MOT02'


class MQTT:
    def __init__(self, mqtt_device_name, mqtt_setup, mqtt_ip='localhost'):
        # connect to server
        from random import randint
        setup_name = mqtt_setup
        device_ID = mqtt_device_id_prefix + str(randint(0, 100000))
        device_MQTT_name = mqtt_device_name
        self.mqtt_connect_to_server(broker= mqtt_ip, 
                    mqttclient_name=mqtt_client_name, 
                    mqttclient_pass=mqtt_client_pass, 
                    mqttclient_ID=device_ID, 
                    port=mqtt_port, 
                    keepalive=mqtt_keepalive, 
                    use_login=False)

        # register devices
        self.raspi = self.mqtt_register_devices(device_MQTT_name,setup_name)
        self.ledarr = self.mqtt_register_devices(mqtt_device_LEDS,setup_name)
        self.motors = self.mqtt_register_devices(mqtt_device_MOTORS,setup_name)
        #fluo = self.mqtt_register_devices(mqtt_device_LASER,setup_name)

    def mqtt_register_devices(self, devices,setup_name):
        '''
        Adds devices to pointers.

        Note: no ERROR-catches! 
        '''
        if devices is None or devices == '':
            namer = None
        elif type(devices) == str:
            namer = MQTTDevice(setup_name, devices, self.mqttclient)
        else:
            namer = []
            for m in devices:
                namer.append(MQTTDevice(setup_name, m, self.mqttclient))

        # done?
        return namer

    def mqtt_connect_to_server(self, broker, mqttclient_name, mqttclient_pass, mqttclient_ID, port=1883, keepalive=60, use_login=False):
        mqtt.Client.connected_flag = False  # create flag in class
        mqtt.Client.bad_connection_flag = False  # new flag
        mqtt.Client.disconnect_flag = False
        mqtt.Client.turnoff_flag = False

        # define broker
        self.mqttclient = mqtt.Client(mqttclient_ID)  # creates a new client
        if use_login:
            self.mqttclient.username_pw_set(self.mqttclient_name, self.mqttclient_pass)

        # attach functions to client
        self.mqttclient.on_connect = self.on_connect
        self.mqttclient.on_message = self.on_message
        self.mqttclient.on_disconnect = self.on_disconnect

        # start loop to process received messages
        self.mqttclient.loop_start()
        try:
            print("self.mqttclient: connecting to broker ".format(broker))
            #print("self.mqttclient: connecting to broker ", broker)
            self.mqttclient.connect(host=broker, port=port, keepalive=keepalive)
            while not self.mqttclient.connected_flag and not self.mqttclient.bad_connection_flag:
                print("self.mqttclient: Waiting for established connection.")
                #print("self.mqttclient: Waiting for established connection.")
                time.sleep(1)
            if self.mqttclient.bad_connection_flag:
                self.mqttclient.loop_stop()
                print("self.mqttclient: had bad-connection. Not trying to connect any further.")
                #print("self.mqttclient: had bad-connection. Not trying to connect any further.")
        except Exception as err:  # e.g. arises when port errors exist etc
            print("self.mqttclient: Connection failed")
            print(err)

        # TODO: spawn Thread that checks for connection status
        # add:
        # if client1.turnoff_flag:
        #    client1.disconnect()
        #    client1.loop_stop()


    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:  # connection established
            client.connected_flag = True
            print("Connected with result code = {}".format(rc))
            #print("Connected with result code = {0}".format(rc))
        else:
            print("Connection error")
            #print("Connection error")
            client.bad_connection_flag = True

    def on_message(self, client, userdata, message):
        #print("on message")
        a = time.time().str
        print("Time on receive={0}".format(a))
        #print("Time on receive={0}".format(a))
        if message == "off":
            client.turnoff_flag = True
        print("Received={0}\nTopic={1}\nQOS={2}\nRetain Flag={3}".format(
            message.payload.decode("utf-8"), message.topic, message.qos, message.retain))


    def on_disconnect(self, client, userdata, rc):
        #logging.info("disconnecting reason: {0}".format)
        print("disconnecting reason: {0}".format)
        client.connected_flag = False
        client.disconnect_flag = True

# ##
# mqtt_ip = 'localhost'
# mqtt_device_name = 'RAS01'
# mqtt_setup = 'S004'

# mymqtt = MQTT(mqtt_device_name,mqtt_setup,mqtt_ip)
