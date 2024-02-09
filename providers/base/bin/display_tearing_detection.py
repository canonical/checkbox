import cv2
import numpy as np

HEIGHT = 1080
WIDTH = 1920


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
    out = cv2.VideoWriter(out_path, fourcc, frame_rate, (WIDTH, HEIGHT), 0)

    return out  # Return the video capture object


def edge_detection(
    cap: cv2.VideoCapture,
    out: cv2.VideoWriter = None,
    show: bool = False,
):

    backSub = cv2.createBackgroundSubtractorMOG2(history=1000, varThreshold=16, detectShadows=True)

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

        edges = backSub.apply(edges)


        # Display frames
        if show:
            # Display original torn frame
            cv2.imshow("Frame", curr_frame)
            # Display detected edges
            cv2.imshow("Sobel Edges", edges)

        if out:
            out.write(edges)

        # Break the loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Release everything if job is finished

    cv2.destroyAllWindows()


if __name__ == "__main__":
    names = [
        # "line_tearing_diagonal",
        # "line_tearing_vertical",
        # "line_tearing_horizontal",
        "tearing_diagonal",
        # "tearing_vertical",
        # "tearing_horizontal",
    ]

    for name in names:
        # For window tearing
        video_path = (
            f"/home/fernando/Videos/Screencasts/streams/stream_{name}.mp4"
        )
        # video_path = f"/home/fernando/Videos/Screencasts/out/tearing_{tearing_type}.mp4"
        out_path = f"/home/fernando/Videos/Screencasts/edges/edges_{name}.mp4"

        # For line tearing
        # video_path = "/home/fernando/Videos/Screencasts/moving_vertical_lines.mp4"
        # out_path = f"/home/fernando/Videos/Screencasts/out/line_tearing_{tearing_type}.mp4"

        cap = load_video(video_path)
        out = start_video_writer(out_path)
        # out = None

        edge_detection(cap, out, show=True)

        cap.release()
        if out:
            out.release()

        print(f"Finished processing {name}.")
