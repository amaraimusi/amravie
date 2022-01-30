
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
from model.JoinSilentVideAndSound import JoinSilentVideAndSound
from model.MixingMp4Mp3 import MixingMp4Mp3
from model.JoinBgms import JoinBgms
from model.BgmMixing import BgmMixing

print('amaravie')

configX = ConfigX();
configs = configX.getConfigs('./split_video_sound.txt');

mode = configs['mode']

if(mode == 'split_video_sound'):
    print ('mp4を音声なしmp4とmp3に分割します')
    splitVideoSound = SplitVideoSound(configs)
    splitVideoSound.run()
    
if(mode == 'join_silent_video_and_sound'):
    print ('音声なしmp4とmp3を連結する')
    joinSilentVideAndSound = JoinSilentVideAndSound(configs)
    joinSilentVideAndSound.run()

if(mode == 'mixing_mp4_mp3'):
    print ('mp4にmp3をミキシングします')
    mixingMp4Mp3 = MixingMp4Mp3(configs)
    mixingMp4Mp3.run()

if(mode == 'join_bgms'):
    print ('複数のbgmを連結して1つのbgmにする')
    joinBgms = JoinBgms(configs)
    joinBgms.run()

if(mode == 'bgm_mixing'):
    print ('複数のbgmを連結してmp4にミキシングします')
    bgmMixing = BgmMixing(configs)
    bgmMixing.run()

print('Success')