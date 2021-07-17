from labthings.extensions import BaseExtension
from labthings import find_component, fields
from labthings.views import ActionView
from typing import Tuple
from labthings.schema import Schema

import time
import io  # Used in our capture action
import logging

# image processing libraries
import numpy as np
import matplotlib.pyplot as plt
import cv2
from scipy.ndimage import gaussian_filter
from scipy.ndimage.measurements import center_of_mass
from scipy.signal import chirp, find_peaks, peak_widths

import serial

# Used to run our autocoupling in a background thread
from labthings import update_action_progress as update_task_progress

from openflexure_microscope.captures.capture_manager import (
    generate_basename,
)

# Used to convert our GUI dictionary into a complete eV extension GUI
from openflexure_microscope.api.utilities.gui import build_gui

# external hardware used for the lens and laser control
from openflexure_microscope.hardware.laser import laser
from openflexure_microscope.hardware.lens import lens

# external camera for automatic coupling 
import openflexure_microscope.camera.buffcam as buffcam

# Serial port of hte ESP32 which hosts the lens
serialport = "/dev/ttyUSB0"

# Camera parameters 
height = 240
width = 320 
exposuretime = 1 # minimum is 1 (int values only!)

# parameters for x/z coodinate search
step_x_min = 0
step_x_max = 3000
step_x_steps = 50

step_z_min = 0
step_z_max = 2000
step_z_steps = 100


# for debugging
is_display = False
if is_display: import matplotlib.pyplot as plt 

# gstreamer pipeline for the jetson IMX219 camera
def gstreamer_pipeline(
    capture_width=640,
    capture_height=480,
    display_width=640,
    display_height=480,
    exposuretime=1,
    framerate=120,
    flip_method=0,
    exposure_comp = 2,
    exposure_time = 10
):
    #gst-launch-1.0 
    # nvarguscamerasrc awblock=true aelock=false  exposuretimerange="100000 100000"  gainrange="1 1" ispdigitalgainrange="1 1"  ! 'video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12' ! nvoverlaysink
    # nvarguscamerasrc awblock=true aelock=false width=(int)640, height=(int)480, exposuretimerange="(int)100000 (int)100000" gainrange="1 1" ispdigitalgainrange="1 1" format=(string)NV12, framerate=(fraction)120/1 ! nvvidconv flip-method=0 ! video/x-raw, width=(int)640, height=(int)480, format=(string)BGRx ! videoconvert ! video/x-raw, format=(string)BGR ! appsinkvideo/x-raw(memory:NVMM), 

    exposuretime = int(exposuretime*100000)
    return (
        'nvarguscamerasrc '
        'exposuretimerange="%d %d" gainrange="1 1" ispdigitalgainrange="1 1" '
        'awblock=true aelock=true '
        '! video/x-raw(memory:NVMM), '
        #"width=(int)%d, height=(int)%d, "
        'width=(int)%d, height=(int)%d, ' #" ##exposurecompensation=-2, aelock=true, "  #exposuretimerange=34000 35873300, 
        "format=(string)NV12, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (
            exposuretime,
            exposuretime,
            capture_width,
            capture_height, 
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )





