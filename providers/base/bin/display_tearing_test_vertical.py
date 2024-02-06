import cv2
import numpy as np

# Load video
video_path = '../data/window_screencast.webm'
cap = cv2.VideoCapture(video_path)

# Check if video opened successfully
if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

HEIGHT = 360*2
WIDTH = 640*2

# Read the first frame and resize it
ret, prev_frame = cap.read()
if ret:
    prev_frame = cv2.resize(prev_frame, (WIDTH, HEIGHT))

# Process video
while cap.isOpened():
    # Read next frame
    ret, curr_frame = cap.read()
    if not ret:
        break

    # Resize the current frame
    curr_frame = cv2.resize(curr_frame, (WIDTH, HEIGHT))

    # Combine the left half of the previous frame and the right half of the current frame
    tear_column = 320  # Half of WIDTH (horizontal center)
    left_half = prev_frame[:, :tear_column]
    right_half = curr_frame[:, tear_column:]
    torn_frame = np.hstack((left_half, right_half))

    # Display torn frame
    cv2.imshow('Vertical Tearing Simulation', torn_frame)

    # Set the current frame as the previous frame for the next iteration
    prev_frame = curr_frame
    import time
    time.sleep(0.05)

    # Break the loop if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release everything if job is finished
cap.release()
cv2.destroyAllWindows()