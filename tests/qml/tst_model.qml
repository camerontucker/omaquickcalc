import QtQuick
import QtTest
import "../../OmaQuickCalcModel.js" as Model

TestCase {
  name: "OmaQuickCalcModel"

  function test_preferences_patch_preserves_unrelated_settings() {
    var original = Model.parseSettings(JSON.stringify({
      backgroundOpacity: 0.92,
      reducedMotion: false,
      historyMode: "persistent",
      precision: 17,
      defaultFromCurrency: "USD",
      defaultToCurrency: "CAD"
    }))
    var updated = Model.patchSettings(original, {
      backgroundOpacity: 0.65,
      historyMode: "session",
      reducedMotion: true
    })
    compare(updated.backgroundOpacity, 0.65)
    compare(updated.historyMode, "session")
    compare(updated.reducedMotion, true)
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

  function test_time_format_defaults_to_12_hour_and_remains_configurable() {
    compare(Model.parseSettings("{}").clockFormat, "12")
    compare(Model.parseSettings(JSON.stringify({ version: 2, clockFormat: "auto" })).clockFormat,
      "12")
    compare(Model.parseSettings(JSON.stringify({ version: 3, clockFormat: "auto" })).clockFormat,
      "auto")
    compare(Model.patchSettings(Model.parseSettings("{}"), { clockFormat: "24" }).clockFormat,
      "24")
    compare(Model.patchSettings(Model.parseSettings("{}"), { clockFormat: "auto" }).clockFormat,
      "auto")
  }

  function test_tax_location_defaults_to_auto_and_validates_supported_regions() {
    compare(Model.parseSettings("{}").taxLocation, "auto")
    compare(Model.patchSettings(Model.parseSettings("{}"), { taxLocation: "ca-mb" }).taxLocation,
      "CA-MB")
    compare(Model.patchSettings(Model.parseSettings("{}"), { taxLocation: "CA-ON" }).taxLocation,
      "CA-ON")
    compare(Model.patchSettings(Model.parseSettings("{}"), { taxLocation: "not-a-place" }).taxLocation,
      "auto")
    compare(Model.patchSettings(Model.parseSettings("{}"), {
      taxLocation: "custom", taxCustomRate: 8.25
    }).taxLocation, "custom")
    compare(Model.patchSettings(Model.parseSettings("{}"), { taxCustomRate: 125 }).taxCustomRate,
      100)
  }

  function test_choice_navigation_wraps() {
    var choices = ["first", "second", "third"]
    compare(Model.wrappedChoice(choices, "first", -1), "third")
    compare(Model.wrappedChoice(choices, "third", 1), "first")
    compare(Model.wrappedChoice(choices, "missing", 1), "second")
  }
}
