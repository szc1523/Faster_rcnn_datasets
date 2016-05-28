# --------------------------------------------------------
# Fast R-CNN
# Copyright (c) 2015 Microsoft
# Licensed under The MIT License [see LICENSE for details]
# Written by Ross Girshick
# Modified by Li Bin
# --------------------------------------------------------

import os
from datasets.imdb import imdb
import datasets.ds_utils as ds_utils
import xml.etree.ElementTree as ET
import numpy as np
import scipy.sparse
import scipy.io as sio
import utils.cython_bbox
import cPickle
import subprocess
import uuid

from fast_rcnn.config import cfg

from kitti_eval import kitti_eval

class kitti(imdb):
    def __init__(self, image_set, devkit_path=None):
        imdb.__init__(self, 'kitti_' + '_' + image_set)
        self._image_set = image_set
        self._devkit_path = self._get_default_path() if devkit_path is None else devkit_path
        self._data_path = os.path.join(self._devkit_path, 'training/image_2')
        self._classes = ('__background__','Car', 'Van', 'Truck', 'Cyclist','Pedestrian', 'Person_sitting', 'Tram', 'Misc' ,'DontCare')
        self._class_to_ind = dict(zip(self.classes, xrange(self.num_classes)))
        self._image_ext = '.png'
        self._image_index = self._load_image_set_index()

        self._salt = str(uuid.uuid4())
        self._comp_id = 'comp4'
        assert os.path.exists(self._devkit_path), 'Kitti path does not exist: {}'.format(self._devkit_path)
        assert os.path.exists(self._data_path), 'Path does not exist: {}'.format(self._data_path)

    def image_path_at(self, i):
        """
        Return the absolute path to image i in the image sequence.
        """
        return self.image_path_from_index(self._image_index[i])

    def image_path_from_index(self, index):
        """
        Construct an image path from the image's "index" identifier.
        """
        image_path = os.path.join(self._data_path,index + self._image_ext)
        assert os.path.exists(image_path), 'Path does not exist: {}'.format(image_path)
        return image_path

    def _load_image_set_index(self):
        """
        Load the indexes listed in this dataset's image set file.
        """
        # there is a bug!!!!!!! i cant use it in train, but can in test
        if self._image_set  == 'test':
            image_set_file = os.path.join(
                self._devkit_path, 'ImageSets','imageset.txt')
            assert os.path.exists(image_set_file), \
                    'Path does not exist: {}'.format(image_set_file)
            with open(image_set_file) as f:
                image_index = [x.strip() for x in f.readlines()]
        elif self._image_set  == 'train':
            image_index = ['{:0>6}'.format(x) for x in range(0, 6000)] #80% data   
        
        return image_index
        
    def _get_default_path(self):
        """
        Return the default path where PASCAL VOC is expected to be installed.
        """
        return os.path.join(cfg.DATA_DIR, 'kitti')

    def gt_roidb(self):
        """
        Return the database of ground-truth regions of interest.

        This function loads/saves from/to a cache file to speed up future calls.
        """
        cache_file = os.path.join(self.cache_path, self.name + '_gt_roidb.pkl')
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as fid:
                roidb = cPickle.load(fid)
            print '{} gt roidb loaded from {}'.format(self.name, cache_file)
            return roidb

        gt_roidb = [self._load_kitti_annotation(index) for index in self.image_index]
        with open(cache_file, 'wb') as fid:
            cPickle.dump(gt_roidb, fid, cPickle.HIGHEST_PROTOCOL)
        print 'wrote gt roidb to {}'.format(cache_file)

        return gt_roidb



    def rpn_roidb(self):
        if  self._image_set != 'test':
            gt_roidb = self.gt_roidb()
            rpn_roidb = self._load_rpn_roidb(gt_roidb)
            roidb = imdb.merge_roidbs(gt_roidb, rpn_roidb)
        else:
            roidb = self._load_rpn_roidb(None)

        return roidb

    def _load_rpn_roidb(self, gt_roidb):
        filename = self.config['rpn_file']
        print 'loading {}'.format(filename)
        assert os.path.exists(filename), \
               'rpn data not found at: {}'.format(filename)
        with open(filename, 'rb') as f:
            box_list = cPickle.load(f)
        return self.create_roidb_from_box_list(box_list, gt_roidb)


    def _load_kitti_annotation(self, index):
        """
        Load image and bounding boxes info from TXT file in the kitti format.
        """
        filename = os.path.join(self._devkit_path, 'training/label_2', index + '.txt')
        f = open(filename)
        lines = f.readlines();
        num_objs = len(lines)
        boxes = np.zeros((num_objs, 4), dtype=np.uint16)
        gt_classes = np.zeros((num_objs), dtype=np.int32)
        overlaps = np.zeros((num_objs, self.num_classes), dtype=np.float32)
        seg_areas = np.zeros((num_objs), dtype=np.float32)
        ix = 0
        for line in lines:
            data = line.split()
            x1 = int(float(data[4]))
            y1 = int(float(data[5]))
            x2 = int(float(data[6]))
            y2 = int(float(data[7]))
            cls = self._class_to_ind[data[0]]
            boxes[ix, :] = [x1, y1, x2, y2]
            gt_classes[ix] = cls
            overlaps[ix, cls] = 1.0
            seg_areas[ix] = (x2 - x1 + 1) * (y2 - y1 + 1)
            ix = ix + 1

        overlaps = scipy.sparse.csr_matrix(overlaps)

        return {'boxes' : boxes,
                'gt_classes': gt_classes,
                'gt_overlaps' : overlaps,
                'flipped' : False,
                'seg_areas' : seg_areas}
                
                
    def _do_python_eval(self, output_dir = 'output'):
        annopath = os.path.join(self._devkit_path, 'training/label_2', '{:s}.txt') 

        imagesetfile = os.path.join(
            self._devkit_path, 'ImageSets','imageset.txt')
            
        cachedir = os.path.join(self._devkit_path, 'annotations_cache')
        aps = []
        # The PASCAL VOC metric changed in 2010
        use_07_metric = True #if int(self._year) < 2010 else False
        print 'VOC07 metric? ' + ('Yes' if use_07_metric else 'No')
        if not os.path.isdir(output_dir):
            os.mkdir(output_dir)
        for i, cls in enumerate(self._classes):
            if cls == '__background__':
                continue
            filename = self._get_voc_results_file_template().format(cls)
            
            # for every class, run a kitti_eval
            rec, prec, ap = kitti_eval(
                filename, annopath, imagesetfile, cls, cachedir, 
                ovthresh=0.5,
                use_07_metric=use_07_metric)
                
            aps += [ap]
            print('AP for {} = {:.4f}'.format(cls, ap))
            with open(os.path.join(output_dir, cls + '_pr.pkl'), 'w') as f:
                cPickle.dump({'rec': rec, 'prec': prec, 'ap': ap}, f)
        print('Mean AP = {:.4f}'.format(np.mean(aps)))
        print('~~~~~~~~')
        print('Results:')
        for ap in aps:
            print('{:.3f}'.format(ap))
        print('{:.3f}'.format(np.mean(aps)))
        print('~~~~~~~~')
        print('')
        print('--------------------------------------------------------------')
        print('Results computed with the **unofficial** Python eval code.')
        print('Results should be very close to the official MATLAB eval code.')
        print('Recompute with `./tools/reval.py --matlab ...` for your paper.')
        print('-- Thanks, The Management')
        print('--------------------------------------------------------------')                
                
                
    def evaluate_detections(self, all_boxes, output_dir):
        self._write_voc_results_file(all_boxes)
        self._do_python_eval(output_dir)
        
        #should use clean up funcion!!!
