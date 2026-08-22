import QtQuick
import QtTest
import "../../OmaQuickCalcModel.js" as Model

TestCase {
  name: "OmaQuickCalcModel"

  function test_preferences_patch_preserves_unrelated_settings() {
    var original = Model.parseSettings(JSON.stringify({
      backgroundOpacity: 0.92,
      historyMode: "persistent",
      precision: 17,
      defaultFromCurrency: "USD",
      defaultToCurrency: "CAD"
    }))
    var updated = Model.patchSettings(original, {
      backgroundOpacity: 0.65,
      historyMode: "session"
    })
    compare(updated.backgroundOpacity, 0.65)
    compare(updated.historyMode, "session")
    compare(updated.precision, 17)
    compare(updated.defaultFromCurrency, "USD")
    compare(updated.defaultToCurrency, "CAD")
  }

  function test_preferences_stay_bounded() {
    var updated = Model.patchSettings(Model.parseSettings("{}"), {
      backgroundOpacity: 5,
      defaultFromCurrency: "not-a-code"
    })
    compare(updated.backgroundOpacity, 1)
    compare(updated.defaultFromCurrency, "USD")
  }

  function test_choice_navigation_wraps() {
    var choices = ["first", "second", "third"]
    compare(Model.wrappedChoice(choices, "first", -1), "third")
    compare(Model.wrappedChoice(choices, "third", 1), "first")
    compare(Model.wrappedChoice(choices, "missing", 1), "second")
  }
}
