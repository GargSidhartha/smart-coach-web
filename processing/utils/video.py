import supervision as sv
import cv2

# get the total number of frames 
def get_number_of_frames(VIDEO_SRC):
    cap = cv2.VideoCapture(VIDEO_SRC)
    if not cap.isOpened():
        return -1, -1 # Return -1 for fps too on error
    else:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release() # Release the capture object
        return total_frames,fps

def get_frames(video_src,stride=1,start=0,end=None):
    # Using sv.process_video for potentially better memory management
    # Note: This returns a generator, which is good
    return sv.get_video_frames_generator(source_path=video_src, stride=stride, start=start, end=end)
    # Alternative using sv.process_video if you want callbacks per frame:
    # sv.process_video(
    #     source_path=video_src,
    #     target_path=None, # We don't write output here
    #     callback=lambda frame, index: frame_processor(frame, index) # Define frame_processor
    # ) 