## Extension methods
def auto_coupling(
    x_range,
    z_range,
    serialport,
    is_display=False
):


    # connect to the lens/laser
    # open the lens and move it 
    serialconnection = serial.Serial(serialport,115200,timeout=1) # Open grbl serial port
    print('Initializing Lens 1')
    # init lens
    lens_1 = lens(serialconnection, lens_id = 1)
    laser_1 = laser(serialconnection, laser_id = 1)

    # open camera
    cap = buffcam.VideoCapture(gstreamer_pipeline(exposuretime=exposuretime,capture_width=width, capture_height = height, display_width=width, display_height=height, flip_method=0))#, cv2.CAP_GSTREAMER)
    print("Camera is open")

    # let the camera warm up
    for _ in range(20):
        cap.read()

    
    # Start Super Fast Chip Coupling...

    # First locate a reflection at the chip surface
    # assume we place the lens at the lower part of the chip where you see good reflection of the spot 
    pos_x = 0
    pos_z = 0

    # reset lens position:
    lens_1.move(pos_x, "X")
    lens_1.move(pos_z, "Z")

    '''
    1. Perform a focus of the spot relative to the chip's surface => smallest spot => in-focus
    '''
    #%%
    ratios = []

    # Capture Frame
    for iz in z_range:
        lens_1.move(iz, "Z")
        time.sleep(.2)
        _, img = cap.read() 

        # only take green and blue channel to avoid oversaturation
        img = np.mean(img[:,:,1:],-1)
        
        # let the camera warm up
        img_filtered = gaussian_filter(img, 20)
        #circles = cv2.HoughCircles(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.HOUGH_GRADIENT, 1.2, 100)
        max_coords = np.where(np.max(img_filtered)==img_filtered)
        img_masked = img_filtered*(img_filtered>np.max(img_filtered)*.5)
        max_coords_COF = center_of_mass(img_masked)
        ratio = np.sum(img_filtered>np.max(img_filtered)*.5) # if its smaller, it is more focussed
        ratios.append(ratio)
        print("Coord Z: "+str(iz)+", Ratio: "+str(ratio)) 
        if(is_display):
            plt.subplot(121)
            plt.title('Filtered Frame at '+str(iz))
            plt.imshow(img_filtered)
            plt.subplot(122)
            plt.imshow(img_masked)    
            plt.plot(max_coords[1], max_coords[0], 'rx')
            plt.plot(max_coords_COF[1], max_coords_COF[0], 'gx'), plt.show()


    ratios = np.array(ratios)
    if (is_display): plt.plot(z_range,ratios), plt.show()

    # we define the focus as the position with highest intensity concentration / smallest spot size
    pos_z = z_range[np.where(ratios==np.min(ratios))]
    if type(pos_z)==np.ndarray:
        pos_z=pos_z[0] # pick only one value
    
    # move lens to the position with highest concentration of the signal 
    lens_1.move(pos_z, "Z")



    '''
    2. Perform adjustment of the lens along X by maximizing the intensity as a function of x 
    Cost function -> argmax(I(x))
    We assume that the exposure time is constant and the sensor is not overexposed
    ''' 
    # Bring focus position and edge in line
    ratios = []

    # move the lens along x
    for ix in x_range:
        lens_1.move(ix, "X")
        time.sleep(.2)
        _, img = cap.read() 
    
        # only take green and blue channel to avoid oversaturation
        img = np.mean(img,-1)
        ratio = np.mean(img)
        ratios.append(ratio)
        print("Coord X: "+str(ix)+", Ratio: "+str(ratio)) 

    
    myedge = np.roll(abs(ratios-np.roll(ratios,1)),-1)
    myedge[0:2]=0; myedge[-3:]=0
    pos_x = np.squeeze(x_range[np.squeeze((np.where(myedge==np.max(myedge))))-1])
    
    # move lens to the optimal position
    lens_1.move(pos_x, "X")

    if is_display: 
        plt.plot(x_range,ratios)
        plt.plot(x_range,myedge), plt.show()

    print("This is the end; Closing the camera and serial connection")
    cap.release()
    serialconnection.close()
    
