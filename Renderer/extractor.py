#--------------------
#Contour Extractor
#Daniel Miron
#7/17/2013
#
#--------------------

import sys
sys.path.append(r'c:\Python27\Lib\site-packages')
import h5py
import numpy as np
import glob
import os

import pickle
import math
import time
import cv2
import threading
from Queue import Queue

from pysqlite2 import dbapi2 as sqlite

class Extractor:
    def __init__(self, out_q, directory, label_ids, resolution_level, location):
        
        self.out_q = out_q
        
        self.directory = directory
        self.w = resolution_level
        self.w_str = "w={0:08}".format(resolution_level)
        self.label_folder = self.directory +"\\ids\\tiles\\" + self.w_str
        
        self.segment_file = self.directory + "\\ids\\segmentInfo.db"
        self.z_folders = glob.glob(self.label_folder + "\\*")
        h5_file = h5py.File(glob.glob(self.z_folders[0] + "\\*")[0], "r")
        self.label_key = h5_file.keys()[0]
        self.shape = np.shape(h5_file[self.label_key][...])
        h5_file.close()
        
        self.tile_rows = self.shape[0]
        self.tile_columns = self.shape[1]
        
        self.tiles_per_layer = len(glob.glob(self.z_folders[0] + "\\*"))
        
        #taking sqrt assumes same number of tiles in x direction as y direction
        self.rows = self.shape[0]*math.sqrt(self.tiles_per_layer)
        self.columns = self.shape[1]*math.sqrt(self.tiles_per_layer)
        self.layers = len(self.z_folders)
        
        #need to figure out way to get num_tiles in each direction when not square
        '''self.rows = self.shape[0]*num_tiles_x
        self.columns =self.shape[1]*num_tiles_y'''
        
        self.label_ids = label_ids
        
        self.z_order = self.make_z_order(location[2])\
        
        color_file = h5py.File(self.directory + "\\ids\\colorMap.hdf5")
        self.color_map = color_file["idColorMap"][...]
        
    def make_z_order(self, start_z):
        z_list = []
        z_list.append(start_z)
        offset= 1
        #continue adding on each side of location until both side filled
        while (start_z>= offset or start_z + offset < self.layers):
            if (start_z>=offset): #don't add z<0
                z_list.append(start_z-offset)
            if (start_z +offset < self.layers): #don't add z>self.layers
                z_list.append(start_z+offset)
            offset +=1
        return z_list
        
    def run(self):
        for label_set in self.label_ids:
            color = self.color_map[label_set[0] % len(self.color_map)]
            #color = self.color_map[1]
            for z in self.z_order:
                contours = self.find_contours(label_set, [z])
                if contours != []:
                    self.out_q.put([contours, color])
        
    def find_contours(self, label_ids, z_list):
        tot_contours = []
        for label in label_ids:
            tile_list = self.get_tile_list(label, z_list)
            for tile in tile_list:
                x = tile[1]
                y = tile[2]
                z = tile[3]
                if True:
                    z_folder = self.z_folders[z]
                    tile_files = glob.glob(z_folder + "\\*")
                    for tile_name in tile_files:
                        if os.path.basename(tile_name) == "y={0:08},x={1:08}.hdf5".format(y, x):
                            t_file = h5py.File(tile_name, "r")
                            labels = t_file[self.label_key][...]
                            labels[labels!=label] = 0
                            labels[labels==label] = 255
                            labels = labels.astype(np.uint8)
                            t_file.close()
                            buffer_array = np.zeros((np.shape(labels)[0]+2, np.shape(labels)[1]+2), np.uint8) #buffer by one pixel on each side
                            buffer_array[1:-1, 1:-1] = labels
                            contours, hierarchy  = cv2.findContours(buffer_array, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                            if not contours == []:
                                contours = [np.array(cnt) for cnt in contours]
                                for idx, cnt in enumerate(contours):
                                    new_cnt = np.zeros((cnt.shape[0], 3))
                                    new_cnt[:, 0] = cnt[:, 0, 0] - 1 + x * self.tile_columns
                                    new_cnt[:, 1] = cnt[:, 0, 1] - 1 + y*self.tile_rows
                                    new_cnt[:, 2] = z
                                    contours[idx] = new_cnt
                                tot_contours+=contours
                        
        return tot_contours
        
    def get_tile_list(self, label, z_list):
        con = sqlite.connect(self.segment_file)
        cur = con.cursor()
        #w = 0 requirement specifies highest resolution
        cur.execute('select w,x,y,z from idTileIndex where w =' +str(self.w) + ' AND id =' + str(label))
        tile_list = cur.fetchall()
        end_tile_list = []
        for tile in tile_list:
            if tile[3] in z_list:
                end_tile_list += [tile]
        return end_tile_list  
        
    

