# Steps
# Get the homography matching the desktop with the camera capture
# Launch the calculator app
# Capture the screen with the calculator

# Get the points of the calculator buttons
# Move the mouse to the calculator buttons
# Click the calculator buttons

# Capture the screen with the result
# Get the points of the result


import cv2
import numpy as np
import matplotlib.pyplot as plt
import sys
import subprocess
from checkbox_support.scripts.zapper_proxy import zapper_run  # noqa: E402
from lightglue import LightGlue, SuperPoint, DISK
from lightglue.utils import load_image, rbd, numpy_image_to_torch
from lightglue import viz2d
import torch
import time

laptop_list = [
    ["202112-29762", "10.102.161.49", "202312-33778", "10.102.241.49"],
    ["202212-30926", "10.102.153.67", "202312-33777", "10.102.233.67"],
    ["202212-30951", "10.102.153.31", "202312-33775", "10.102.233.31"],
    ["202304-31460", "10.102.153.97", "202312-33772", "10.102.233.97"],
    ["202210-30711", "10.102.152.245", "202312-33770", "10.102.232.245"],
    ["202212-30908", "10.102.152.225", "202312-33769", "10.102.232.225"],
    ["202301-31119", "10.102.154.125", "202312-33765", "10.102.234.125"],
]


screen_size = (1920, 1080)

torch.set_grad_enabled(False)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
extractor = (
    SuperPoint(max_num_keypoints=2048).eval().to(device)
)  # load the extractor
matcher = LightGlue(features="superpoint").eval().to(device)


def get_homography_matrix(ref, capture, name, show_result=False):

    img_tensor_0 = numpy_image_to_torch(ref)
    img_tensor_1 = numpy_image_to_torch(capture)

    feats0 = extractor.extract(img_tensor_0.to(device))
    feats1 = extractor.extract(img_tensor_1.to(device))

    matches01 = matcher({"image0": feats0, "image1": feats1})
    feats0, feats1, matches01 = [
        rbd(x) for x in [feats0, feats1, matches01]
    ]  # remove batch dimension

    kpts0, kpts1, matches = (
        feats0["keypoints"],
        feats1["keypoints"],
        matches01["matches"],
    )
    m_kpts0, m_kpts1 = kpts0[matches[..., 0]], kpts1[matches[..., 1]]

    # Convert torch tensor to OpenCV format
    kpts0 = m_kpts0.cpu().numpy().astype(int)
    kpts1 = m_kpts1.cpu().numpy().astype(int)

    H, mask = cv2.findHomography(kpts1, kpts0, cv2.USAC_MAGSAC, 5.0)

    # Use the homography matrix to warp the result image
    result = cv2.warpPerspective(capture, H, ref.shape[1::-1])
    # Display the result
    fig, ax = plt.subplots(1, 3, figsize=(20, 5))
    ax[0].imshow(ref)
    ax[0].set_title("Image 0")
    ax[1].imshow(result)
    ax[1].set_title("Image 0 warped")
    ax[2].imshow(capture)
    ax[2].set_title("Image 1")

    plt.tight_layout()
    plt.savefig(f"images/{name}.jpg")
    if show_result:
        plt.show()

    return H


