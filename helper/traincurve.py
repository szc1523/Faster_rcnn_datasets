import os
os.chdir('../faster-rcnn-kitti/caffe-fast-rcnn')
import sys
sys.path.insert(0, './python')
import caffe

from pylab import *

os.chdir('../tools')
import _init_paths
from fast_rcnn.config import cfg

"""parse train loss"""

import re
#train_log_name = 'faster_rcnn_end2end_VGG16_.txt.2016-05-23_15-31-51'
#train_log_path = os.path.join(cfg.ROOT_DIR, 'experiments/logs', train_log_name)

train_log_name = 'train.txt'
train_log_path = os.path.join(cfg.ROOT_DIR,
                              'experiments/processing/VGG16prefaster/iter_file', 
                              train_log_name)

pattern = 'Iteration [0-9]+, loss = [0-9\.]+'

f = open(train_log_path)
lines = f.readlines();
f.close()

train_iter = []
train_loss = []
ix = 0
for line in lines:
    #print line    
    matchObj = re.search(pattern, line, flags=0)
    if matchObj:        
        #print(matchObj.group())
        temp = matchObj.group().split(',')
        train_iter.append(int(temp[0].split()[1]))
        train_loss.append(float(temp[1].split()[2]))
        
        #print(Iter)
        #print(Loss)
#niter = len(train_iter)
#print(niter)

train_iter[4000:] = []  #1000 is 2WT
train_loss[4000:] = []


"""parse test accuracy"""

os.chdir('..') #now in root folder
import subprocess

import time

# may use subprocess.check_output instead
test_iter = ['10000', '20000', '30000', '40000', '50000','60000', '70000', '80000']#,'90000']#,'100000']
test_ap = []

start = time.time()
for obj in test_iter:
    #attention!  change the save folder of a new model!!!
    filename = os.path.join(cfg.ROOT_DIR, 
                            'experiments/processing/VGG16prefaster/iter_file', 
                            'test_iter{}.txt')
    print(os.path.exists(filename.format(obj)))                            
    if not os.path.exists(filename.format(obj)):
        with open(filename.format(obj), 'w') as logfile:
            subprocess.call(['./test_iter.sh', obj, 'VGG16'], stdout=logfile, shell=False)
    
    f = open(filename.format(obj))
    lines = f.readlines();
    
    for line in lines:
        print(line)
        matchObj = re.search('AP for Car = [0-9\.]+', line, flags=0)
        if matchObj:
            test_ap.append(float(matchObj.group().split()[4]))
            
    f.close()
end = time.time()
t = end - start  
print('time', t)          

test_iter = [10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000]#, 90000]#$, 100000]

_, ax1 = subplots()
ax2 = ax1.twinx()
ax1.plot(train_iter, train_loss)
ax2.plot(test_iter, test_ap, 'r')
ax1.set_xlabel('iteration')
ax1.set_ylabel('train loss')
ax2.set_ylabel('test AP')

print(test_ap)