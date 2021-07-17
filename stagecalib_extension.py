from labthings.extensions import BaseExtension
from labthings import find_component, fields
from labthings.views import ActionView
from typing import Tuple
from labthings.schema import Schema
from labthings import find_extension

import time
import io  # Used in our capture action
import logging
import numpy as np
try:
    import cv2
except:
    print("CV2 is missing..still trying to run the Stagecalib extension")

# Used to run our stagecalib in a background thread
from labthings import update_action_progress as update_task_progress

from openflexure_microscope.captures.capture_manager import (
    generate_basename,
)

# Used to convert our GUI dictionary into a complete eV extension GUI
from openflexure_microscope.api.utilities.gui import build_gui

stdvthres = 100
mydarkval = 0

def find_sample(camera, microscope, darkval=0, nsearch = 3, distsearch=1000):
    # move as long as you find a brightness change

    iiter = 0
    currentpos = microscope.stage.position
    myvals = []
    while True:
        # snake scan
        if iiter % 4 in (1, 2): dir_x = 1
        else: dir_x = -1
        if iiter % 4 in (2,3): dir_y = 1
        else: dir_y = -1
        
        ix = dir_x*((iiter+1)// 4)
        iy = dir_y*((iiter) // 4)

        # frames behave weird
        mymean = np.mean(capture_in_background(camera))
        myvals.append(mymean)
        print("Iter: "+str(iiter) + ", mean: "+str(mymean))
        iiter += 1
        
        if mymean > 80 and iiter >0:
            break

        myx = currentpos[0]+(ix*distsearch)
        myy = currentpos[1]+(iy*distsearch)
        microscope.stage.move_abs((myx,myy,0))
        
        if iiter > 20:
            microscope.stage.move_abs(currentpos)
            break
        
            
    return microscope.stage.position

def capture_in_background(camera):
    output = io.BytesIO()
    camera.capture(output, use_video_port=True, resize=(320, 240))
    frame_data = np.frombuffer(output.getvalue(), dtype=np.uint8)
    frame = cv2.imdecode(frame_data, cv2.IMREAD_GRAYSCALE)
    del output
    return frame

## Extension methods
def move_stage(
    microscope,
    task_name,
    n_scans,
    metadata: dict = {}
):

    with microscope.stage.lock:

        if task_name == 'Homing':
            microscope.stage.go_home(offsetx=0, offsety=0)
            microscope.stage.move_rel((0,0,1)) # update gui? 
        elif task_name == 'Search Sample':            
            # Retrieve frame data
            camera = microscope.camera
            sample_pos = find_sample(camera, microscope, nsearch = 5, distsearch=1000)
        elif task_name == "Scan 96 well plate":
            # first we want to move the stage to the end position
            microscope.stage.go_home(offsetx=0, offsety=0)
            autofocus_extension = find_extension("org.openflexure.autofocus")

            # Retrieve frame data
            camera = microscope.camera   
            
            # estimate the mean value in the background
            frame = capture_in_background(camera)  
            mydarkval = np.mean(frame)
            print("My darkval: "+str(mydarkval))     

            N_sample_found = 0
            # go and find the first well
            for iter in range(15):
                microscope.stage.move_rel((300, 300, 0))
                frame = capture_in_background(camera)  
                mymean = np.mean(frame)
                if mymean > 80:
                    N_sample_found += 1
                    if N_sample_found > 3:
                        # make sure you really found a sample
                        break
                print("My darkval: "+str(mymean))   

            # save value for later
            sample_pos = microscope.stage.position

            # construct the scan positions
            Nx = 12
            Ny = 8
            distmove = 9000
            scanpositions = []
            scanpositions.append((0,0,0))
            
            for iiter in range(Nx*Ny):
                # snake scan
                if ((1+iiter)%(Nx))==0: dir_x = 1
                else: dir_x = 0
                if (iiter//(Nx))%2: dir_y = -1
                else: dir_y = 1
                if(dir_x == 1): dir_y = 0
                ix = distmove * dir_x
                iy = distmove * dir_y
                scanpositions.append((ix,iy,0))
            scanpositions = np.array(scanpositions)

            # Location to store video
            folder = "WellplateScan"
            basename = generate_basename()
            filename = f"{basename}"
            positionold = microscope.stage.position
            for it in range(n_scans):
                microscope.stage.move_abs(positionold)
                for iiter in range(scanpositions.shape[0]):
                    microscope.stage.move_rel((scanpositions[iiter,0],scanpositions[iiter,1],scanpositions[iiter,2]))
                    # Run fast autofocus. Client should provide dz ~ 2000
                    autofocus_dz = 3000
                    autofocus_extension.fast_autofocus(microscope, dz=autofocus_dz)
                    microscope.capture(
                        filename=filename+"_96WellplateScan_"+str(it)+"_" + str(iiter), 
                        folder=folder, 
                        temporary=False
                    )

                
                    # Much faster Capture but won't be added to the GUI
                    # output = './openflexure/data/micrographs/' + folder + '/' + filename+"_96WellplateScan_" + str(iiter)
                    # microscope.camera.capture(output)


            
            microscope.stage.move_abs((sample_pos))        



        elif task_name == 'Focus Calibration':
            # first we want to move the stage to the end position
            microscope.stage.go_home(offsetx=0, offsety=0)

            # Retrieve frame data
            camera = microscope.camera

            # estimate the mean value in the background
            frame = capture_in_background(camera)  
            mydarkval = np.mean(frame)
            print("My darkval: "+str(mydarkval))     

            posx_max = 60000
            posy_max = 100000
            myposarray = np.array(((0,0,0), (posx_max,0,0),(0,posy_max,0),(-posx_max,0,0)))
            myzero = ((0,0,0))
            myoldspeed_x,myoldspeed_y,myoldspeed_z = microscope.stage.board.getspeed()
            microscope.stage.board.setspeed(200,150,40)
            for N in range(n_scans):
                for i in range(myposarray.shape[0]):
                    print("Move to: " +str(myposarray[i,:])+"mm")
                    microscope.stage.move_rel((myposarray[i,0],myposarray[i,1],myposarray[i,2]))
                    if N==0 :
                       sample_pos = find_sample(camera, microscope,darkval=mydarkval)
                       if i==0:
                           myzero = sample_pos
                    print("check focus")
                    time.sleep(10)
                microscope.stage.move_abs((myzero))
            microscope.stage.board.setspeed(myoldspeed_x,myoldspeed_y,myoldspeed_z)                  
            print("Done with stage calibration..")

        elif task_name == "Plate-Shaking":
            microscope.stage.do_plateshaking(d_shift=100, time_shake = n_scans)


## Extension views
class StageCalibAPI(ActionView):
    """
    Record a stagecalib
    """
    args = {
        "task_name": fields.String(
            missing="Homing", example="Homing", description="Task to be done by the stage"
        ),
        "n_scans": fields.Integer(
            missing=1, example=1, description="Number of roundtrips/scans"
        ),
    }




    def post(self, args):
        task_name = args.get("task_name")
        n_scans = args.get("n_scans")

        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")

        return move_stage(
            microscope,
            task_name,
            n_scans,
            metadata=microscope.metadata,
        )


## Extension GUI (OpenFlexure eV)
# Alternate form without any dynamic parts
extension_gui = {
    "icon": "query_builder",  # Name of an icon from https://material.io/resources/icons/
    "forms": [  # List of forms. Each form is a collapsible accordion panel
        {
            "name": "Acquire a stagecalib series",  # Form title
            "route": "/stagecalib",  # The URL rule (as given by "add_view") of your submission view
            "isTask": True,  # This forms submission starts a background task
            "isCollapsible": False,  # This form cannot be collapsed into an accordion
            "submitLabel": "Start Process",  # Label for the form submit button
            "schema": [  # List of dictionaries. Each element is a form component.
                {
                    "fieldType": "selectList",
                    "name": "task_name",
                    "label": "Task",
                    "value": "Focus Calibration",
                    "options": ["Focus Calibration","Homing","Search Sample","Plate-Shaking" "Scan 96 well plate"],
                },
                {
                    "fieldType": "numberInput",
                    "name": "n_scans",  # Name of the view arg this value corresponds to
                    "label": "Number of images",
                    "min": 1,  # HTML number input attribute
                    "default": 1,  # HTML number input attribute
                },
            ],
        }
    ],
}


## Create extension

# Create your extension object
stagecalib_extension = BaseExtension("org.openflexure.stagecalib_extension", version="0.0.0")

# Add methods to your extension
stagecalib_extension.add_method(move_stage, "move_stage")

# Add API views to your extension
stagecalib_extension.add_view(StageCalibAPI, "/stagecalib")

# Add OpenFlexure eV GUI to your extension
stagecalib_extension.add_meta("gui", build_gui(extension_gui, stagecalib_extension))
