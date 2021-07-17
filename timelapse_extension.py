from labthings.extensions import BaseExtension
from labthings import find_component, fields
from labthings.views import ActionView
from typing import Tuple
from labthings.schema import Schema

import time
import io  # Used in our capture action
import logging

# Used to run our timelapse in a background thread
from labthings import update_action_progress as update_task_progress

from openflexure_microscope.captures.capture_manager import (
    generate_basename,
)

# Used to convert our GUI dictionary into a complete eV extension GUI
from openflexure_microscope.api.utilities.gui import build_gui

## Extension methods
def acquire_timelapse(
    microscope,
    filename,
    folder,
    t_duration,
    t_period,
    t_name,
    t_modality,
    i_laser=255,
    metadata: dict = {}
):


    # Do recording
    t_duration *= 60 # convert minutes to seconds
    with microscope.camera.lock:
        #TO CHANGE VIDEO RESOLUTION RESIZE, UNCOMMENT THE LINES BELOW
        iiter = 0
        
        # save the time when starting the image acquisition
        time_init = time.time()

        # compute number of images which will be taken..
        N_images = t_duration//t_period
        
        while((time.time()-time_init)<t_duration):
            for i_modality in range(len(t_modality)):
                print("Turning on modality illu: "+t_modality[i_modality])
                if t_modality[i_modality]=='Fluorescence':
                    microscope.stage.set_laser_intensity(i_laser)
                    time.sleep(.2)
                if t_modality[i_modality]=='Brightfield':
                    microscope.stage.set_led(1)
                    time.sleep(.2)                    
                # Create a file to save the image to and Capture
                microscope.capture(
                    filename=filename+"_"+t_modality[i_modality] + "_" + str(iiter), 
                    folder=folder, 
                    temporary=False
                )
                microscope.stage.set_laser_intensity(0)
                microscope.stage.set_led(0)
            iiter += 1
            
            # Update task progress (only does anyting if the function is running in a LabThings task)
            progress_pct = ((iiter + 1) / N_images) * 100  # Progress, in percent
            update_task_progress(progress_pct)

            # wait until we want to take the next image
            time.sleep(t_period)



## Extension views
class TimeLapseAPI(ActionView):
    """
    Record a timelapse
    """
    args = {
        "t_duration": fields.Number(
            missing=1, example=1, description="Length (minutes) of TimeLapse imaging"
        ),
        "t_period": fields.Number(
            missing=30,
            example=30,
            description="Period of frame acquisition (every N seconds)",
        ),
        "t_name": fields.String(
            missing="TL_", example="TL_", description="Title of timelapse series"
        ),
        "i_laser": fields.Number(
            missing=30,
            example=512,
            description="Intensity Laser (0..1024)",
        ),
        "select_modality": fields.List(
            fields.String, missing=[], allow_none=True
        )
    }

    def post(self, args):

        t_duration = args.get("t_duration")
        t_period = args.get("t_period")
        i_laser = args.get("i_laser")
        t_name = args.get("t_name")
        t_modality = args.get("select_modality") or {}

        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Location to store video
        folder = "TimeLapse"
        basename = generate_basename()
        filename = f"{basename}"


        return acquire_timelapse(
            microscope,
            filename=filename,
            folder=folder,
            t_duration=t_duration,
            t_period=t_period,
            t_name=t_name,
            t_modality=t_modality,
            i_laser = i_laser,
            metadata=microscope.metadata,
        )


## Extension GUI (OpenFlexure eV)
# Alternate form without any dynamic parts
extension_gui = {
    "icon": "query_builder",  # Name of an icon from https://material.io/resources/icons/
    "forms": [  # List of forms. Each form is a collapsible accordion panel
        {
            "name": "Acquire a timelapse series",  # Form title
            "route": "/timelapse",  # The URL rule (as given by "add_view") of your submission view
            "isTask": True,  # This forms submission starts a background task
            "isCollapsible": False,  # This form cannot be collapsed into an accordion
            "submitLabel": "Start Acquisition",  # Label for the form submit button
            "schema": [  # List of dictionaries. Each element is a form component.
                {
                    "fieldType": "numberInput",
                    "name": "t_duration",
                    "label": "Duration (minutes) of timelapse acquisition",
                    "min": 0.,  # HTML number input attribute
                    "step": 0.1,  # HTML number input attribute
                    "default": 2,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "t_period",
                    "label": "Time between two timestamps (seconds)",
                    "min": .1,  # HTML number input attribute
                    "step": .1,  # HTML number input attribute
                    "default": 2,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "i_laser",
                    "label": "Intensity Laser (0..1024",
                    "min": 0,  # HTML number input attribute
                    "step": 1,  # HTML number input attribute
                    "default": 512,  # HTML number input attribute
                },
                 {
                    "fieldType": "checkList",
                    "name": "select_modality",
                    "label": "Select Imaging Modality",
                    "value": (["Brightfield", "Fluorescence"]),
                    "options": (["Brightfield", "Fluorescence"])
                }
            ],
        }
    ],
}


## Create extension

# Create your extension object
timelapse_extension = BaseExtension("org.openflexure.timelapse_extension", version="0.0.0")

# Add methods to your extension
timelapse_extension.add_method(acquire_timelapse, "acquire_timelapse")

# Add API views to your extension
timelapse_extension.add_view(TimeLapseAPI, "/timelapse")

# Add OpenFlexure eV GUI to your extension
timelapse_extension.add_meta("gui", build_gui(extension_gui, timelapse_extension))
