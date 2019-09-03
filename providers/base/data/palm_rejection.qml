/*
 * This file is part of Checkbox.
 *
 * Copyright 2018-2019 Canonical Ltd.
 * Written by:
 *   Maciej Kisielewski <maciej.kisielewski@canonical.com>
 *
 * Checkbox is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3,
 * as published by the Free Software Foundation.
 *
 * Checkbox is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
 */
import QtQuick 2.5
import QtQuick.Layouts 1.2
import QtQuick.Controls 1.4

Item {
    property var steps: [
        ['images/palm-rejection-1.jpg', 2000],
        ['images/palm-rejection-2.jpg', 500],
        ['images/palm-rejection-3.jpg', 1000],
        ['images/palm-rejection-4.jpg', 500],
        ['images/palm-rejection-5.jpg', 500],
        ['images/palm-rejection-6.jpg', 1000],
        ['images/palm-rejection-7.jpg', 1000],
    ]
    property var currentStep: 0

    anchors.fill: parent

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 30
        Image {
            source: steps[currentStep][0]
            fillMode: Image.PreserveAspectFit
            Layout.fillHeight: true
            Layout.fillWidth: true
        }
        Label {
            text: "The cursor <b>SHOULD NOT</b> move with the palm movement?"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            Layout.minimumHeight: 30
            Layout.fillHeight: true
            Layout.fillWidth: true
        }
        RowLayout {
            Layout.minimumHeight: 10
            Layout.fillWidth: true
            Button {
                text: 'Pass'
                Layout.fillHeight: true
                Layout.fillWidth: true
                onClicked: {
                    console.log('PASS')
                    Qt.quit()
                }
            }
            Button {
                text: 'Fail'
                Layout.fillHeight: true
                Layout.fillWidth: true
                onClicked: Qt.quit()
            }
        }
    }
    Timer {
        interval: steps[currentStep][1]
        running: true
        repeat: true
        onTriggered: {
            currentStep = (currentStep + 1) % steps.length;
        }
    }
}