def compare_two_images(
    reference,
    template,
    name="",
    show_result=False,
    threshold=0.8,
    method=cv2.TM_CCORR_NORMED,
):
    # Load the reference image and the template
    img = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    w, h = template.shape[::-1]

    # All the 6 methods for comparison in a list
    threshold = 0.8

    # Create a figure with subplots
    fig, axs = plt.subplots(1, 2, figsize=(10, 1 * 4))

    img2 = img.copy()

    res = cv2.matchTemplate(img2, template, method=method)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    # If the method is TM_SQDIFF or TM_SQDIFF_NORMED, take minimum
    if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
        top_left = min_loc
        match_val = 1 - min_val
    else:
        top_left = max_loc
        match_val = max_val

    # Check if the match value meets the threshold
    if match_val >= threshold:
        bottom_right = (top_left[0] + w, top_left[1] + h)
        cv2.rectangle(img2, top_left, bottom_right, 0, 20)
        match_text = f"Match (val: {match_val:.2f})"
    else:
        match_text = f"No Match (val: {match_val:.2f})"

    # Plot matching result
    axs[0].imshow(template, cmap="gray")
    axs[0].set_title("Template")
    axs[0].set_xticks([]), axs[0].set_yticks([])

    # Plot detected point (only top left corner of the image)
    top_left_corner = img2.copy()[: screen_size[1], : screen_size[0]]
    axs[1].imshow(top_left_corner, cmap="gray")
    axs[1].set_title(f"Detected Point ({match_text})")
    axs[1].set_xticks([]), axs[1].set_yticks([])

    # Adjust layout and display the plot
    plt.tight_layout()
    # Save the plot
    plt.savefig(f"images/{name}.jpg")

    if show_result:
        plt.show()

    # print the center of the rectangle
    center = (top_left[0] + w // 2, top_left[1] + h // 2)
    print(f"Center of the rectangle: ({center[0]}, {center[1]})")
    return center


def click_position(zapper_ip, position, screen_size):
    """
    Request Zapper to type on keyboard and assert the received events
    are like expected.
    """

    ROBOT_INIT = """
*** Settings ***
Library    libraries/ZapperHid.py

*** Test Cases ***
Do nothing
    Log    Re-configure HID device
    """

    if screen_size == (3456, 2160):
        # if i set the mouse
        x = position[0] / 4
        y = position[1] / 4

    else:
        x = position[0] / 2
        y = position[1] / 2

    # round the values
    x = int(round(x))
    y = int(round(y))
    print(x)
    print(y)

    ROBOT_MOUSE = f"""
*** Settings ***
Library    libraries/ZapperHid.py

*** Test Cases ***
Click in the middle of the screen
    [Documentation]     Click a button
    Move Mouse To Absolute  {x}    {y}
    Click Pointer Button    LEFT
    """

    print("Running the mouse test")
    zapper_run(zapper_ip, "robot_run", ROBOT_INIT.encode(), {}, {})
    zapper_run(zapper_ip, "robot_run", ROBOT_MOUSE.encode(), {}, {})


def start_calculator(device_ip):
    p = subprocess.Popen(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"ubuntu@{device_ip}",
            "DISPLAY=:0",
            "gnome-calculator",
        ]
    )
    time.sleep(10)
    return p


def stop_calcualtor(device_ip):
    subprocess.run(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"ubuntu@{device_ip}",
            "pkill",
            "-f",
            "gnome-calculator",
        ],
        check=True,
    )


def get_screen_size(device_ip):
    output = subprocess.check_output(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"ubuntu@{device_ip}",
            "DISPLAY=:0",
            "xrandr",
        ],
        text=True,
    )
    for line in output.split("\n"):
        if "*" in line:
            screen_size = line.split()[0]
            screen_size = screen_size.split("x")
            screen_size = (int(screen_size[0]), int(screen_size[1]))
            return screen_size


def get_screenshot(device_ip):

    subprocess.run(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"ubuntu@{device_ip}",
            "sudo apt install -y gnome-screenshot",
        ],
        check=True,
    )

    subprocess.run(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"ubuntu@{device_ip}",
            "DISPLAY=:0",
            "gnome-screenshot -f /tmp/screenshot.png",
        ],
        check=True,
    )

    # Copy the screenshot to the local machine
    subprocess.run(
        [
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"ubuntu@{device_ip}:/tmp/screenshot.png",
            "/tmp/screenshot.png",
        ],
        check=True,
    )

    img = cv2.imread("/tmp/screenshot.png")
    return img


def capture_image(zapper_ip):
    subprocess.run(
        [
            "curl",
            "-m",
            "10",
            "-o",
            "/tmp/capture.jpg",
            f"{zapper_ip}:60020/snapshot",
        ],
        check=True,
    )
    img = cv2.imread("/tmp/capture.jpg")
    return img


