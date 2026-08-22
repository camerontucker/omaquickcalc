import QtQuick
import QtTest
import "../.." as OmaQuickCalc

TestCase {
  name: "OmaQuickCalcPlainText"

  Component {
    id: labelComponent
    OmaQuickCalc.PlainText {}
  }

  function test_markup_shaped_values_remain_plain_text() {
    var label = createTemporaryObject(labelComponent, this, {
      text: '<img src="file:///tmp/should-not-load"> <b>value</b>'
    })
    verify(label !== null)
    compare(label.textFormat, Text.PlainText)
    compare(label.text, '<img src="file:///tmp/should-not-load"> <b>value</b>')
  }
}