#        if self.config['matlab_eval']:
#            self._do_matlab_eval(output_dir)
#        if self.config['cleanup']:
#            for cls in self._classes:
#                if cls == '__background__':
#                    continue
#                filename = self._get_voc_results_file_template().format(cls)
#                os.remove(filename)   
        

    def _get_voc_results_file_template(self):
        # VOCdevkit/results/VOC2007/Main/<comp_id>_det_test_aeroplane.txt
        filename = self._comp_id + '_det_' + self._image_set + '_{:s}.txt'
        path = os.path.join(
            self._devkit_path,
            'results',
            'Main',
            filename)
        return path

    def _write_voc_results_file(self, all_boxes):
        for cls_ind, cls in enumerate(self.classes):
            if cls == '__background__':
                continue
            print 'Writing {} VOC results file'.format(cls)
            filename = self._get_voc_results_file_template().format(cls)
            with open(filename, 'wt') as f:
                for im_ind, index in enumerate(self.image_index):
                    dets = all_boxes[cls_ind][im_ind]
                    if dets == []:
                        continue
                    # the VOCdevkit expects 1-based indices
                    for k in xrange(dets.shape[0]):
                        f.write('{:s} {:.3f} {:.1f} {:.1f} {:.1f} {:.1f}\n'.
                                format(index, dets[k, -1],
                                       dets[k, 0], dets[k, 1],
                                       dets[k, 2], dets[k, 3]))

if __name__ == '__main__':
    pass
