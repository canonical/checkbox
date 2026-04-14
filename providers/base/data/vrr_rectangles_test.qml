import QtQuick 2.0
import QtQuick.Window 2.0
import QtQuick.Controls 1.4

Window {
    id: root
    width: 800
    height: 600
    visible: true
    title: "Dynamic Refresh Rate Demo"
    color: "#1a1a1a"

    property int targetFps: 60
    property int rectCount: 5

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
            for (let i = 0; i < rectContainer.children.length; i++) {
                let rect = rectContainer.children[i];
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
                
                property real vx: (Math.random() - 0.5) * 500
                property real vy: (Math.random() - 0.5) * 500

                Component.onCompleted: {
                    x = Math.random() * (root.width - width);
                    y = Math.random() * (root.height - height);
                }

                // Custom function called by the Timer
                function updatePosition() {
                    x += vx / targetFps;
                    y += vy / targetFps;

                    // Bounce logic
                    if (x <= 0 || x >= root.width - width) vx *= -1;
                    if (y <= 0 || y >= root.height - height) vy *= -1;
                }
            }
        }
    }

    // Control Panel
    Rectangle {
        id: "panel"
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: contentColumn.implicitWidth + 50
        height: contentColumn.implicitHeight + 50
        color: "#cc000000"
        radius: 12
        border.color: "white"
        anchors.margins: 20

        Column {
            id: contentColumn
            anchors.centerIn: parent
            spacing: 5
            
            Text {
                text: "Press Esc to quit"
                color: "white"
                font.bold: true
                anchors.horizontalCenter: parent.horizontalLeft
            }

            Text {
                text: "This test should be run at fullscreen"
                color: "grey"
                anchors.horizontalCenter: parent.horizontalLeft
            }
            
            Text {
                text: "Set GALLIUM_HUD=fps vblank_mode=0"
                color: "grey"
                anchors.horizontalCenter: parent.horizontalLeft
            }

            Text {
                text: "Look for tearing ONLY. Any stutter or fps mismatch is OK."
                color: "red"
                font.bold: true
                anchors.horizontalCenter: parent.horizontalLeft
            }

            Text {
                text: "Refresh Rate: " + targetFps + " FPS"
                color: "white"
                font.bold: true
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Slider {
                minimumValue: 20
                maximumValue: 200
                value: 60
                onValueChanged: {
                    targetFps = Math.floor(value)
                }
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Text {
                text: "Number of rectangles: " + rectCount
                color: "white"
                font.bold: true
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Slider {
                minimumValue: 1
                maximumValue: 10
                value: rectCount
                onValueChanged: {
                    rectCount = value
                }
                anchors.horizontalCenter: parent.horizontalCenter
            }
        }
    }
}