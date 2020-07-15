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


def timelapse(microscope, n_images, t_between):
    """
    Save a set of images in a timelapse

    Args:
        microscope: Microscope object
        n_images (int): Number of images to take
        t_between (int/float): Time, in seconds, between sequential captures
    """
    base_file_name = generate_basename()
    folder = "TIMELAPSE_{}".format(base_file_name)

    # Take exclusive control over both the camera and stage
    with microscope.camera.lock, microscope.stage.lock:
        for n in range(n_images):
            # Generate a filename
            filename = f"{base_file_name}_image{n}"
            # Create a file to save the image to
            output = microscope.camera.new_image(
                filename=filename, folder=folder, temporary=False
            )

            # Capture
            microscope.camera.capture(output)

            # Add system metadata
            output.put_metadata(microscope.metadata, system=True)

            # Update task progress (only does anyting if the function is running in a LabThings task)
            progress_pct = ((n + 1) / n_images) * 100  # Progress, in percent
            update_task_progress(progress_pct)

            # Wait for the specified time
            time.sleep(t_between)


## Extension views


class TimelapseAPI(ActionView):
    """
    Take a series of images in a timelapse, running as a background task
    """
    args = {
        "n_images": fields.Integer(
            required=True, example=5, description="Number of images"
        ),
        "t_between": fields.Number(
            missing=1, example=1, description="Time (seconds) between images"
        ),
    }

    def post(self, args):
        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Create and start "timelapse", running in a background task
        return timelapse(
            microscope, args.get("n_images"), args.get("t_between")
        )


## Extension GUI (OpenFlexure eV)
# Alternate form without any dynamic parts
extension_gui = {
    "icon": "timelapse",  # Name of an icon from https://material.io/resources/icons/
    "forms": [  # List of forms. Each form is a collapsible accordion panel
        {
            "name": "Start a timelapse",  # Form title
            "route": "/timelapse",  # The URL rule (as given by "add_view") of your submission view
            "isTask": True,  # This forms submission starts a background task
            "isCollapsible": False,  # This form cannot be collapsed into an accordion
            "submitLabel": "Start",  # Label for the form submit button
            "schema": [  # List of dictionaries. Each element is a form component.
                {
                    "fieldType": "numberInput",
                    "name": "n_images",  # Name of the view arg this value corresponds to
                    "label": "Number of images",
                    "min": 1,  # HTML number input attribute
                    "default": 5,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "t_between",
                    "label": "Time (seconds) between images",
                    "min": 0.1,  # HTML number input attribute
                    "step": 0.1,  # HTML number input attribute
                    "default": 1,  # HTML number input attribute
                },
            ],
        }
    ],
}


## Create extension

# Create your extension object
my_extension = BaseExtension("com.myname.timelapse-extension", version="0.0.0")

# Add methods to your extension
my_extension.add_method(timelapse, "timelapse")

# Add API views to your extension
my_extension.add_view(TimelapseAPI, "/timelapse")

# Add OpenFlexure eV GUI to your extension
my_extension.add_meta("gui", build_gui(extension_gui, my_extension))