import pandas as pd
from PIL import Image
import numpy as np
import os

import cv2
from skimage import io
import skimage
import os
from skimage import data
from skimage.color import rgb2hsv
from scipy import ndimage

def basic_image_stats(read_from)
    filenames = []
    for filename in os.listdir(read_from):
        if filename.endswith(".jpg"):
            filenames.append(filename)

    thumbnails = {'thumbnailFilename': filenames}
    df = pd.DataFrame(thumbnails)

    def get_video_id(filename):
        return filename.split('.')[0]

    videoId = df['thumbnailFilename'].apply(lambda x: get_video_id(x))
    df.insert(loc=0, column='videoId', value=videoId)

    def calc_image_stats(read_from, filename):
        filepath = read_from + filename
        image = io.imread(filepath)

        width = image.shape[0]
        height = image.shape[1]
        size = width*height

        rgb_img = image
        hsv_img = rgb2hsv(image)
        hue_img = hsv_img[:, :, 0]
        saturation_img = hsv_img[:,:, 1]
        value_img = hsv_img[:, :, 2]

        mean_hue = np.mean(hue_img, axis=(0,1))

        mean_saturation = np.mean(saturation_img, axis=(0,1))

        mean_brightness = np.mean(value_img)

        img_grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        contrast = img_grey.std()

        sobel_x = ndimage.sobel(value_img, axis=0, mode='constant')
        sobel_y = ndimage.sobel(value_img, axis=1, mode='constant')
        edge_image = np.hypot(sobel_x, sobel_y)
        edgesum = np.sum(edge_image)

        return {'width': width,
                'height': height,
                'size': size,
                'mean_hue': mean_hue,
                'mean_saturation': mean_saturation,
                'mean_brightness': mean_brightness,
                'contrast': contrast,
                'edge_score': edgesum}
    stats = []
    df['stats'] = df['thumbnailFilename'].apply(lambda x: calc_image_stats(read_from, x))
    df2 = pd.concat([df.drop(['stats'], axis=1), df['stats'].apply(pd.Series)], axis=1)
    return df2