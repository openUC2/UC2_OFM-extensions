#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul  9 10:25:48 2020

@author: bene
"""
from MQTTInit import MQTT

from labthings.server.extensions import BaseExtension
from labthings.server.find import find_component
from labthings.server.view import View, ActionView

from labthings.server.schema import Schema
from labthings.server import fields

from flask import send_file  # Used to send images from our server
import io  # Used in our capture action
import time  # Used in our timelapse function

# Used in our timelapse function
from openflexure_microscope.captures.capture_manager import generate_basename

# Used to run our timelapse in a background thread
from labthings.core.tasks import update_task_progress

# Used to convert our GUI dictionary into a complete eV extension GUI
from openflexure_microscope.api.utilities.gui import build_gui

## Extension methods


def sendmqtt(microscope, mqttdevice, command):

    mqttdevice.mqttclient.subscribe("S0/MOTz1/MOV", qos=1)
    mqttdevice.mqttclient.publish("S0/MOTz1/MOV", "1", qos=1, retain=False)
    


## Extension views


class MQTTAPI(ActionView):
    """
    Take a series of images in a timelapse, running as a background task
    """
    
    '''
    args = {
        "n_images": fields.Integer(
            required=True, example=5, description="Number of images"
        ),
        "t_between": fields.Number(
            missing=1, example=1, description="Time (seconds) between images"
        ),
    }
    '''
    
    mqtt_ip = 'localhost'
    mqtt_device_name = 'RAS01'
    mqtt_setup = 'S004'
    
    mqttdevice = MQTT(mqtt_device_name,mqtt_setup,mqtt_ip)
    

    def post(self, args):
        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Create and start "timelapse", running in a background task
        command = 'Dummy'
        return sendmqtt(microscope, mqttdevice, command)
        )
    


## Extension GUI (OpenFlexure eV)
# Alternate form without any dynamic parts
extension_gui = {
    "icon": "send",  # Name of an icon from https://material.io/resources/icons/
    "forms": [  # List of forms. Each form is a collapsible accordion panel
        {
            "name": "Send a command",  # Form title
            "route": "/sendmqtt",  # The URL rule (as given by "add_view") of your submission view
            "isTask": True,  # This forms submission starts a background task
            "isCollapsible": False,  # This form cannot be collapsed into an accordion
            "submitLabel": "Send",  # Label for the form submit button
            "schema": [  # List of dictionaries. Each element is a form component.
                # {
                #     "fieldType": "numberInput",
                #     "name": "n_images",  # Name of the view arg this value corresponds to
                #     "label": "Number of images",
                #     "min": 1,  # HTML number input attribute
                #     "default": 5,  # HTML number input attribute
                # },
                # {
                #     "fieldType": "numberInput",
                #     "name": "t_between",
                #     "label": "Time (seconds) between images",
                #     "min": 0.1,  # HTML number input attribute
                #     "step": 0.1,  # HTML number input attribute
                #     "default": 1,  # HTML number input attribute
                # },
            ],
        }
    ],
}


## Create extension

# Create your extension object
my_extension = BaseExtension("com.myname.mqtt-extension", version="0.0.0")

# Add methods to your extension
my_extension.add_method(sendmqtt, "sendmqtt")

# Add API views to your extension
my_extension.add_view(MQTTAPI, "/sendmqtt")

# Add OpenFlexure eV GUI to your extension
my_extension.add_meta("gui", build_gui(extension_gui, my_extension))
