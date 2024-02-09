import cv2
import numpy as np

HEIGHT = 1080
WIDTH = 1920


# Tear line for horizontal tearing
HORIZONTAL_TEAR_LINE = int(HEIGHT * 0.5)

# Tear line for vertical tearing
VERTICAL_TEAR_LINE = int(WIDTH * 0.65)

# Create a triangular mask for diagonal tearing
diag_mask = np.tri(HEIGHT, WIDTH, int(WIDTH * 0.15), dtype=np.uint8)
diag_mask = np.expand_dims(diag_mask, axis=-1) * np.ones(3, dtype=np.uint8)


def load_video(video_path: str) -> cv2.VideoCapture:
    # Load video
    cap = cv2.VideoCapture(video_path)

    # Check if video opened successfully
    if not cap.isOpened():
        print("Error: Could not open video.")
        exit()

    return cap  # Return the video capture object


def start_video_writer(out_path: str) -> cv2.VideoWriter:
    # Set up the output video writer
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # Codec for MP4 format
    frame_rate = 30  # Adjust according to your video's frame rate
    out = cv2.VideoWriter(out_path, fourcc, frame_rate, (WIDTH, HEIGHT))

    return out  # Return the video capture object

def edge_detection(
    cap: cv2.VideoCapture,
    out: cv2.VideoWriter = None,
    show: bool = False,
):

    # Create a triangular mask for diagonal tearing
    # Adjust the parameters for different angles of tearing

    # Process video
    while cap.isOpened():
        # Read next frame
        ret, curr_frame = cap.read()
        if not ret:
            break

        # Resize the current frame
        curr_frame = cv2.resize(curr_frame, (WIDTH, HEIGHT))

        # Convert to grayscale for edge detection
        gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

        # # Apply Canny edge detection
        # edges = cv2.Canny(gray, 100, 200)  # These thresholds can be tuned
        # Apply Sobel edge detection
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sobel_edges = cv2.magnitude(sobelx, sobely)
        edges = np.uint8(sobel_edges)




        # Display frames
        if show:
            # Display original torn frame
            cv2.imshow('Frame', curr_frame)
            # Display detected edges
            cv2.imshow('Canny Edges', edges)


        if out:
            out.write(edges)


        # Break the loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Release everything if job is finished

    cv2.destroyAllWindows()


if __name__ == "__main__":
    tearing_type = "diagonal"
    # tearing_type = "vertical"
    # tearing_type = "horizontal"

    # For window tearing
    video_path = f"/home/fernando/Videos/Screencasts/out/line_tearing_{tearing_type}.mp4"
    # video_path = f"/home/fernando/Videos/Screencasts/out/tearing_{tearing_type}.mp4"
    out_path = f"/home/fernando/Videos/Screencasts/out/edges_tearing_{tearing_type}.mp4"

    # For line tearing
    # video_path = "/home/fernando/Videos/Screencasts/moving_vertical_lines.mp4"
    # out_path = f"/home/fernando/Videos/Screencasts/out/line_tearing_{tearing_type}.mp4"

    cap = load_video(video_path)
    # out = start_video_writer(out_path)
    out = None

    edge_detection(cap, out, show=True)

    cap.release()
    if out:
        out.release()
