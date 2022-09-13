import pandas as pd
import geopandas as gpd
import numpy as np
from pyproj.transformer import Transformer
import shapely
from shapely.geometry import asLineString
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
import os
import glob
import pyodbc
from matplotlib import style

def crossSlope():
    filesList = os.listdir("Cross-slope")
    filesList = glob.glob("Cross-slope/*.csv")
#Cutting the sting to only get the file name from dir\\filename

    final_res = []

    for file in filesList:
        filename = file
        filename = file.split("\\")[1].split(".")[0]


        #accessing the crosslope database file to get desired run values.
        MDB = 'C:/Users/mvorr/OneDrive - Georgia Institute of Technology/Georgia Tech/Spring 2022/Smarcity Lidar/Code/crosslopedb.mdb'
        DRV = 'Microsoft Access Driver (*.mdb, *.accdb)'
            # connect to db
        con = pyodbc.connect('DRIVER={};DBQ={}'.format(DRV, MDB))
        cur = con.cursor()

        # Get Run_GUID
        SQL = 'SELECT Run_GUID FROM RunDeviceData WHERE FileName=\'' + filename + '.las\';'
        run_guid = cur.execute(SQL).fetchall()
        run_guid = run_guid[0][0]

        # Get Run_ID
        SQL = 'SELECT Run_ID FROM Run WHERE Run_GUID=\'' + run_guid + '\';'
        run_id = cur.execute(SQL).fetchall()
        run_id = str(run_id[0][0])
        # Get X,Y,Z corresponding to Run_ID
        SQL = 'SELECT x,y,z FROM RunGraph WHERE ObjId=' + run_id + ';'  # your query goes here
        coordinates = cur.execute(SQL).fetchall()

        cur.close()
        con.close()
        #Fetching the GPS data and crossSlope data
        GPSdata = pd.read_csv("RunGraph.csv")
        GPSdf = pd.DataFrame(GPSdata)
        GPSdf = GPSdf.loc[GPSdf["ObjId"] == 174]
        GPSdf = GPSdf.filter(['x','y','z'])

        LidarData = pd.read_csv("crosslopeData.csv")
        #Making a GPS Geo data frame
        gpsGDF = gpd.GeoDataFrame(data=GPSdf, crs=4326, geometry=gpd.points_from_xy(GPSdf["x"],GPSdf["y"]))
        #making the GPSGDF a numpy array of points
        point_list = gpsGDF.to_numpy()
        #Converting these lat,long point to feet,feet
        projectionTrans = Transformer.from_crs(4326, 'ESRI:102604', always_xy=True)
        projPoints = np.array(projectionTrans.transform(point_list[:,0], point_list[:, 1], direction="forward")).T
        #making a lineSting object
        line = asLineString(projPoints)
        #making a lidarpoint GDF
        LidarGDF = gpd.GeoDataFrame(data=LidarData, crs=4326, geometry=gpd.points_from_xy(LidarData["X"],LidarData["Y"]))
        LidarGDF = LidarGDF.to_crs('ESRI:102604')
        #making the substrings and buffers
        ROI_length = 4
        ROI_width = 12            # width of the ROI normal to the road
        sub_line_list = []
        midlist = []

        for target_location in np.linspace(ROI_length/2, line.length, int(line.length/26)):
            sub_line= shapely.ops.substring(line, target_location-ROI_length/2, target_location+ROI_length/2)   
            sub_line_list.append(sub_line)
            midlist.append(line.interpolate(target_location))
        #making the sindex
        for i in sub_line_list:
            index_array = LidarGDF.sindex.query(i.buffer(ROI_width/2, cap_style=2),predicate="contains")
            if(len(index_array) == 0):
                continue
            query_results = LidarGDF.iloc[index_array]
            #making the regression model to get the slope of the line
        slopes = []
        for line1 in sub_line_list:
            left_line = line1.parallel_offset(ROI_width/2, side="left")
            ROIpts = LidarGDF.iloc[index_array]
            ROIpts
            dists = []
            z_vals = []
            for i, row in ROIpts.iterrows():
                
                dists.append(row['geometry'].distance(left_line))
                
                z_vals.append(row['Z']*3.2808) #Multiplied Z vals by the feet metric to get a better correlation.
            style.use('dark_background')
            regression_line = LinearRegression(fit_intercept=True)
            dists1 = np.array(dists)
            z_vals1 = np.array(z_vals)
            regression_line.fit(dists1.reshape(-1, 1), z_vals1)
            slope = regression_line.coef_ # y =mx+b; .coef_ -> m which is the slope
            print(regression_line.coef_) #Crosslope
            intercept  = regression_line.intercept_
            print(slope, intercept)
            slopes.append(slope[0])
            plt.scatter(dists1, z_vals1, alpha=0.6, color= "green")
            style.use('dark_background')
            x = [0, 12]
            y = [intercept, slope*12 + intercept]
            if(filename == "05102012Cur(0)_GLS"):
                plt.plot(x, y, color='red')
        data = {'Filename': filename,"Cross-slopes(%)": np.array(slopes)*100,  }
        res = pd.DataFrame(data)
        geores = gpd.GeoDataFrame(data, geometry=midlist, crs= 'ESRI:102604')
        geores = geores.to_crs(4326)
        res['X'], res['Y'] = geores['geometry'].x, geores['geometry'].y
        final_res.append(res)
    for frame in range(len(final_res)):
        final_res[frame].to_csv("crossSlopes/crossSlope{index}.csv".format(index = frame))




