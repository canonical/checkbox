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
import sys
import subprocess
from checkbox_support.scripts.zapper_proxy import zapper_run  # noqa: E402


screen_size = (3456, 2160)

# Homography matrix from your data
homography_matrix = np.array(
    [
        [2.3497401216403873, 0.32739839205407256, -430.2644530168988],
        [-0.03441855074237415, 2.574459827018083, -240.52384223791717],
        [-0.000004170753263481942, 0.00015643521128339517, 1],
    ]
)


def apply_homography_to_capture(img):
    img = cv2.warpPerspective(img, homography_matrix, screen_size)
    return img


def compare_two_images(reference, template):
    # Load the reference image and the template
    img = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    w, h = template.shape[::-1]

    # All the 6 methods for comparison in a list
    threshold = 0.8

    img2 = img.copy()

    res = cv2.matchTemplate(img2, template, cv2.TM_CCORR_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    top_left = max_loc
    match_val = max_val

    # Check if the match value meets the threshold
    if match_val >= threshold:
        bottom_right = (top_left[0] + w, top_left[1] + h)
        cv2.rectangle(img2, top_left, bottom_right, 0, 20)
    else:
        return None

    # print the center of the rectangle
    center = (top_left[0] + w // 2, top_left[1] + h // 2)
    print(f"Center of the rectangle: ({center[0]}, {center[1]})")
    return center


def click_position(zapper_ip, position):
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

    # if i set the mouse
    x = position[0] / 4
    y = position[1] / 4

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


if __name__ == "__main__":
    zapper_ip = sys.argv[1]
    device_ip = sys.argv[2]
    calc_top_raw = cv2.imread("images/snapshot_calc_top.jpg")

    calc_top = apply_homography_to_capture(calc_top_raw)


    # start the calculator app with from ssh to the device

    print("Running the calculator app")
    calculator_process = subprocess.Popen(["gnome-calculator"])
    import time
    time.sleep(4)

    number_2 = cv2.imread("images/number_2.jpg")
    plus = cv2.imread("images/plus.jpg")
    equal = cv2.imread("images/equal.jpg")

    number_2_pos = compare_two_images(calc_top, number_2)
    plus_pos = compare_two_images(calc_top, plus)
    equal_pos = compare_two_images(calc_top, equal)

    click_position(zapper_ip, number_2_pos)
    time.sleep(2)
    click_position(zapper_ip, plus_pos)
    time.sleep(2)
    click_position(zapper_ip, number_2_pos)
    time.sleep(2)
    click_position(zapper_ip, equal_pos)
    time.sleep(2)

    number_2 = cv2.imread("images/result.jpg")
    result_pos = compare_two_images(calc_top, number_2)
    print("Result found at position: ", result_pos)
    time.sleep(4)

    print("Test finished. Closing the calculator.")
    calculator_process.terminate()
    calculator_process.wait()

    if result_pos:
        print("Test passed")
