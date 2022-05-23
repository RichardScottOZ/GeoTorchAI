
import os
from typing import Optional, Callable
import numpy as np
import rasterio
import torch
from torch import Tensor
from torchvision.datasets.utils import download_url
from torchvision.datasets.utils import extract_archive
from torch.utils.data import Dataset, DataLoader, sampler
from torchvision.datasets import ImageFolder
from kaggle.api.kaggle_api_extended import KaggleApi
from PIL import Image


## Please cite https://www.kaggle.com/code/cordmaur/38-cloud-data-preparation?scriptVersionId=31357028
class Cloud38Dataset(Dataset):

	SPECTRAL_BANDS = ["red", "green", "blue", "nir"]
	RGB_BANDS = ["red", "green", "blue"]

	def __init__(self, root, download = False, bands = SPECTRAL_BANDS, transform: Optional[Callable] = None, target_transform: Optional[Callable] = None):
		super().__init__()
		# first check if selected bands are valid. Trow exception otherwise
		if not self._isValidBands(bands):
			# Trow error instead of printing
			print("Invalid band names")
			return

		self.selectedBandIndices = torch.tensor([self.SPECTRAL_BANDS.index(band) for band in bands])
		self.transform = transform
		self.target_transform = target_transform
		self.image_paths = []

		if download:
			api = KaggleApi()
			api.authenticate()
			api.dataset_download_files('sorour/38cloud-cloud-segmentation-in-satellite-images', '38-Cloud_training', root)
			extract_archive(root + "/38-Cloud_training/38cloud-cloud-segmentation-in-satellite-images.zip", root + "/38-Cloud_training")

		image_folders = ["train_red", "train_green", "train_blue", "train_nir"]
		label_folder = "train_gt"
		data_dir = self._getPath(root)
		band_indices = self.selectedBandIndices.numpy()
		folder_band_1 = data_dir + "/" + image_folders[band_indices[0]]
		files = os.listdir(folder_band_1)
		for i in range(len(files)):
			if os.path.isfile(folder_band_1 + "/" + files[i]):
				img_path = {}
				if i == 0:
					color_name = files[i].split("_")[0]
				for index in band_indices:
					img_path[self.SPECTRAL_BANDS[index]] = data_dir + "/" + image_folders[index] + "/" + files[i].replace(color_name, self.SPECTRAL_BANDS[index])
				img_path["gt"] = data_dir + "/" + label_folder + "/" + files[i].replace(color_name, "gt")
				self.image_paths.append(img_path)


	def __len__(self) -> int:
		return len(self.image_paths)

	def __getitem__(self, index: int):
		img = []
		for band_index in self.selectedBandIndices.numpy():
			img.append(np.array(Image.open(self.image_paths[index][self.SPECTRAL_BANDS[band_index]])))
		img = torch.tensor(img, dtype=torch.float32)
		label = torch.tensor(np.array(Image.open(self.image_paths[index]['gt'])), dtype=torch.torch.int64)

		if self.transform is not None:
			img = self.transform(img)
		if self.target_transform is not None:
			label = self.target_transform(label)

		return img, label

	def _getPath(self, data_dir):
		while True:
			folders = os.listdir(data_dir)
			if "train_red" in folders or "train_green" in folders or "train_blue" in folders:
				return data_dir

			for folder in folders:
				if os.path.isdir(data_dir + "/" + folder):
					data_dir = data_dir + "/" + folder

		return None


	def _isValidBands(self, bands):
		for band in bands:
			if band not in self.SPECTRAL_BANDS:
				return False
		return True






