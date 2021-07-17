from labthings.extensions import BaseExtension
from labthings.find import find_component
from labthings.views import ActionView

from labthings.schema import Schema
from labthings import find_component, fields
from labthings import (
    current_action,
    fields,
    find_component,
    find_extension,
    update_action_progress,
)

from flask import send_file  # Used to send images from our server
import io  # Used in our capture action
import time  # Used in our wellscan function
import numpy as np


# Used in our wellscan function
from openflexure_microscope.captures.capture_manager import (
    generate_basename,
)

# Used to convert our GUI dictionary into a complete eV extension GUI
from openflexure_microscope.api.utilities.gui import build_gui

## Extension methods




def wellscan(microscope, autofocus, offset_x, offset_y, 
    	Nx=3, Ny=3, t_period=60, well_to_well_steps = 9000,
        autofocus_dz=2000, autofocus_Nz=11):
    """
    Save a set of images in a wellscan

    Args:
        microscope: Microscope object
        offset_x (int): Number of images to take
        offset_y (int/float): Time, in seconds, between sequential captures
    """
    base_file_name = generate_basename()
    folder = "wellscan_{}".format(base_file_name)

    Nx = int(Nx)
    Ny = int(Ny)
    t_period = int(t_period)
    well_to_well_steps = int(well_to_well_steps)
    
    # Take exclusive control over both the camera and stage
    with microscope.camera.lock, microscope.stage.lock:
        # microscope parameters
        offset_z = microscope.stage.position[-1]

        name_experiment = base_file_name+"_test_large_scan_new_"

        
        # move to the home positoin
        print("Start moving to the position")
        microscope.stage.move_abs((offset_x,offset_y,offset_z))
        #autofocus.autofocus(microscope, np.linspace(-1500, 1500, 11))

        i_well = 0
        i_experiment = 0
 
        print("Start scan")
        #%%
        focus_pos_list = []
        folder = "SCAN_{}".format(base_file_name)
        i_image = 0


        time_last = 0
        while(True):
            if time.time()-time_last>t_period:
 
                time_last = time.time()
                i_well = 0
                last_offset_z_row = offset_z
                for wellpos_y in range(Nx):
                    for wellpos_x in range(Nx):

                        if last_offset_z_row == 0:
                            offset_z = last_offset_z_row

                        print("Move microscope")
                        current_x, current_y = offset_x+well_to_well_steps*wellpos_x,offset_y+well_to_well_steps*wellpos_y
                        
                        if (i_experiment % 10)== 0:
                            if i_well == 0:
                                focus_pos_list = []
                            
                            microscope.stage.move_abs((current_x, current_y, offset_z))
                            autofocus.autofocus(microscope, np.linspace(-autofocus_dz, autofocus_dz, autofocus_Nz))
                            offset_z = microscope.stage.position[-1]                                

                            focus_pos_list.append(offset_z)

                            if last_offset_z_row == 0:
                                last_offset_z_row = offset_z
                        else:
                            offset_z = focus_pos_list[i_well]
                        microscope.stage.move_abs((current_x, current_y, offset_z))
                        print("offset_z:"+str(offset_z))

                        bayer = False
                        tags = ["xy_scan_"+str(wellpos_x)+"_"+str(wellpos_y)]
                        temporary =  False
                        use_video_port = True
                        filename = name_experiment+str(i_experiment)+"_"+str(i_well)+"_"+str(i_image)+"_"+str(wellpos_x)+"_"+str(wellpos_y)

                        time.sleep(1) # wait for debouncing
                        microscope.capture(filename=filename,
                            folder=folder,
                            temporary=temporary,
                            use_video_port=use_video_port,
                            bayer=bayer,
                            tags=tags,
                        )
                        print(filename)

                        i_image += 1

                        i_well += 1

                i_experiment += 1

                


