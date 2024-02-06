import cv2
import numpy as np

# Load video
video_path = '../data/window_screencast.webm'
cap = cv2.VideoCapture(video_path)

# Check if video opened successfully
if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

# Read the first frame and resize it
ret, prev_frame = cap.read()
if ret:
    prev_frame = cv2.resize(prev_frame, (640, 480))

# Process video
while cap.isOpened():
    # Read next frame
    ret, curr_frame = cap.read()
    if not ret:
        break

    # Resize the current frame
    curr_frame = cv2.resize(curr_frame, (640, 480))

    # Combine the top half of the previous frame and the bottom half of the current frame
    tear_line = 240  # Half of 480 (vertical center)
    top_half = prev_frame[:tear_line, :]
    bottom_half = curr_frame[tear_line:, :]
    torn_frame = np.vstack((top_half, bottom_half))

    # Display torn frame
    cv2.imshow('Tearing Simulation', torn_frame)

    # Set the current frame as the previous frame for the next iteration
    prev_frame = curr_frame
    import time
    time.sleep(0.1)

    # Break the loop if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release everything if job is finished
cap.release()
cv2.destroyAllWindows()