import QtQuick 2.0
import Ubuntu.Components 0.1
import QtQuick.Layouts 1.1

Item {
    id: root
    signal testDone(var test);
    property var testingShell;

    Component.onCompleted: testingShell.pageStack.push(mainPage)

    Page {
        id: mainPage
        title: i18n.tr("A simple test")

        ColumnLayout {
            spacing: units.gu(10)
            anchors {
                margins: units.gu(5)
                fill: parent
            }

            Button {
                Layout.fillWidth: true; Layout.fillHeight: true
                text: i18n.tr("Next screen")
                color: "#38B44A"
                onClicked: {
                    testingShell.pageStack.push(subPage);
                }
            }
        }
    }


    Page {
        id: subPage
        visible: false
        ColumnLayout {
            spacing: units.gu(10)
            anchors {
                margins: units.gu(5)
                fill: parent
            }

            Text {
                text: i18n.tr("You can use toolbar to nagivage back")
            }

            Button {
                Layout.fillWidth: true; Layout.fillHeight: true
                text: i18n.tr("Pass")
                color: "#38B44A"
                onClicked: {
                    testDone({'outcome': 'pass'});
                }
            }

            Button {
                Layout.fillWidth: true; Layout.fillHeight: true
                text: i18n.tr("Fail")
                color: "#DF382C"
                onClicked: {
                    testDone({"outcome": "fail"});
                }
            }
        }
    }
}