## Extension views
class wellscanAPI(ActionView):
    """
    Take a series of images in a wellscan, running as a background task
    """
    args = {
            "offset_x": fields.Integer(
                missing=1, required=False, example=3000, description="Offset X"
            ),
            "offset_y": fields.Number(
                missing=1, required=False, example=2000, description="Offset Y"
            ),
            "N_x": fields.Number(
                missing=1, required=False, example=3, description="Number wells X"
            ),
            "N_y": fields.Number(
                missing=1, required=False, example=3, description="Number wells Y"
            ),
            "autofocus_dz": fields.Number(
                example=2000, description="Searchdistance for Autofocus +/-"
            ),
            "autofocus_Nz": fields.Number(
                example=11, description="Searchsteps for Autofocus"
            ),
            "well_to_well_steps": fields.Number(
                example=9000, description="Well to Well steps"
            ),            
        }
    
    def post(self, args):
        # Find our microscope component
        microscope = find_component("org.openflexure.microscope")
        autofocus = find_extension("org.openflexure.autofocus")
        # parse arguments
        offset_x = args.get("offset_x")
        offset_y = args.get("offset_y")

        N_x = args.get("N_x")
        N_y = args.get("N_y")

        well_to_well_steps = args.get("well_to_well_steps")
        autofocus_dz = args.get("autofocus_dz")
        autofocus_Nz = args.get("autofocus_Nz")

        # Create and start "wellscan", running in a background task
        return wellscan(microscope, autofocus, offset_x, offset_y, N_x, N_y,
                t_period, well_to_well_steps,
                autofocus_dz, autofocus_Nz)
        
## Extension GUI (OpenFlexure eV)
# Alternate form without any dynamic parts
extension_gui = {
    "icon": "wellscan",  # Name of an icon from https://material.io/resources/icons/
    "forms": [  # List of forms. Each form is a collapsible accordion panel
        {
            "name": "Start a wellscan",  # Form title
            "route": "/wellscan",  # The URL rule (as given by "add_view") of your submission view
            "isTask": True,  # This forms submission starts a background task
            "isCollapsible": False,  # This form cannot be collapsed into an accordion
            "submitLabel": "Start",  # Label for the form submit button
            "schema": [  # List of dictionaries. Each element is a form component.
                {
                    "fieldType": "numberInput",
                    "name": "offset_x",  # Name of the view arg this value corresponds to
                    "label": "Offset X",
                    "min": 0,  # HTML number input attribute
                    "default": 3000,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "offset_y",
                    "label": "Offset Y",
                    "min": 0,  # HTML number input attribute
                    "default": 2000,  # HTML number input attribute
                },
		        {
                    "fieldType": "numberInput",
                    "name": "N_x",  # Name of the view arg this value corresponds to
                    "label": "Number wells X",
                    "min": 1,  # HTML number input attribute
                    "default": 3,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "N_y",
                    "label": "Number wells Y",
                    "min": 0,  # HTML number input attribute
                    "default": 3,  # HTML number input attribute
                },
		        {
                    "fieldType": "numberInput",
                    "name": "autofocus_dz",  # Name of the view arg this value corresponds to
                    "label": "Searchdistance for Autofocus +/-X",
                    "min": 500,  # HTML number input attribute
                    "default": 2000,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "autofocus_Nz",
                    "label": "Searchsteps for Autofocus",
                    "min": 5,  # HTML number input attribute
                    "default": 11,  # HTML number input attribute
                },
                {
                    "fieldType": "numberInput",
                    "name": "well_to_well_steps",
                    "label": "Well to Well steps",
                    "min": 0,  # HTML number input attribute
                    "default": 9000,  # HTML number input attribute
                },
            ],
        }
    ],
}


## Create extension

# Create your extension object
my_extension = BaseExtension("com.myname.wellscan-extension", version="0.0.0")

# Add methods to your extension
my_extension.add_method(wellscan, "wellscan")

# Add API views to your extension
my_extension.add_view(wellscanAPI, "/wellscan")

# Add OpenFlexure eV GUI to your extension
my_extension.add_meta("gui", build_gui(extension_gui, my_extension))

