import os
import cv2
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import tzlocal
import ffmpeg

camera = cv2.VideoCapture(0)
while True:
  good, img = camera.read()
  imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
  cv2.imshow("Image", img)
  if cv2.waitKey(1) == ord('q'):
    break