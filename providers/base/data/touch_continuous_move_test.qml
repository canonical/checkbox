/* This file is part of Checkbox.

 Copyright 2015 Canonical Ltd.
 Written by:
 Sylvain Pineau <sylvain.pineau@canonical.com>

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

Rectangle {
    width: 500
    height: 500

    MouseArea {
        anchors.fill: parent
        anchors.margins: 30
        onPositionChanged: {
            if (timer2.running) {
                timer2.restart();
            }
        }
        hoverEnabled: true
    }

    Column {
        spacing: units.gu(5)
        anchors.centerIn: parent
        Text {
            id: legend
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Continuously move your mouse cursor"
            font.bold: true
            font.pointSize: 30
        }
        Text {
            id: countdown
            anchors.horizontalCenter: parent.horizontalCenter
            text: " "
            font.pointSize: 40
        }
    }

    Timer {
        id: timer1
        interval: 1000
        running: true
        repeat: true
        property int timeout: 11
        onTriggered: {
            timeout = timeout - 1
            countdown.text = timeout
            if (timeout <= 0) {
                running = false
                console.log("PASS")
                Qt.quit()
            }
        }
    }

    Timer {
        id: timer2
        interval: 200
        running: false
        repeat: true
        onTriggered: {
            running = false
            console.log("FAIL")
            Qt.quit()
        }
    }

    Timer {
        id: timer3
        interval: 2000
        running: true
        onTriggered: {
            timer2.running = true
        }
    }
}
