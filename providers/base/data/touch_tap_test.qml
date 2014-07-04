import Ubuntu.Components 0.1
import QtQuick 2.0

Rectangle {
    id: main
    color: "black"
    width: 800
    height: 600
    focus:true
    Keys.onEscapePressed: {Qt.quit()}

    Arguments {
        id: args

        Argument {
            name: "touchpoints"
            help: "minimum TouchPoints"
            required: true
            valueNames: ["TouchPoints"]
        }
    }

    Text {
        id: text
        color: "white"
        font.pointSize: units.gu(1.5)
        property var timeout: 15
        text: "<p>Touch the screen with "+args.values.touchpoints+" fingers at the same time</p>" +
        "<p>Press ESC to cancel the test at any time.</p>" +
        "<p><b>Test will exit automatically in " +
        timeout + " seconds </b></p>"
        wrapMode: Text.Wrap
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
                Qt.quit()
            }
        }
    }

    // Visual presentation of the touch points
    Repeater {
        id: touchBalls
        model: multiArea.points

        Item {
            x: modelData.x
            y: modelData.y

            Rectangle {
                anchors.centerIn: parent
                color: "white"
                opacity: 0.1
                width: 1000 * modelData.pressure
                height: width
                radius: width / 2
            }

            Rectangle {
                anchors.centerIn: parent
                color: "#20cc2c"
                opacity: modelData.pressure * 10
                width: 100
                height: width
                radius: width / 2
            }
        }
    }

    MultiPointTouchArea {
        id: multiArea

        property variant points: []
        property var done

        enabled: true
        anchors.fill: parent

        minimumTouchPoints: args.values.touchpoints
        maximumTouchPoints: minimumTouchPoints

        onReleased: {
            points = touchPoints;
            if (done) {
                console.log("PASS")
                Qt.quit();
            }
        }
        onPressed: {
            points = touchPoints;
            done = true
        }
    }

}
