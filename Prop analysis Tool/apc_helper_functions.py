import pickle

import numpy as np
import pandas as pd
from scipy import optimize

import matplotlib.pyplot as plt

path_to_interpolator_files = "apc_prop_helper/20_APC_interpolator_files/"
#path_to_interpolator_files = "20_APC_interpolator_files/"
db_filename = "APC-Prop-DB.pkl"


def get_thrust_from_RPM_speed(prop,V_ms,RPM,verbose=False):

    #print(path_to_interpolator_files)

    # speed in m/s

    filename = path_to_interpolator_files + prop + "_thrust_interpolator.pkl"
    interpolator = pickle.load(open(filename,"rb"))


    thrust_N = interpolator(V_ms,RPM)

    if ((thrust_N == -99) & (verbose == True)):
        print("parameters are out of the props envelopte")

    return float(thrust_N)


def get_power_from_RPM_speed(prop,V_ms,RPM,verbose=False):

    # speed in m/s

    filename = path_to_interpolator_files + prop + "_power_interpolator.pkl"
    interpolator = pickle.load(open(filename,"rb"))


    power_W = interpolator(V_ms,RPM)

    if (power_W == -99) & (verbose ==True):
        print("parameters are out of the props envelopte")

    return float(power_W)
    
def get_power_from_thrust_speed(prop,T_req,V_ms,get_RPM=False):

    def fun(RPM,interp,thrust_request,V_ms):
        thrust_N = interp(V_ms,RPM)
    
        return thrust_N - thrust_request
    
    
    filename = path_to_interpolator_files + prop + "_thrust_interpolator.pkl"
    interp = pickle.load(open(filename,"rb"))

    RPMs = [x[1] for x in interp.points]
    
    min_RPM = min(RPMs)
    max_RPM = max(RPMs)

    max_thrust = interp(V_ms,max_RPM)

    if T_req > max_thrust:
        print("Thrust Request exceeds propeller limits!")
        return # get_power_from_RPM_speed(prop,V_ms,max_RPM,verbose=True)

    res = optimize.root_scalar(fun,args=(interp,T_req,V_ms),bracket=(min_RPM,max_RPM),rtol=.001)

    RPM = int(res.root)

    power_W = get_power_from_RPM_speed(prop,V_ms,RPM,verbose=True)
    
    if get_RPM == False:    
        return power_W
    else:
        return power_W,RPM
    
    
    
    
def plot_prop_thrust(prop):


    
    df = pd.read_pickle(db_filename)
    prop_df = df[df.PROP==prop] 
    
    fig, ax = plt.subplots(1,figsize=[12,8])
    
    for RPM in prop_df.RPM.unique():
            
        pdf = prop_df[prop_df.RPM==RPM]
        ax.plot(pdf.V_ms,pdf.Thrust_N,label = "RPM ="+str(RPM))
        
        
    #ax.plot(speeds,thrusts,color="grey",marker="x",lw=0.5,label=" Thrust prediction for 22500 RPM")
    
    
    ax.legend(loc="best",ncol=2)
    ax.grid(True)
    
    
    ax.set_xlabel("Speed [m/s]")
    ax.set_ylabel("Thrust [N]")
    
    plt.title("Prop Thrust Mapping "+prop)
    
    
def plot_prop_power(prop):

    df = pd.read_pickle(db_filename)
    prop_df = df[df.PROP==prop] 
    
    fig, ax = plt.subplots(1,figsize=[12,8])
    
    for RPM in prop_df.RPM.unique():
            
        pdf = prop_df[prop_df.RPM==RPM]
        ax.plot(pdf.V_ms,pdf.PWR_W,label = "RPM ="+str(RPM))
        
           
    
    ax.legend(loc="best",ncol=2)
    ax.grid(True)
    
    #ax.set_ylim(-1,40)
    
    ax.set_xlabel("Speed [m/s]")
    ax.set_ylabel("Power [W]")
    
    plt.title("Prop Power Mapping "+prop)
    
    
    
def plot_prop_max_thrust(prop):
    filename = path_to_interpolator_files + prop + "_thrust_interpolator.pkl"
    interp = pickle.load(open(filename,"rb"))
    
    speeds = [x[0] for x in interp.points]
    RPMs = [x[1] for x in interp.points]
    
    min_speed = min(speeds)
    max_speed = max(speeds)
    min_RPM = min(RPMs)
    max_RPM = max(RPMs)
    
    thrusts = []
    
    pspeeds = np.linspace(min_speed,max_speed,50)
    
    for speed in pspeeds:  
        thrusts.append(interp(speed,max_RPM))
    
                    
    fig, ax = plt.subplots(1,figsize=[10,6])
    
    ax.plot(pspeeds,thrusts)    
    
    ax.set_ylim(0,max(thrusts)+1)
    
    ax.grid("both")
    
    ax.set_title("Max Thrust for APC "+prop+" propeller",size=15)
    ax.set_xlabel("Airspeed [m/s]")
    ax.set_ylabel("Thrust [N]")
