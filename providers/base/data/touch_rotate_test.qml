/* This file is part of Checkbox.

 Copyright 2014 Canonical Ltd.
 Written by:
 Daniel Manrique <roadmr@ubuntu.com>

 Checkbox is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License version 3,
 as published by the Free Software Foundation.

 Checkbox is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
*/
import QtQuick 2.0
import Ubuntu.Components 0.1

Rectangle{
    id: mainWindow
    width: 400
    height: 400
    focus: true
    Keys.onEscapePressed: {
        console.log("ESC pressed, exiting")
        Qt.quit()
    }
    PinchArea {
        anchors.fill: parent
        property var startpinchangle
        property var rotangle
        property var currentangle
        onPinchStarted: {
            startpinchangle = pinch.angle
            rotangle = rotatable.rotation
        }
        onPinchUpdated: {
            if (startpinchangle != null){
                currentangle = rotangle - (pinch.angle - startpinchangle)
                rotatable.rotation = currentangle
            }
            if (Math.abs(currentangle) < 1){
                rotatable.color = "green"
            }
            else if(Math.abs(Math.abs(currentangle) - 180) < 1){
                rotatable.color = "green"
            }
            else{
                rotatable.color = "blue"
            }
        }
        onPinchFinished:{
            console.log("Current angle: " + Math.abs(currentangle))
            if (Math.abs(currentangle) < 1 ||
            Math.abs(Math.abs(currentangle) - 180) < 1){
                console.log("PASS")
                timer.running = false
                Qt.quit()
            }
        }
    }
    Rectangle{
        id: instructions
        z: 1 // So it appears on top
        height: mainWindow.height / 3
        anchors.margins: units.gu(1.5)
        anchors.top: mainWindow.top
        anchors.left: mainWindow.left
        anchors.right: mainWindow.right
        color: "#aaaaaa"
        radius: 10
        Text {
            id: text
            anchors.fill: instructions
            anchors.margins: units.gu(1.5)
            font.pointSize: units.gu(1.5)
            property var timeout: 30
            text: "Using two fingers, rotate the blue rectangle so it fits within the red outline. " +
            "Press ESC to cancel the test at any time. <b>Test will exit automatically in " +
            timeout + " seconds </b>"
            wrapMode: Text.Wrap
        }
    }

    Timer {
        id: timer
        interval: 1000
        running: true
        repeat: true
        onTriggered: {
            text.timeout = text.timeout - 1
            if (text.timeout <= 0) {
                running = false
                console.log("TIMED OUT - no action detected")
                Qt.quit()
            }
        }
    }

    Rectangle{
        id: goalsize
        anchors.top: instructions.bottom
        anchors.margins: units.gu(8)
        anchors.right: mainWindow.right
        anchors.left: mainWindow.left
        anchors.bottom: mainWindow.bottom
        anchors.bottomMargin: units.gu(10)
        border.color: "red"
        border.width: 4
    }

    Rectangle{
        id: rotatable
        anchors.horizontalCenter: goalsize.horizontalCenter
        anchors.verticalCenter: goalsize.verticalCenter
        width: goalsize.width * 0.95
        height: goalsize.height * 0.85
        color: "blue"
        rotation: 45
    }
}

