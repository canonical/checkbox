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

# Create a triangular mask for diagonal tearing
mask = np.tri(HEIGHT, WIDTH, -320, dtype=np.uint8)  # Adjust the parameters for different angles of tearing

# Process video
while cap.isOpened():
    # Read next frame
    ret, curr_frame = cap.read()
    if not ret:
        break

    # Resize the current frame
    curr_frame = cv2.resize(curr_frame, (640, 480))

    # Apply the mask to create diagonal tearing
    torn_frame = prev_frame * mask + curr_frame * (1 - mask)

    # Display torn frame
    cv2.imshow('Diagonal Tearing Simulation', torn_frame)

    # Set the current frame as the previous frame for the next iteration
    prev_frame = curr_frame

    # Break the loop if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release everything if job is finished
cap.release()
cv2.destroyAllWindows()