def start_zapper_camera(zapper_ip):
    subprocess.run(
        [
            "sshpass",
            "-p",
            "insecure",
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"ubuntu@{zapper_ip}",
            "zapper",
            "ustreamer",
            "start",
            "camera",
            "--resolution",
            "1920x1080",
            "--quality",
            "100",
        ],
        check=True,
    )


def stop_zapper_camera(zapper_ip):
    subprocess.run(
        [
            "sshpass",
            "-p",
            "insecure",
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"ubuntu@{zapper_ip}",
            "zapper",
            "ustreamer",
            "stop",
            "camera",
        ],
        check=True,
    )


if __name__ == "__main__":

    for laptop in laptop_list:
        try:
            device_id = laptop[0]
            device_ip = laptop[1]
            zapper_id = laptop[2]
            zapper_ip = laptop[3]
            # Create a dir for the device
            subprocess.run(["mkdir", "-p", f"images/{device_id}"], check=True)

            # Get the screen size
            screen_size = get_screen_size(device_ip)
            print("screen_size: ", screen_size)

            # Put the cursor in the middle
            middle = (screen_size[0] // 2, screen_size[1] // 2)
            click_position(zapper_ip, middle, screen_size)

            # Get the screenshot
            start_zapper_camera(zapper_ip)
            screenshot = get_screenshot(device_ip)
            cv2.imwrite(f"images/{device_id}/screenshot.png", screenshot)

            # Get the capture
            capture = capture_image(zapper_ip)
            cv2.imwrite(
                f"images/{device_id}/snapshot_desktop_raw.jpg", capture
            )

            # Get the homography matrix
            H = get_homography_matrix(
                screenshot, capture, f"{device_id}/homography"
            )

            # Start the calculator
            p = start_calculator(device_ip)

            calc_top_raw = capture_image(zapper_ip)
            cv2.imwrite(
                f"images/{device_id}/snapshot_calc_top_raw.jpg", calc_top_raw
            )

            calc_top = cv2.warpPerspective(calc_top_raw, H, screen_size)
            cv2.imwrite(
                f"images/{device_id}/snapshot_calc_wrapped.jpg", calc_top
            )

            number_2 = cv2.imread("images/number_2.jpg")
            plus = cv2.imread("images/plus.jpg")
            equal = cv2.imread("images/equal.jpg")
            sum_result = cv2.imread("images/sum_result.jpg")

            if screen_size != (3456, 2160):
                number_2 = cv2.resize(number_2, None, fx=0.5, fy=0.5)
                plus = cv2.resize(plus, None, fx=0.5, fy=0.5)
                equal = cv2.resize(equal, None, fx=0.5, fy=0.5)
                sum_result = cv2.resize(sum_result, None, fx=0.5, fy=0.5)

            number_2_pos = compare_two_images(
                calc_top, number_2, f"{device_id}/number_2"
            )
            plus_pos = compare_two_images(calc_top, plus, f"{device_id}/plus")
            equal_pos = compare_two_images(
                calc_top, equal, f"{device_id}/equal"
            )

            click_position(zapper_ip, number_2_pos, screen_size)
            click_position(zapper_ip, plus_pos, screen_size)
            click_position(zapper_ip, number_2_pos, screen_size)
            click_position(zapper_ip, equal_pos, screen_size)

            result_raw = capture_image(zapper_ip)
            cv2.imwrite(
                f"images/{device_id}/snapshot_result_raw.jpg", result_raw
            )

            result = cv2.warpPerspective(result_raw, H, screen_size)
            cv2.imwrite(
                f"images/{device_id}/snapshot_result_wrapped.jpg", result
            )

            result_pos = compare_two_images(
                result, sum_result, f"{device_id}/sum_result"
            )

            stop_calcualtor(device_ip)
            stop_zapper_camera(zapper_ip)

            if result_pos:
                print("Test passed")
                # Write the test result
                with open(f"images/{device_id}/test_result.txt", "a") as f:
                    f.write(f"{device_id} passed\n")
        except:
            print("Test failed")
            # Write the test result
            with open(f"images/{device_id}/test_result.txt", "a") as f:
                f.write(f"{device_id} failed\n")
            stop_calcualtor(device_ip)
            stop_zapper_camera(zapper_ip)
            continue
