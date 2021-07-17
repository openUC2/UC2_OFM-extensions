from labthings.extensions import BaseExtension
from labthings import find_component, fields
from labthings.views import ActionView
from typing import Tuple
from labthings.schema import Schema

import os
import time
import io  # Used in our capture action
import logging

from openflexure_microscope.captures.capture_manager import (
    generate_basename,
)

# Used to convert our GUI dictionary into a complete eV extension GUI
from openflexure_microscope.api.utilities.gui import build_gui

## Extension methods


def record_video(
    microscope,
    filename,
    folder,
    video_length,
    video_framerate,
    steps_2_move = (0,0),
    video_format: str = "h264",
    metadata: dict = {},
    annotations: dict = {},
    tags: list = [],
):
    # Create video output
    output = microscope.captures.new_video(
        temporary=False, filename=filename, folder=folder, fmt=video_format
    )

    # Do recording

    with microscope.camera.lock:
        #TO CHANGE VIDEO RESOLUTION RESIZE, UNCOMMENT THE LINES BELOW
        old_stream_resolution = microscope.camera.stream_resolution
        old_stream_framerate = microscope.camera.camera.framerate
        if(microscope.camera.camera.revision=='ALVIUM'):
            if not os.path.exists(output.file.split('.h264')[0]):
                os.makedirs(output.file.split('.h264')[0])
            microscope.camera.start_recording(output=output.file)#, video_framerate)
            logging.info('Changed framerate to: {}'.format(video_framerate))
            time.sleep(video_length)
            microscope.camera.stop_recording()
        else:   
            #if video_framerate != microscope.camera.camera.framerate:
                #microscope.camera.stop_stream()
                #logging.info('Changed resolution to: {}'.format(microscope.camera.stream_resolution))
            #    microscope.camera.camera.framerate = video_framerate
            #    logging.info('Changed framerate to: {}'.format(microscope.camera.camera.framerate))
                #microscope.camera.start_stream()
            microscope.camera.stream_resolution = (1920, 1080) #Change this to the video resolution you want the resizing to
            myzero = microscope.stage.position
            myoldspeed_x,myoldspeed_y,myoldspeed_z = microscope.stage.board.getspeed()
            microscope.stage.board.setspeed(10,10,40)
            microscope.camera.start_recording(output=output.file, fmt=video_format)
            microscope.stage.move_rel((steps_2_move[0],steps_2_move[1],0)) 
            microscope.camera.stop_recording()
            # reset speed
            microscope.stage.board.setspeed(myoldspeed_x,myoldspeed_y,myoldspeed_z)               
            microscope.stage.move_rel((-steps_2_move[0],-steps_2_move[1],0)) 

           # microscope.camera.camera.framerate = old_stream_framerate
            microscope.camera.stream_resolution = old_stream_resolution
            #logging.info('Changed resolution back to: {}'.format(microscope.camera.stream_resolution))


## Extension views
class VideoAPI(ActionView):
    """
    Record a video
    """
    args = {
        "video_length": fields.Number(
            missing=100, example=100, description="Length (seconds) of video"
        ),
        "video_framerate": fields.Number(
            missing=30,
            example=30,
            description="Video framerate (frames per second)",
        ),
        "video_format": fields.String(
            missing="h264", example="h264", description="Video format (h264,...)"
        ),
        "move_x": fields.Number(
            missing=100,
            example=100,
            description="Number of steps to move in X",
        ),        
        
    }

    def post(self, args):

        video_length = args.get("video_length")
        video_format = args.get("video_format")
        video_framerate = args.get("video_framerate")
        move_x = args.get("move_x")

        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        # Location to store video
        folder = "Videos"
        basename = generate_basename()
        filename = f"{basename}"


        return record_video(
            microscope,
            filename=filename,
            folder=folder,
            steps_2_move = (move_x,0),
            video_length=video_length,
            video_format=video_format,
            video_framerate=video_framerate,
            metadata=microscope.metadata,
        )


## Extension GUI (OpenFlexure eV)
# Alternate form without any dynamic parts
extension_gui = {
    "icon": "videocam",  # Name of an icon from https://material.io/resources/icons/
    "forms": [  # List of forms. Each form is a collapsible accordion panel
        {
            "name": "Record a video",  # Form title
            "route": "/video",  # The URL rule (as given by "add_view") of your submission view
            "isTask": True,  # This forms submission starts a background task
            "isCollapsible": False,  # This form cannot be collapsed into an accordion
            "submitLabel": "Start recording",  # Label for the form submit button
            "schema": [  # List of dictionaries. Each element is a form component.
                {
                    "fieldType": "numberInput",
                    "name": "video_length",
                    "label": "Length (seconds) of video",
                    "min": 0.1,  # HTML number input attribute
                    "step": 0.1,  # HTML number input attribute
                    "default": 100,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "video_framerate",
                    "label": "Framerate (Frames Per Second)",
                    "min": 1,  # HTML number input attribute
                    "max": 90,
                    "step": 1,  # HTML number input attribute
                    "default": 30,  # HTML number input attribute
                },
                {
                    "fieldType": "selectList",
                    "name": "video_format",
                    "label": "Video format",
                    "value": "h264",
                    "options": ["h264","mjpeg","yuv","rgb","rgba","bgr","bgra"],
                },
                {
                    "fieldType": "numberInput",
                    "name": "move_x",
                    "label": "Steps to move in X",
                    "min": 0,  # HTML number input attribute
                    "step": 100,  # HTML number input attribute
                    "default": 0,  # HTML number input attribute
                },                
            ],
        }
    ],
}


## Create extension

# Create your extension object
video_extension = BaseExtension("org.openflexure.video_extension", version="0.0.0")

# Add methods to your extension
video_extension.add_method(record_video, "record_video")

# Add API views to your extension
video_extension.add_view(VideoAPI, "/video")

# Add OpenFlexure eV GUI to your extension
video_extension.add_meta("gui", build_gui(extension_gui, video_extension))
