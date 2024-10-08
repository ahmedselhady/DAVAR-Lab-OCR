#!/usr/bin/env python
# -*- coding: utf-8 -*-
from collections import namedtuple
import rrc_evaluation_funcs
import importlib
import sys
import json

import math 

def evaluation_imports():
    """
    evaluation_imports: Dictionary ( key = module name , value = alias  )  with python modules used in the evaluation. 
    """    
    return {
            'Polygon':'plg',
            'numpy':'np'
            }

def default_evaluation_params():
    """
    default_evaluation_params: Default parameters to use for the validation and evaluation.
    """
    p = dict([s[1:].split('=') for s in sys.argv[1:]])

    iou = float(p.get('iou', 0.5))
    word_spotting = p.get('word_spotting', "FALSE")
    if word_spotting.upper() == "FALSE":
        word_spotting = False
    else:
        word_spotting = True

    if p['g'].split("/")[-1] in ['gt-icdar2013.zip']:
        gt_format = 'gt_img_([0-9]+).txt'
        det_format = 'img_([0-9]+).txt'
    elif  p['g'].split("/")[-1] in ['gt-icdar2015.zip']:
        gt_format = 'gt_img_([0-9]+).txt'
        det_format = 'img_([0-9]+).txt'
    elif  p['g'].split("/")[-1] in ['total-text-gt.zip']:
        gt_format = 'poly_gt_img([0-9]+).txt'
        det_format = 'img([0-9]+).txt'
    else:
        gt_format = '([0-9]+).txt'
        det_format = '([0-9]+).txt'

    return {
        'IOU_CONSTRAINT': iou,
        'AREA_PRECISION_CONSTRAINT': iou,
        'WORD_SPOTTING': word_spotting,
        'MIN_LENGTH_CARE_WORD': 3,
        'GT_SAMPLE_NAME_2_ID': gt_format,
        'DET_SAMPLE_NAME_2_ID': det_format,
        'LTRB': False,  # LTRB:2points(left,top,right,bottom) or 4 points(x1,y1,x2,y2,x3,y3,x4,y4)
        'CRLF': False,  # Lines are delimited by Windows CRLF format
        'CONFIDENCES': False,  # Detections must include confidence value. MAP and MAR will be calculated,
        'SPECIAL_CHARACTERS': '!?.:,*"()·[]/\' ',
        'ONLY_REMOVE_FIRST_LAST_CHARACTER': True
    }


def validate_data(gtFilePath, submFilePath, evaluationParams):
    """
    Method validate_data: validates that all files in the results folder are correct (have the correct name contents).
                            Validates also that there are no missing files in the folder.
                            If some error detected, the method raises the error
    """
    gt = rrc_evaluation_funcs.load_zip_file(gtFilePath, evaluationParams['GT_SAMPLE_NAME_2_ID'])

    subm = rrc_evaluation_funcs.load_zip_file(submFilePath, evaluationParams['DET_SAMPLE_NAME_2_ID'], True)
    # Validate format of GroundTruth
    for k in gt:
        rrc_evaluation_funcs.validate_lines_in_file(k, gt[k], evaluationParams['CRLF'], evaluationParams['LTRB'], True)
    # Validate format of results
    for k in subm:
        if (k in gt) == False:
            raise Exception("The sample %s not present in GT" % k)

        rrc_evaluation_funcs.validate_lines_in_file(k, subm[k], evaluationParams['CRLF'], evaluationParams['LTRB'],
                                                    True, evaluationParams['CONFIDENCES'])


