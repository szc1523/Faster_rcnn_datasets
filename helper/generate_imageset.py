f = open('/home/szc/spyderwork/faster-rcnn-kitti/data/kitti/ImageSets/imageset.txt','w')
# training
#iamge_index = ['{:0>6}'.format(x) for x in range(6000)] #or 6000

# testing
iamge_index = ['{:0>6}'.format(x) for x in range(6000, 7481)] #20%
#debug
#iamge_index = ['{:0>6}'.format(x) for x in range(100)] 

#f.write('hi, there\n')
print(iamge_index)
for item in iamge_index:
    f.write(item + '\n')
#f.write(iamge_index)
f.close()