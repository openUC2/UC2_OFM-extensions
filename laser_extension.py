from labthings.extensions import BaseExtension
from labthings import find_component, fields
from labthings.views import ActionView
from typing import Tuple
from labthings.schema import Schema

import time
import io  # Used in our capture action
import logging

# Used to run our laser in a background thread
from labthings import update_action_progress as update_task_progress

from openflexure_microscope.captures.capture_manager import (
    generate_basename,
)

# Used to convert our GUI dictionary into a complete eV extension GUI
from openflexure_microscope.api.utilities.gui import build_gui

## Extension methods
def control_laser(microscope, i_laser=0, i_led=0):
    microscope.stage.set_led(state=int(i_led))
    microscope.stage.set_laser_intensity(int(i_laser))


 
## Extension views
class laserAPI(ActionView):
    """
    Control a laser
    """
    args = {
        "i_laser": fields.Number(
            missing=30,
            example=512,
            description="Intensity Laser (0..1024)",
        ),
        "i_led": fields.Number(
            missing=0,
            example=1,
            description="Intensity LED (0..1)",
        )
    }

    def post(self, args):
        i_laser = args.get("i_laser")
        i_led = args.get("i_led")

        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        return control_laser(
            microscope = microscope,
            i_laser = i_laser,
            i_led = i_led
        )


## Extension GUI (OpenFlexure eV)
# Alternate form without any dynamic parts
extension_gui = {
    "icon": "query_builder",  # Name of an icon from https://material.io/resources/icons/
    "forms": [  # List of forms. Each form is a collapsible accordion panel
        {
            "name": "Control the laser intensity ",  # Form title
            "route": "/laser",  # The URL rule (as given by "add_view") of your submission view
            "isTask": True,  # This forms submission starts a background task
            "isCollapsible": False,  # This form cannot be collapsed into an accordion
            "submitLabel": "Set Illumination ",  # Label for the form submit button
            "schema": [  # List of dictionaries. Each element is a form component.
                {
                    "fieldType": "numberInput",
                    "name": "i_laser",
                    "label": "Intensity Laser (0..1024)",
                    "min": 0,  # HTML number input attribute
                    "step": 1,  # HTML number input attribute
                    "default": 512,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "i_led",
                    "label": "Intensity LED (0 or 1)",
                    "min": 0,  # HTML number input attribute
                    "min": 0,  # HTML number input attribute
                    "step": 1,  # HTML number input attribute
                    "default": 1,  # HTML number input attribute
                }
            ],
        }
    ],
}


## Create extension

# Create your extension object
laser_extension = BaseExtension("org.openflexure.laser_extension", version="0.0.0")

# Add methods to your extension
laser_extension.add_method(control_laser, "control_laser")

# Add API views to your extension
laser_extension.add_view(laserAPI, "/laser")

# Add OpenFlexure eV GUI to your extension
laser_extension.add_meta("gui", build_gui(extension_gui, laser_extension))
