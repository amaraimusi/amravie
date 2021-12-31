
import os
import pprint
import datetime
import cv2
import glob
from pydub import AudioSegment #音声操作用　mp3関連の処理
import ffmpeg
import tkinter as tk
from vendor.CrudBase.ConfigX import ConfigX
from model.SplitVideoSound import SplitVideoSound
from model.MixingMp4Mp3 import MixingMp4Mp3

print('amaravie')

configX = ConfigX();
configs = configX.getConfigs('./config.txt');
pprint.pprint(configs)

mode = configs['mode']

if(mode == 'split_video_sound'):
    print ('mp4を音声なしmp4とmp3に分割します')
    splitVideoSound = SplitVideoSound(configs)
    splitVideoSound.run()

if(mode == 'mixing_mp4_mp3'):
    print ('mp4にmp3をミキシングします')
    mixingMp4Mp3 = MixingMp4Mp3(configs)
    mixingMp4Mp3.run()

print('Success')