def evaluate_method(gtFilePath, submFilePath, evaluationParams):
    """
    Method evaluate_method: evaluate method and returns the results
        Results. Dictionary with the following values:
        - method (required)  Global method metrics. Ex: { 'Precision':0.8,'Recall':0.9 }
        - samples (optional) Per sample metrics. Ex: {'sample1' : { 'Precision':0.8,'Recall':0.9 } , 'sample2' : { 'Precision':0.8,'Recall':0.9 }
    """
    for module, alias in evaluation_imports().items():
        globals()[alias] = importlib.import_module(module)

    def polygon_from_points(points, correctOffset=False):
        """
        Returns a Polygon object to use with the Polygon2 class from a list of 8 points: x1,y1,x2,y2,x3,y3,x4,y4
        """

        if correctOffset:  # this will substract 1 from the coordinates that correspond to the xmax and ymax
            points[2] -= 1
            points[4] -= 1
            points[5] -= 1
            points[7] -= 1

        resBoxes = np.empty([1, 8], dtype='int32')
        resBoxes[0, 0] = int(points[0])
        resBoxes[0, 4] = int(points[1])
        resBoxes[0, 1] = int(points[2])
        resBoxes[0, 5] = int(points[3])
        resBoxes[0, 2] = int(points[4])
        resBoxes[0, 6] = int(points[5])
        resBoxes[0, 3] = int(points[6])
        resBoxes[0, 7] = int(points[7])
        pointMat = resBoxes[0].reshape([2, 4]).T
        return plg.Polygon(pointMat)

    def polygon_from_points_any_shape(points):
        """
        Returns a Polygon object to use with the Polygon2 class from a list of arbitrary number of points: x1,y1,x2,y2,...,x14,y14
        """
        n = len(points)

        resBoxes = np.empty([1, n], dtype='int32')
        for i in range(int(n / 2)):
            resBoxes[0, i] = int(points[2 * i])
            resBoxes[0, i + int(n / 2)] = int(points[2 * i + 1])
        temp = resBoxes[0][0:int(n/2*2)]
        pointMat = temp.reshape([2, int(n / 2)]).T
        return plg.Polygon(pointMat)

    def rectangle_to_polygon(rect):
        resBoxes = np.empty([1, 8], dtype='int32')
        resBoxes[0, 0] = int(rect.xmin)
        resBoxes[0, 4] = int(rect.ymax)
        resBoxes[0, 1] = int(rect.xmin)
        resBoxes[0, 5] = int(rect.ymin)
        resBoxes[0, 2] = int(rect.xmax)
        resBoxes[0, 6] = int(rect.ymin)
        resBoxes[0, 3] = int(rect.xmax)
        resBoxes[0, 7] = int(rect.ymax)

        pointMat = resBoxes[0].reshape([2, 4]).T

        return plg.Polygon(pointMat)

    def rectangle_to_points(rect):
        points = [int(rect.xmin), int(rect.ymax), int(rect.xmax), int(rect.ymax), int(rect.xmax), int(rect.ymin),
                  int(rect.xmin), int(rect.ymin)]
        return points

    def get_union(pD, pG):
        areaA = pD.area()
        areaB = pG.area()
        return areaA + areaB - get_intersection(pD, pG)

    def get_intersection_over_union(pD, pG):
        try:
            return get_intersection(pD, pG) / get_union(pD, pG)
        except:
            return 0

    def get_intersection(pD, pG):
        pInt = pD & pG
        if len(pInt) == 0:
            return 0
        return pInt.area()

    def compute_ap(confList, matchList, numGtCare):
        correct = 0
        AP = 0
        if len(confList) > 0:
            confList = np.array(confList)
            matchList = np.array(matchList)
            sorted_ind = np.argsort(-confList)
            confList = confList[sorted_ind]
            matchList = matchList[sorted_ind]
            for n in range(len(confList)):
                match = matchList[n]
                if match:
                    correct += 1
                    AP += float(correct) / (n + 1)

            if numGtCare > 0:
                AP /= numGtCare

        return AP

    def transcription_match(transGt, transDet, specialCharacters='!?.:,*"()·[]/\'',
                            onlyRemoveFirstLastCharacterGT=True):

        if onlyRemoveFirstLastCharacterGT:
            # special characters in GT are allowed only at initial or final position
            if (transGt == transDet):
                return True

            if len(transGt) >0 and specialCharacters.find(transGt[0]) > -1:
                if transGt[1:] == transDet:
                    return True

            if len(transGt) >0 and specialCharacters.find(transGt[-1]) > -1:
                if transGt[0:len(transGt) - 1] == transDet:
                    return True

            if len(transGt) >0 and specialCharacters.find(transGt[0]) > -1 and specialCharacters.find(transGt[-1]) > -1:
                if transGt[1:len(transGt) - 1] == transDet:
                    return True
            return False
        else:
            # Special characters are removed from the begining and the end of both Detection and GroundTruth
            while len(transGt) > 0 and specialCharacters.find(transGt[0]) > -1:
                transGt = transGt[1:]

            while len(transDet) > 0 and specialCharacters.find(transDet[0]) > -1:
                transDet = transDet[1:]

            while len(transGt) > 0 and specialCharacters.find(transGt[-1]) > -1:
                transGt = transGt[0:len(transGt) - 1]

            while len(transDet) > 0 and specialCharacters.find(transDet[-1]) > -1:
                transDet = transDet[0:len(transDet) - 1]

            return transGt == transDet

    def include_in_dictionary(transcription):
        """
        Function used in Word Spotting that finds if the Ground Truth transcription meets the rules to enter into the dictionary. If not, the transcription will be cared as don't care
        """
        # special case 's at final
        if transcription[len(transcription) - 2:] == "'s" or transcription[len(transcription) - 2:] == "'S":
            transcription = transcription[0:len(transcription) - 2]

        # hypens at init or final of the word
        transcription = transcription.strip('-')

        specialCharacters = evaluationParams['SPECIAL_CHARACTERS']
        for character in specialCharacters:
            transcription = transcription.replace(character, ' ')
        transcription = transcription.strip()

        if len(transcription) != len(transcription.replace(" ", "")):
            return False

        if len(transcription) < evaluationParams['MIN_LENGTH_CARE_WORD']:
            return False

        notAllowed = "×÷·"

        range1 = [ord(u'a'), ord(u'z')]
        range2 = [ord(u'A'), ord(u'Z')]
        range3 = [ord(u'À'), ord(u'ƿ')]
        range4 = [ord(u'Ǆ'), ord(u'ɿ')]
        range5 = [ord(u'Ά'), ord(u'Ͽ')]
        range6 = [ord(u'-'), ord(u'-')]

        for char in transcription:
            charCode = ord(char)
            if (notAllowed.find(char) != -1):
                return False

            valid = (charCode >= range1[0] and charCode <= range1[1]) or (
            charCode >= range2[0] and charCode <= range2[1]) or (charCode >= range3[0] and charCode <= range3[1]) or (
                    charCode >= range4[0] and charCode <= range4[1]) or (
                    charCode >= range5[0] and charCode <= range5[1]) or (
                    charCode >= range6[0] and charCode <= range6[1])
            if valid == False:
                return False

        return True

    def include_in_dictionary_transcription(transcription):
        """
        Function applied to the Ground Truth transcriptions used in Word Spotting. It removes special characters or terminations
        """
        # special case 's at final
        if transcription[len(transcription) - 2:] == "'s" or transcription[len(transcription) - 2:] == "'S":
            transcription = transcription[0:len(transcription) - 2]

        # hypens at init or final of the word
        transcription = transcription.strip('-')

        specialCharacters = evaluationParams['SPECIAL_CHARACTERS']
        for character in specialCharacters:
            transcription = transcription.replace(character, ' ')

        transcription = transcription.strip()

        return transcription

    perSampleMetrics = {}

    matchedSum_det = 0
    matchedSum_tiouGt = 0
    matchedSum_tiouDt = 0
    matchedSum_spot = 0

    Rectangle = namedtuple('Rectangle', 'xmin ymin xmax ymax')

    gt = rrc_evaluation_funcs.load_zip_file(gtFilePath, evaluationParams['GT_SAMPLE_NAME_2_ID'])
    subm = rrc_evaluation_funcs.load_zip_file(submFilePath, evaluationParams['DET_SAMPLE_NAME_2_ID'], True)

    numGlobalCareGt = 0
    numGlobalCareDet = 0
    totalNumDetPols = 0

    arrGlobalConfidences = [];
    arrGlobalMatches = [];

    for resFile in gt:

        gtFile = rrc_evaluation_funcs.decode_utf8(gt[resFile])
        if (gtFile is None):
            raise Exception("The file %s is not UTF-8" % resFile)

        recall = 0
        precision = 0
        hmean = 0
        
        detMatched = 0
        detMatched_tiouGt = 0
        detMatched_tiouDt = 0
        detCorrect = 0

        iouMat = np.empty([1, 1])
        gtPols = []
        detPols = []
        gtTrans = []
        detTrans = []
        gtPolPoints = []
        detPolPoints = []
        gtDontCarePolsNum = []  # Array of Ground Truth Polygons' keys marked as don't Care
        detDontCarePolsNum = []  # Array of Detected Polygons' matched with a don't Care GT
        detMatchedNums = []
        pairs = []

        arrSampleConfidences = [];
        arrSampleMatch = [];
        sampleAP = 0;

        evaluationLog = ""

        pointsList, transcriptionsList = rrc_evaluation_funcs.get_values(gtFile, evaluationParams['CRLF'], True)
        for n in range(len(pointsList)):
            points = pointsList[n]
            transcription = transcriptionsList[n]
            dontCare = transcription == "###"
            if evaluationParams['LTRB']:
                gtRect = Rectangle(*points)
                gtPol = rectangle_to_polygon(gtRect)
            else:
                gtPol = polygon_from_points_any_shape(points)
            gtPols.append(gtPol)
            gtPolPoints.append(points)

            # On word spotting we will filter some transcriptions with special characters
            if evaluationParams['WORD_SPOTTING']:
                if dontCare == False:
                    if include_in_dictionary(transcription) == False:
                        dontCare = True
                    else:
                        transcription = include_in_dictionary_transcription(transcription)

            gtTrans.append(transcription)
            if dontCare:
                gtDontCarePolsNum.append(len(gtPols) - 1)

        evaluationLog += "GT polygons: " + str(len(gtPols)) + (
        " (" + str(len(gtDontCarePolsNum)) + " don't care)\n" if len(gtDontCarePolsNum) > 0 else "\n")

        if resFile in subm:
            detFile = rrc_evaluation_funcs.decode_utf8(subm[resFile])
            pointsList, transcriptionsList = rrc_evaluation_funcs.get_values(detFile, evaluationParams['CRLF'], True)

            for n in range(len(pointsList)):
                points = pointsList[n]
                transcription = transcriptionsList[n]

                if evaluationParams['LTRB']:
                    detRect = Rectangle(*points)
                    detPol = rectangle_to_polygon(detRect)
                else:
                    detPol = polygon_from_points_any_shape(points)
                detPols.append(detPol)
                detPolPoints.append(points)
                detTrans.append(transcription)

                if len(gtDontCarePolsNum) > 0:
                    for dontCarePol in gtDontCarePolsNum:
                        dontCarePol = gtPols[dontCarePol]
                        intersected_area = get_intersection(dontCarePol, detPol)
                        pdDimensions = detPol.area()
                        precision = 0 if pdDimensions == 0 else intersected_area / pdDimensions
                        if (precision > evaluationParams['AREA_PRECISION_CONSTRAINT']):
                            detDontCarePolsNum.append(len(detPols) - 1)
                            break

            evaluationLog += "DET polygons: " + str(len(detPols)) + (
            " (" + str(len(detDontCarePolsNum)) + " don't care)\n" if len(detDontCarePolsNum) > 0 else "\n")

            if len(gtPols) > 0 and len(detPols) > 0:
                # Calculate IoU and precision matrixs
                outputShape = [len(gtPols), len(detPols)]
                iouMat = np.empty(outputShape)
                gtRectMat = np.zeros(len(gtPols), np.int8)
                detRectMat = np.zeros(len(detPols), np.int8)
                for gtNum in range(len(gtPols)):
                    for detNum in range(len(detPols)):
                        pG = gtPols[gtNum]
                        pD = detPols[detNum]
                        iouMat[gtNum, detNum] = get_intersection_over_union(pD, pG)

                for gtNum in range(len(gtPols)):
                    for detNum in range(len(detPols)):
                        if gtRectMat[gtNum] == 0 and detRectMat[
                            detNum] == 0 and gtNum not in gtDontCarePolsNum and detNum not in detDontCarePolsNum:
                            if iouMat[gtNum, detNum] > evaluationParams['IOU_CONSTRAINT']:
                                gtRectMat[gtNum] = 1
                                detRectMat[detNum] = 1
                                detMatched += 1
                                # detection matched only if transcription is equal
                                if evaluationParams['WORD_SPOTTING']:
                                    correct = gtTrans[gtNum].upper() == detTrans[detNum].upper()
                                else:
                                    correct = transcription_match(gtTrans[gtNum].upper(), detTrans[detNum].upper(),
                                                                  evaluationParams['SPECIAL_CHARACTERS'],
                                                                  evaluationParams[
                                                                      'ONLY_REMOVE_FIRST_LAST_CHARACTER']) == True
                                detCorrect += (1 if correct else 0)
                                if correct:
                                    detMatchedNums.append(detNum)
                                pairs.append({'gt': gtNum, 'det': detNum, 'correct': correct})
                                evaluationLog += "Match GT #" + str(gtNum) + " with Det #" + str(
                                    detNum) + " trans. correct: " + str(correct) + "\n"

            if evaluationParams['CONFIDENCES']:
                ## confidencesList extraction to be implemented!!!
                confidencesList = []
                for detNum in range(len(detPols)):
                    if detNum not in detDontCarePolsNum:
                        # we exclude the don't care detections
                        match = detNum in detMatchedNums

                        arrSampleConfidences.append(confidencesList[detNum])
                        arrSampleMatch.append(match)

                        arrGlobalConfidences.append(confidencesList[detNum])
                        arrGlobalMatches.append(match)

        numGtCare = (len(gtPols) - len(gtDontCarePolsNum))
        numDetCare = (len(detPols) - len(detDontCarePolsNum))
        if numGtCare == 0:
            recall = float(1)
            precision = float(0) if numDetCare > 0 else float(1)
            sampleAP = precision
        else:
            recall = float(detCorrect) / numGtCare
            precision = 0 if numDetCare == 0 else float(detCorrect) / numDetCare
            if evaluationParams['CONFIDENCES']:
                sampleAP = compute_ap(arrSampleConfidences, arrSampleMatch, numGtCare)

        hmean = 0 if (precision + recall) == 0 else 2.0 * precision * recall / (precision + recall)

        matchedSum_det += detMatched
        matchedSum_spot += detCorrect

        numGlobalCareGt += numGtCare
        numGlobalCareDet += numDetCare
        totalNumDetPols += len(detPols)

        perSampleMetrics[resFile] = {
            'precision': precision,
            'recall': recall,
            'hmean': hmean,
            'pairs': pairs,
            'AP': sampleAP,
            'iouMat': [] if len(detPols) > 100 else iouMat.tolist(),
            'gtPolPoints': gtPolPoints,
            'detPolPoints': detPolPoints,
            'gtTrans': gtTrans,
            'detTrans': detTrans,
            'gtDontCare': gtDontCarePolsNum,
            'detDontCare': detDontCarePolsNum,
            'evaluationParams': evaluationParams,
            'evaluationLog': evaluationLog
        }

    # Compute AP
    AP = 0
    if evaluationParams['CONFIDENCES']:
        AP = compute_ap(arrGlobalConfidences, arrGlobalMatches, numGlobalCareGt)

    det_recall = 0 if numGlobalCareGt == 0 else float(matchedSum_det) / numGlobalCareGt
    det_precision = 0 if numGlobalCareDet == 0 else float(matchedSum_det) / numGlobalCareDet
    det_hmean = 0 if det_recall + det_precision == 0 else 2 * det_recall * det_precision / (
    det_recall + det_precision)

    spot_recall = 0 if numGlobalCareGt == 0 else float(matchedSum_spot) / numGlobalCareGt
    spot_precision = 0 if numGlobalCareDet == 0 else float(matchedSum_spot) / numGlobalCareDet
    spot_hmean = 0 if spot_recall + spot_precision == 0 else 2 * spot_recall * spot_precision / (
    spot_recall + spot_precision)

    methodMetrics = {'precision': spot_precision, 'recall': spot_recall, 'hmean': spot_hmean, 'AP': AP}

    print('num_gt, num_det: ', numGlobalCareGt, totalNumDetPols)
    print("Origin:")
    print("det_recall: ", round(det_recall, 4), "det_precision: ", round(det_precision, 4), "det_hmean: ",
          round(det_hmean, 4))
    print("spot_recall: ", round(spot_recall, 4), "spot_precision: ", round(spot_precision, 4), "spot_hmean: ",
          round(spot_hmean, 4))

    resDict = {'calculated': True, 'Message': '', 'method': methodMetrics, 'per_sample': perSampleMetrics}

    return resDict


if __name__ == '__main__':
    rrc_evaluation_funcs.main_evaluation(None, default_evaluation_params, validate_data, evaluate_method)
