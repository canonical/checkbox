import QtQuick 2.0
import QtQuick.Window 2.0
import QtQuick.Controls 1.4
import QtQuick.Layouts 1.2

Window {
    id: root
    width: 1280
    height: 720
    visible: true
    title: "Dynamic Refresh Rate Demo"
    color: "#1a1a1a"

    property int targetFps: 60
    property int rectCount: 5
    property int minFps: 10
    property int maxFps: 200    

    // old QT workaround, there's no 'Shortcuts' property on Window
    // in new QTs don't do this
    Item {
        anchors.fill: parent
        focus: true     
        Keys.onPressed: {
            if (event.key === Qt.Key_Escape) {
                root.close()
            }
        }
    }

    Timer {
        interval: 1000 / targetFps
        running: true
        repeat: true
        onTriggered: {
            // manually update the positions
            // this also implicitly changes the framerate to the requested one
            for (let i = 0; i < rectContainer.children.length; i++) {
                let rect = rectContainer.children[i];
                // this QT version doesn't support optional chaining
                // don't use rect?.updatePosition?.()
                // this also must be checked
                // since it doesn't exist on the very 1st frame
                if (rect.updatePosition) {
                    rect.updatePosition();
                }
            }
        }
    }

    // Container for the rectangles
    Item {
        id: rectContainer
        anchors.fill: parent
        
        Repeater {
            model: rectCount
            Rectangle {
                width: Screen.width * 0.05
                height: Screen.width * 0.05
                color: Qt.hsla(Math.random(), 0.6, 0.6, 0.9)
                radius: 4
                
                // velocity x and y
                property real vx: (Math.random() - 0.5) * 500
                property real vy: (Math.random() - 0.5) * 500

                Component.onCompleted: {
                    x = Math.random() * (root.width - width);
                    y = Math.random() * (root.height - height);
                }

                // Custom function called by the Timer
                function updatePosition() {
                    // normalize position change w.r.t. fps
                    x += vx / targetFps;
                    y += vy / targetFps;

                    // bounce at the walls
                    if (x <= 0 || x >= root.width - width) {
                        vx *= -1;
                    }
                    if (y <= 0 || y >= root.height - height) {
                        vy *= -1
                    }
                }
            }
        }
    }

    // Control Panel
    Rectangle {
        id: panel
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: contentColumn.implicitWidth + 50
        height: contentColumn.implicitHeight + 50
        color: "#cc000000"
        radius: 12
        border.color: "white"
        anchors.margins: 10    

        Column {
            id: contentColumn
            anchors.centerIn: parent
            spacing: 5
            
            Text {
                text: "Press Esc to quit"
                color: "white"
                font.bold: true
                anchors.left: parent.left
            }

            Text {
                text: "This test should be run at fullscreen"
                color: "grey"
                anchors.left: parent.left
            }
            
            Text {
                text: "Set GALLIUM_HUD=fps vblank_mode=3 MESA_VK_WSI_PRESENT_MODE=relaxed"
                color: "grey"
                anchors.left: parent.left
            }

            Text {
                text: "Look for tearing ONLY. Any stutter or fps mismatch is OK."
                color: "red"
                font.bold: true
                anchors.left: parent.left
            }

            Text {
                text: "Requested Refresh Rate: " + targetFps + " FPS"
                color: "white"
                font.bold: true
                anchors.horizontalCenter: parent.horizontalCenter
            }

            RowLayout {
                Layout.minimumHeight: 10
                Layout.fillWidth: true
                anchors.horizontalCenter: parent.horizontalCenter
                Button {
                    text: '-'
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    onClicked: {
                        targetFps = Math.max(minFps, targetFps - 1)
                    }
                }
                Slider {
                    minimumValue: minFps
                    maximumValue: maxFps
                    value: targetFps
                    onValueChanged: {
                        targetFps = Math.floor(value)
                    }
                }
                Button {
                    text: '+'
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    onClicked: {
                        targetFps = Math.min(maxFps, targetFps + 1)
                    }
                }
            }

            Text {
                text: "Number of rectangles: " + rectCount
                color: "white"
                font.bold: true
                anchors.horizontalCenter: parent.horizontalCenter
            }

            RowLayout {
                Layout.minimumHeight: 10
                Layout.fillWidth: true
                anchors.horizontalCenter: parent.horizontalCenter
                Button {
                    text: '-'
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    onClicked: {
                        rectCount = Math.max(1, rectCount - 1)
                    }
                }
                Slider {
                    minimumValue: 1
                    maximumValue: 10
                    value: rectCount
                    onValueChanged: {
                        rectCount = Math.floor(value)
                    }
                }
                Button {
                    text: '+'
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    onClicked: {
                        rectCount = Math.min(10, rectCount + 1)
                    }
                }
            }
        }
    }
}