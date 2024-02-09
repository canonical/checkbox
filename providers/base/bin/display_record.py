import cv2
import subprocess



def read_video(stream_url: str) -> cv2.VideoCapture:
    # Load video
    cap = cv2.VideoCapture(stream_url)

    # Check if video opened successfully
    if not cap.isOpened():
        print("Error: Could not open video.")
        exit()

    return cap  # Return the video capture object


def start_video_writer(out_path: str, cap) -> cv2.VideoWriter:
    frame_width = int(cap.get(3))
    frame_height = int(cap.get(4))
    # Set up the output video writer
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # Codec for MP4 format
    frame_rate = 30  # Adjust according to your video's frame rate
    out = cv2.VideoWriter(
        out_path, fourcc, frame_rate, (frame_width, frame_height)
    )

    return out  # Return the video capture object


def capture_video(
    process: subprocess.Popen,
    cap: cv2.VideoCapture,
    out: cv2.VideoWriter = None,
    show: bool = False,
):

    while process.poll() is None:
        # Capture frame-by-frame
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        # Write the frame into the file 'output_video.mp4'
        out.write(frame)

        # Display the resulting frame (optional)
        if show:
            cv2.imshow("Frame", frame)

        # Break the loop when 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    stdout, stderr = (
        process.communicate()
    )  # This will wait for each process to finish
    if process.returncode == 0:
        print("Success:", stdout)
    else:
        print(stdout)
        print(stderr)
        process.kill()

    cv2.destroyAllWindows()


if __name__ == "__main__":

    name = "line_tearing_vertical"
    video_path = f"/home/ubuntu/Videos/out/{name}.mp4"
    flags = "--play-and-exit --no-qt-privacy-ask --fullscreen --no-video-title-show"
    command = [
        "ssh",
        "-X",
        "ubuntu@10.102.161.49",
        f"DISPLAY=:0 vlc {video_path} {flags}",
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    import time

    time.sleep(3)

    # For window tearing
    stream_url = "http://10.102.241.49:60020/stream"
    out_path = f"/home/fernando/Videos/Screencasts/streams/stream_{name}.mp4"

    cap = read_video(stream_url)
    out = start_video_writer(out_path, cap)

    capture_video(process, cap, out, show=False)

    cap.release()
    if out:
        out.release()

