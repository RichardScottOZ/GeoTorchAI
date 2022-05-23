
import os
import requests
from typing import Optional, Callable
import numpy as np
import rasterio
import torch
from torch import Tensor
from torchvision.datasets.utils import download_url
from torchvision.datasets.utils import extract_archive
from torch.utils.data import Dataset, DataLoader, sampler
from PIL import Image


# This dataset is based on https://github.com/FIBLAB/DeepSTN/tree/master/BikeNYC/DATA
## Gri map_height and map_width = 21 and 12
class NYC_Bike_DeepSTN_Dataset(Dataset):

    DATA_URL = "https://raw.githubusercontent.com/FIBLAB/DeepSTN/master/BikeNYC/DATA/dataBikeNYC/flow_data.npy"
    POI_URL = "https://raw.githubusercontent.com/FIBLAB/DeepSTN/master/BikeNYC/DATA/dataBikeNYC/poi_data.npy"

    def __init__(self, root, is_training_data=True, download=False, len_test = 24*14, len_closeness = 3, len_period = 4, len_trend = 4, T_closeness=1, T_period=24, T_trend=24*7):
        super().__init__()
        self.is_training_data = is_training_data

        if download:
            req = requests.get(self.DATA_URL)
            file_name = root + "/" + self.DATA_URL.split('/')[-1]
            with open(file_name, 'wb') as output_file:
                output_file.write(req.content)

            req2 = requests.get(self.POI_URL)
            file_name_poi = root + "/" + self.POI_URL.split('/')[-1]
            with open(file_name_poi, 'wb') as output_file:
                output_file.write(req2.content)

        data_dir = self._getPath(root)

        flow_data = np.load(open(data_dir + "/flow_data.npy", "rb"))
        poi_data = np.load(open(data_dir + "/poi_data.npy", "rb"))

        self._create_feature_vector(flow_data, poi_data, len_test, len_closeness, len_period, len_trend, T_closeness, T_period, T_trend)
        


    def get_min_max_difference(self):
        return self.min_max_diff


    def __len__(self) -> int:
        return len(self.Y_data)


    def __getitem__(self, index: int):

        sample = {"x_closeness": self.X_closeness[index], \
        "x_period": self.X_period[index], \
        "x_trend": self.X_trend[index], \
        "t_data": self.T_data[index], \
        "p_data": self.P_data[index], \
        "y_data": self.Y_data[index]}

        return sample


    def _getPath(self, data_dir):
        while True:
            folders = os.listdir(data_dir)
            if "flow_data.npy" in folders and "poi_data.npy" in folders:
                return data_dir

            for folder in folders:
                if os.path.isdir(data_dir + "/" + folder):
                    data_dir = data_dir + "/" + folder
        return None


    # This is replication of lzq_load_data method proposed by authors here: https://github.com/FIBLAB/DeepSTN/blob/master/BikeNYC/DATA/lzq_read_data_time_poi.py
    def _create_feature_vector(self, all_data, poi, len_test, len_closeness, len_period, len_trend, T_closeness, T_period, T_trend):
        max_data = np.max(all_data)
        min_data = np.min(all_data)
        self.min_max_diff = max_data-min_data

        len_total,feature,map_height,map_width = all_data.shape

        time=np.arange(len_total,dtype=int)
        time_hour=time%T_period
        matrix_hour=np.zeros([len_total,24,map_height,map_width])
        for i in range(len_total):
            matrix_hour[i,time_hour[i],:,:]=1

        time_day=(time//T_period)%7
        matrix_day=np.zeros([len_total,7,map_height,map_width])
        for i in range(len_total):
            matrix_day[i,time_day[i],:,:]=1

        matrix_T=np.concatenate((matrix_hour,matrix_day),axis=1)
        all_data=(2.0*all_data-(max_data+min_data))/(max_data-min_data)
        #print('mean=',np.mean(all_data),' variance=',np.std(all_data))

        if len_trend>0:
            number_of_skip_hours=T_trend*len_trend
        elif len_period>0:
            number_of_skip_hours=T_period*len_period
        elif len_closeness>0:
            number_of_skip_hours=T_closeness*len_closeness
        else:
            print("wrong")
        #print('number_of_skip_hours:',number_of_skip_hours)

        Y=all_data[number_of_skip_hours:len_total]

        if len_closeness>0:
            self.X_closeness=all_data[number_of_skip_hours-T_closeness:len_total-T_closeness]
            for i in range(len_closeness-1):
                self.X_closeness=np.concatenate((self.X_closeness,all_data[number_of_skip_hours-T_closeness*(2+i):len_total-T_closeness*(2+i)]),axis=1)
        if len_period>0:
            self.X_period=all_data[number_of_skip_hours-T_period:len_total-T_period]
            for i in range(len_period-1):
                self.X_period=np.concatenate((self.X_period,all_data[number_of_skip_hours-T_period*(2+i):len_total-T_period*(2+i)]),axis=1)
        if len_trend>0:
            self.X_trend=all_data[number_of_skip_hours-T_trend:len_total-T_trend]
            for i in range(len_trend-1):
                self.X_trend=np.concatenate((self.X_trend,all_data[number_of_skip_hours-T_trend*(2+i):len_total-T_trend*(2+i)]),axis=1)

        matrix_T=matrix_T[number_of_skip_hours:]

        if self.is_training_data:
            self.X_closeness=self.X_closeness[:-len_test]
            self.X_period=self.X_period[:-len_test]
            self.X_trend=self.X_trend[:-len_test]
            self.T_data=matrix_T[:-len_test]

            self.Y_data=Y[:-len_test]
        else:
            self.X_closeness=self.X_closeness[-len_test:]
            self.X_period=self.X_period[-len_test:]
            self.X_trend=self.X_trend[-len_test:]
            self.T_data=matrix_T[-len_test:]

            self.Y_data=Y[-len_test:]

        #X_data=[self.X_closeness, self.X_period, self.X_trend]

        len_data=self.X_closeness.shape[0]
        print('len_data='+str(len_data))

        for i in range(poi.shape[0]):
            poi[i]=poi[i]/np.max(poi[i])
        self.P_data=np.repeat(poi.reshape(1,poi.shape[0],map_height,map_width),len_data,axis=0)

        self.X_closeness = torch.tensor(self.X_closeness)
        self.X_period = torch.tensor(self.X_period)
        self.X_trend = torch.tensor(self.X_trend)
        self.T_data = torch.tensor(self.T_data)
        self.P_data = torch.tensor(self.P_data)
        self.Y_data = torch.tensor(self.Y_data)


