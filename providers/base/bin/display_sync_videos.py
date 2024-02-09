import cv2
import numpy as np

HEIGHT = 1080
WIDTH = 1920


def load_cap(video_path: str) -> cv2.VideoCapture:
    # Load video
    cap = cv2.VideoCapture(video_path)

    # Check if video opened successfully
    if not cap.isOpened():
        print("Error: Could not open video.")
        exit()

    return cap  # Return the video capture object


def sync_videos(name: str):
    # Open the video files
    cap1 = load_cap(
        f"/home/fernando/Videos/Screencasts/original/no_{name}.mp4"
    )
    cap2 = load_cap(
        f"/home/fernando/Videos/Screencasts/tearing/{name}.mp4"
    )
    cap3 = load_cap(
        f"/home/fernando/Videos/Screencasts/streams/stream_{name}.mp4"
    )
    cap4 = load_cap(
        f"/home/fernando/Videos/Screencasts/edges/edges_{name}.mp4"
    )

    # Setup VideoWriter object (adjust 'frame_rate' and 'fourcc' as needed)
    frame_rate = 30
    out_size = (WIDTH, HEIGHT)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_path = f"/home/fernando/Videos/Screencasts/combined/all_{name}.mp4"
    out = cv2.VideoWriter(out_path, fourcc, frame_rate, out_size)

    # Offsets for each video (number of frames to skip at the beginning)
    offsets = [20, 20, 2, 2]  # Example offsets for each video

    # Function to skip initial frames based on offset
    def skip_initial_frames(cap, offset):
        for _ in range(offset):
            cap.read()

    # Apply offsets
    skip_initial_frames(cap1, offsets[0])
    skip_initial_frames(cap2, offsets[1])
    skip_initial_frames(cap3, offsets[2])
    skip_initial_frames(cap4, offsets[3])

    # Define the color and thickness of the lines
    line_color = (128, 128, 128)  # Grey color in BGR
    line_thickness = 2  # Thickness of the line
    idx = 0
    while True:
        # Read a frame from each video
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()
        ret3, frame3 = cap3.read()
        ret4, frame4 = cap4.read()


        # Break the loop if any video ends
        if not all([ret1, ret2, ret3, ret4]):
            break

        frame1 = cv2.resize(frame1, (960, 540))
        frame2 = cv2.resize(frame2, (960, 540))
        frame3 = cv2.resize(frame3, (960, 540))
        frame4 = cv2.resize(frame4, (960, 540))

        # Combine frames into a 2x2 grid
        top_row = np.hstack((frame1, frame2))
        bottom_row = np.hstack((frame3, frame4))
        combined_frame = np.vstack((top_row, bottom_row))
        
        middle_line = 540
        cv2.line(combined_frame, (0, middle_line), (1920, middle_line), line_color, line_thickness)

        middle_column = 960
        cv2.line(combined_frame, (middle_column, 0), (middle_column, 1080), line_color, line_thickness)

        
        # Write the combined frame to the output video
        out.write(combined_frame)
        idx += 1

    # Release everything when done
    cap1.release()
    cap2.release()
    cap3.release()
    cap4.release()
    out.release()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    names = [
        "tearing_diagonal",
        "tearing_vertical",
        "tearing_horizontal",
        "line_tearing_diagonal",
        "line_tearing_vertical",
        "line_tearing_horizontal",
    ]

    for name in names:
        sync_videos(name)

        print(f"Finished processing {name}.")
