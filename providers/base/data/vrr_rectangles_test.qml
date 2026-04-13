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

    property int targetFps: 10
    property int rectCount: 10

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
                width: 30; height: 30
                color: Qt.hsla(Math.random(), 0.6, 0.6, 0.9)
                radius: 4
                
                // State variables for manual movement
                property real vx: (Math.random() - 0.5) * 10
                property real vy: (Math.random() - 0.5) * 10

                Component.onCompleted: {
                    x = Math.random() * (root.width - width);
                    y = Math.random() * (root.height - height);
                }

                // Custom function called by the Timer
                function updatePosition() {
                    x += vx;
                    y += vy;

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
        width: 400
        height: 180
        color: "#cc000000"
        radius: 10
        border.color: "white"
        anchors.margins: 20

        Column {
            anchors.centerIn: parent
            spacing: 5
            // anchors.margins: 5
            
            Text {
                text: "Press Esc to quit"
                color: "grey"
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Text {
                text: "Refresh Rate: " + targetFps + " FPS"
                color: "white"
                font.bold: true
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Slider {
                minimumValue: 48
                maximumValue: 120
                value: 60
                // onMoved: targetFps = value
                onValueChanged: {
                    targetFps = Math.floor(value)
                }
            }
        }
    }
}