import QtQuick
import "../.." as Calc
Rectangle {
 width: 960; height: 360
 color: "#101315"
 property string resultText: ""
 Text { x: 30; y: 28; text: "OmaQuickCalc · isolated Wayland candidate"; color: "#a5a19a"; font.pixelSize: 18 }
 Rectangle {
  x: 20; y: 90; width: 920; height: 180
  color: "#201a13"; border.color: "#b69a6b"; border.width: 2
  Calc.GuardedInput {
   id: field; objectName: "field"
   x: 25; y: 10; width: 870; height: 65
   font.family: "monospace"; font.pixelSize: 30
   color: "#a5a19a"; selectionColor: "#53432e"; selectedTextColor: "#e2c575"
   onEdited: function(updated) { value = updated }
   onPasteRequested: function(primary, capacity, serial) {
    testBroker.request(field, primary, capacity, serial)
   }
  }
  Rectangle { x: 25; y: 78; width: 870; height: 1; color: "#b69a6b" }
  Text { x: 25; y: 105; text: resultText; color: "#e2c575"; font.family: "monospace"; font.pixelSize: 40; font.bold: true }
 }
}