## Extension views
class AutocouplingAPI(ActionView):
    """
    Perform auto chip coupling
    """

    args = {
        "step_x_min": fields.Number(
            missing=1, example=0, description="Start Position for the Lens scan in X"
        ),
        "step_x_max": fields.Number(
            missing=1, example=3000, description="End Position for the Lens scan in X"
        ),
        "step_x_steps": fields.Number(
            missing=1, example=50, description="Stepsize for the Lens scan in X"
        ),
        "step_z_min": fields.Number(
            missing=1, example=0, description="Start Position for the Lens scan in Z"
        ),
        "step_z_max": fields.Number(
            missing=1, example=3000, description="End Position for the Lens scan in Z"
        ),
        "step_z_steps": fields.Number(
            missing=1, example=50, description="Stepsize for the Lens scan in Z"
        ),      
        "serialport": fields.String(
            missing="/dev/ttyUSB0", example="/dev/ttyUSB0", description="Serialport"
        ),  
        "serialport": fields.String(
            missing=1, example=50, description="Stepsize for the Lens scan in Z"
        )
    }

    

    def post(self, args):

        step_x_min =  args.get("step_x_min")
        step_x_max = args.get("step_x_max")
        step_x_steps = args.get("step_x_steps")

        step_z_min = args.get("step_z_min")
        step_z_max = args.get("step_z_max")
        step_z_steps = args.get("step_z_steps")

        serialport = args.get("serialport") or {}

        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        x_range = np.int32(np.array(np.arange(step_x_min,step_x_max,step_x_steps)))
        z_range = np.int32(np.array(np.arange(step_z_min,step_z_max,step_z_steps)))

        return auto_coupling(
            x_range,
            z_range,
            serialport,
            is_display=False
        )


    args = {
        "step_x_min": fields.Number(
            missing=1, example=0, description="Start Position for the Lens scan in X"
        ),
        "step_x_max": fields.Number(
            missing=1, example=3000, description="End Position for the Lens scan in X"
        ),
        "step_x_steps": fields.Number(
            missing=1, example=50, description="Stepsize for the Lens scan in X"
        ),
        "step_z_min": fields.Number(
            missing=1, example=0, description="Start Position for the Lens scan in Z"
        ),
        "step_z_max": fields.Number(
            missing=1, example=3000, description="End Position for the Lens scan in Z"
        ),
        "step_z_steps": fields.Number(
            missing=1, example=50, description="Stepsize for the Lens scan in Z"
        ),      
        "serialport": fields.String(
            missing="/dev/ttyUSB0", example="/dev/ttyUSB0", description="Serialport"
        )
    }

## Extension GUI (OpenFlexure eV)
# Alternate form without any dynamic parts
extension_gui = {
    "icon": "query_builder",  # Name of an icon from https://material.io/resources/icons/
    "forms": [  # List of forms. Each form is a collapsible accordion panel
        {
            "name": "Perform autocoupling into the chip",  # Form title
            "route": "/autocoupling",  # The URL rule (as given by "add_view") of your submission view
            "isTask": True,  # This forms submission starts a background task
            "isCollapsible": False,  # This form cannot be collapsed into an accordion
            "submitLabel": "Start Coupling",  # Label for the form submit button
            "schema": [  # List of dictionaries. Each element is a form component.
                {
                    "fieldType": "numberInput",
                    "name": "step_x_min",
                    "label": "Start Position for the Lens scan in X",
                    "min": 0.,  # HTML number input attribute
                    "step": 50,  # HTML number input attribute
                    "default": 0.,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "step_x_max",
                    "label": "End Position for the Lens scan in X",
                    "min": 1000.,  # HTML number input attribute
                    "step": 50,  # HTML number input attribute
                    "default": 3000.,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "step_x_steps",
                    "label": "Stepsize for the Lens scan in X",
                    "min": 50.,  # HTML number input attribute
                    "step": 50,  # HTML number input attribute
                    "default": 50.,  # HTML number input attribute
                },                 
                {
                    "fieldType": "numberInput",
                    "name": "step_z_min",
                    "label": "Start Position for the Lens scan in Z",
                    "min": 0.,  # HTML number input attribute
                    "step": 50.,  # HTML number input attribute
                    "default": 0.,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "step_z_max",
                    "label": "End Position for the Lens scan in Z",
                    "min": 1000.,  # HTML number input attribute
                    "step": 50.,  # HTML number input attribute
                    "default": 2000.,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "step_z_steps",
                    "label": "Stepsize for the Lens scan in Z",
                    "min": 0.,  # HTML number input attribute
                    "step": 50.,  # HTML number input attribute
                    "default": 100.,  # HTML number input attribute
                },                                                
                {
                    "fieldType": "selectList",
                    "name": "serialport",
                    "label": "Serial Port",
                    "value": "/dev/ttyUSB0",
                    "options": ["/dev/ttyUSB0","/dev/ttyUSB1"],
                },

            ],
        }
    ],
}


## Create extension

# Create your extension object
autocoupling_extension = BaseExtension("org.openflexure.autocoupling_extension", version="0.0.0")

# Add methods to your extension
autocoupling_extension.add_method(auto_coupling, "auto_coupling")

# Add API views to your extension
autocoupling_extension.add_view(AutocouplingAPI, "/autocoupling")

# Add OpenFlexure eV GUI to your extension
autocoupling_extension.add_meta("gui", build_gui(extension_gui, autocoupling_extension))
