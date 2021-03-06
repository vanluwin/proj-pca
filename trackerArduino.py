from utils import drawAxis, getOrientation
import numpy as np
import cv2 as cv
import argparse
import serial

# Color range of the mice un the subtracted image
lower_white = np.array([70, 70, 70])
upper_white = np.array([170, 170, 170])

def onTrackbarLower(val):
    global lower_white
    lower_white = np.array([val, val, val])

def onTrackbarUpper(val):
    global upper_white
    upper_white = np.array([val, val, val])

def parser_args():
    parser = argparse.ArgumentParser(
        description='Tracks mice.'
    )

    parser.add_argument(
        'video', type=str,
        help='Path to the file file to be processed.'
    )

    parser.add_argument(
        'bg_image', type=str,
        help='Path to the background image of the scene.'
    )

    parser.add_argument(
        '--draw-axis', action='store_true',
        help='Draw both PCA axis.'
    )

    parser.add_argument(
        '--save-video', action='store_true',
        help='Create a video file with the analysis result.'
    )

    parser.add_argument(
        '--color-mask', action='store_true',
        help='Draw a colored mask over the detection.'
    )

    parser.add_argument(
        '--log-position', action='store_true',
        help='Logs the position of the center of mass to file.'
    )

    return parser.parse_args()
    
if __name__ == '__main__':
    args = parser_args()

    ser = serial.Serial(port='/dev/ttyUSB0', baudrate=500000)

    bg_img = cv.imread(args.bg_image)

    if(bg_img.size is None):
        print('Error opening background image')
        exit()

    cap = cv.VideoCapture(args.video)

    if (not cap.isOpened()):
        print('Error opening video stream')
        exit()

    # Selection of the ROIs
    ret, frame = cap.read()

    if(not ret):
        print('Error readning video stream')
        exit()

    roi = cv.selectROI('ROI Selection', frame, False)
    cv.destroyWindow('ROI Selection')

    result_win = 'Tracker'
    cv.namedWindow(result_win, cv.WINDOW_KEEPRATIO)
    cv.resizeWindow(result_win, 640, 528)

    trackbarLower = 'Lower Color x %d' % 255
    cv.createTrackbar(trackbarLower, result_win , 70, 255, onTrackbarLower)

    trackbarUpper = 'Upper Color %d' % 255
    cv.createTrackbar(trackbarUpper, result_win , 170, 255, onTrackbarUpper)

    if(args.save_video):
        outWriter = cv.VideoWriter(
            'result.avi',
            cv.VideoWriter_fourcc('M', 'J', 'P', 'G'),
            50, (640, 480)
        )
    
    while(cap.isOpened()):
        ret, frame = cap.read()

        if(not ret):
            print('Error readning video stream')
            exit()

        sub_frame = cv.medianBlur(cv.GaussianBlur(cv.absdiff(frame, bg_img), (5, 5), 0), 5)

        filtered_frame = cv.inRange(sub_frame, lower_white, upper_white)
        
        # Kernel for morphological operation opening
        kernel1 = cv.getStructuringElement(
            cv.MORPH_ELLIPSE,
            (18, 18),
            (-1, -1)
        )

        kernel2 = cv.getStructuringElement(
            cv.MORPH_ELLIPSE,
            (30, 30),
            (-1, -1)
        )

        # Morphological opening
        mask = cv.dilate(cv.erode(filtered_frame, kernel1), kernel2)

        # Find all the contours in the mask
        returns = cv.findContours(mask, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)
        
        # Check what findContours returned
        contours = []
        if(len(returns) == 3):
            contours = returns[1]
        else:
            contours = returns[0]

        cntr = (0, 0)
        for i, c in enumerate(contours):
            # Calculate the area of each contour
            area = cv.contourArea(c)

            # Ignore contours that are too small or too large
            if area < 1e2 or 1e5 < area:
                continue

            # Draw each contour only for visualisation purposes
            cv.drawContours(frame, contours, i, (255, 0, 255), 2)

            # Find the orientation of each shape
            cntr, _ = getOrientation(c, frame, args.draw_axis)
        
        # Draw ROI and check if the mice is inside 
        if(roi is not None):
            x, y, w, h = roi
            
            if(any(cntr)):
                if(x <= cntr[0] <= x+w and y <= cntr[1] <= y+h):                        
                    cv.rectangle(
                        frame,
                        (x, y),
                        (x + w, y + h),
                        (128, 244, 66), 2
                    )

                    ser.write(b'1')

                else:
                    writeToSerial = False
                    cv.rectangle(
                        frame,
                        (x, y),
                        (x + w, y + h),
                        (80, 80, 80), 2
                    )

                    ser.write(b'0')
    
            else:
                writeToSerial = False
                cv.rectangle(
                    frame,
                    (x, y),
                    (x + w, y + h),
                    (80, 80, 80), 2
                )

                ser.write(b'0')

        # Save position to file
        if(args.log_position):
            logFileName = args.video.split('/')[-1].split('.')[0] + '_log.txt'

            with open(logFileName, 'a') as logFile:
                logFile.write(f'{cntr[0]} {cntr[1]}\n')

        if(args.color_mask):
            # Change the color of the mask
            colored_mask = cv.cvtColor(mask, cv.COLOR_GRAY2BGR)
            colored_mask[np.where((colored_mask == [255, 255, 255]).all(axis = 2))] = [0, 0, 255]

            # Apply the mask
            frame = cv.add(frame, colored_mask)

        cv.imshow(result_win, frame)

        if(args.save_video):
            outWriter.write(frame)

        key = cv.waitKey(5)
        if(key == 27 or key == 113):
            cv.destroyAllWindows()
            cap.release()

            if(args.save_video):
                outWriter.release()

            exit()
        elif(key == 32):
            while True:

                cv.imshow(result_win, frame)
                
                key2 = cv.waitKey(5)
                if(key2 == 32):
                    break
                elif(key2 == 27 or key == 113):
                    cv.destroyAllWindows()
                    cap.release()

                    if(args.save_video):
                        outWriter.release()

                    exit()