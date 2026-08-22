.pragma library

var defaults = {
  version: 4,
  historyMode: "persistent",
  historyLimit: 100,
  historyRetentionDays: 90,
  saveOnClose: false,
  defaultAction: "copy-close",
  previewTimeoutMs: 250,
  submitTimeoutMs: 2000,
  qalcBinary: "qalc",
  unicode: true,
  digitGrouping: 0,
  precision: 10,
  clockFormat: "12",
  defaultFromCurrency: "USD",
  defaultToCurrency: "CAD",
  taxLocation: "auto",
  taxCustomRate: 0,
  rateStaleDays: 7,
  refreshExchangeRates: true,
  backgroundOpacity: 0.92,
  reducedMotion: false,
  remPx: 16,
  workdayHours: 8,
  inputHint: "Type a calculation…"
}

function boundedNumber(value, fallback, minimum, maximum) {
  var number = Number(value)
  if (!isFinite(number)) return fallback
  return Math.max(minimum, Math.min(maximum, number))
}

function boundedInteger(value, fallback, minimum, maximum) {
  return Math.round(boundedNumber(value, fallback, minimum, maximum))
}

function parseSettings(raw) {
  var parsed = ({})
  try {
    parsed = JSON.parse(String(raw || "{}"))
  } catch (error) {
    parsed = ({})
  }

  var mode = String(parsed.historyMode || defaults.historyMode)
  if (["persistent", "session", "disabled"].indexOf(mode) < 0)
    mode = defaults.historyMode

  var action = String(parsed.defaultAction || defaults.defaultAction)
  if (["copy-close", "copy-stay", "reuse"].indexOf(action) < 0)
    action = defaults.defaultAction

  var clockFormat = String(parsed.clockFormat || defaults.clockFormat)
  if (["auto", "12", "24"].indexOf(clockFormat) < 0)
    clockFormat = defaults.clockFormat
  // Version 2 generated `auto`, which follows a 24-hour system locale on many
  // Omarchy installs. Version 3 adopts the requested 12-hour default while
  // preserving explicit choices made after migration.
  if (Number(parsed.version) === 2 && clockFormat === "auto")
    clockFormat = defaults.clockFormat

  var fromCurrency = String(parsed.defaultFromCurrency || defaults.defaultFromCurrency).toUpperCase()
  var toCurrency = String(parsed.defaultToCurrency || defaults.defaultToCurrency).toUpperCase()
  if (!/^[A-Z]{3}$/.test(fromCurrency)) fromCurrency = defaults.defaultFromCurrency
  if (!/^[A-Z]{3}$/.test(toCurrency)) toCurrency = defaults.defaultToCurrency

  var taxLocation = String(parsed.taxLocation || defaults.taxLocation)
  if (["auto", "custom"].indexOf(taxLocation.toLowerCase()) >= 0)
    taxLocation = taxLocation.toLowerCase()
  else {
    taxLocation = taxLocation.toUpperCase()
    if ([
      "CA-AB", "CA-BC", "CA-MB", "CA-NB", "CA-NL", "CA-NS", "CA-NT",
      "CA-NU", "CA-ON", "CA-PE", "CA-QC", "CA-SK", "CA-YT", "AU", "NZ",
      "GB", "DE", "FR", "IT", "ES", "PL", "NL", "IN", "CN", "JP", "MX",
      "SG", "ZA", "SA", "AE"
    ].indexOf(taxLocation) < 0) taxLocation = defaults.taxLocation
  }

  return {
    version: 4,
    historyMode: mode,
    historyLimit: boundedInteger(parsed.historyLimit, defaults.historyLimit, 1, 1000),
    historyRetentionDays: boundedInteger(parsed.historyRetentionDays,
      defaults.historyRetentionDays, 1, 3650),
    saveOnClose: parsed.saveOnClose === undefined ? defaults.saveOnClose : Boolean(parsed.saveOnClose),
    defaultAction: action,
    previewTimeoutMs: boundedInteger(parsed.previewTimeoutMs, defaults.previewTimeoutMs, 50, 10000),
    submitTimeoutMs: boundedInteger(parsed.submitTimeoutMs, defaults.submitTimeoutMs, 100, 60000),
    qalcBinary: String(parsed.qalcBinary || defaults.qalcBinary),
    unicode: parsed.unicode === undefined ? defaults.unicode : Boolean(parsed.unicode),
    digitGrouping: boundedInteger(parsed.digitGrouping, defaults.digitGrouping, 0, 2),
    precision: boundedInteger(parsed.precision, defaults.precision, 2, 50),
    clockFormat: clockFormat,
    defaultFromCurrency: fromCurrency,
    defaultToCurrency: toCurrency,
    taxLocation: taxLocation,
    taxCustomRate: boundedNumber(parsed.taxCustomRate, defaults.taxCustomRate, 0, 100),
    rateStaleDays: boundedInteger(parsed.rateStaleDays, defaults.rateStaleDays, 1, 365),
    refreshExchangeRates: parsed.refreshExchangeRates === undefined
      ? defaults.refreshExchangeRates : Boolean(parsed.refreshExchangeRates),
    backgroundOpacity: boundedNumber(parsed.backgroundOpacity,
      defaults.backgroundOpacity, 0, 1),
    reducedMotion: parsed.reducedMotion === undefined
      ? defaults.reducedMotion : Boolean(parsed.reducedMotion),
    remPx: boundedNumber(parsed.remPx, defaults.remPx, 1, 512),
    workdayHours: boundedNumber(parsed.workdayHours, defaults.workdayHours, 1, 24),
    inputHint: String(parsed.inputHint || defaults.inputHint)
  }
}

function patchSettings(current, changes) {
  var next = ({})
  var source = current && typeof current === "object" ? current : defaults
  var patch = changes && typeof changes === "object" ? changes : ({})
  for (var key in source) next[key] = source[key]
  for (var changedKey in patch) next[changedKey] = patch[changedKey]
  return parseSettings(JSON.stringify(next))
}

function wrappedChoice(choices, current, delta) {
  if (!Array.isArray(choices) || choices.length === 0) return current
  var index = choices.indexOf(current)
  if (index < 0) index = 0
  var offset = Math.round(Number(delta) || 0)
  return choices[(index + offset % choices.length + choices.length) % choices.length]
}

function normalizeEntry(value) {
  if (!value || typeof value !== "object") return null
  var expression = String(value.expression || "").trim()
  var result = String(value.result || "").trim()
  if (!expression || !result) return null
  return {
    expression: expression,
    result: result,
    rawResult: String(value.rawResult || result).trim(),
    kind: String(value.kind || "math"),
    dynamic: Boolean(value.dynamic),
    pinned: Boolean(value.pinned),
    timestamp: boundedInteger(value.timestamp, Date.now(), 0, 9007199254740991)
  }
}

function parseHistory(raw, limit, retentionDays) {
  var parsed
  try {
    parsed = JSON.parse(String(raw || "[]"))
  } catch (error) {
    return []
  }
  if (!Array.isArray(parsed)) return []

  var output = []
  var maximum = boundedInteger(limit, defaults.historyLimit, 1, 1000)
  var retention = boundedInteger(retentionDays, defaults.historyRetentionDays, 1, 3650)
  var oldest = Date.now() - retention * 24 * 60 * 60 * 1000
  for (var index = 0; index < parsed.length && output.length < maximum; index += 1) {
    var entry = normalizeEntry(parsed[index])
    if (entry && (entry.pinned || entry.timestamp >= oldest)) output.push(entry)
  }
  return output
}

function addHistoryEntry(history, value, limit) {
  var entry = normalizeEntry(value)
  if (!entry) return Array.isArray(history) ? history.slice() : []

  var maximum = boundedInteger(limit, defaults.historyLimit, 1, 1000)
  var current = Array.isArray(history) ? history : []
  for (var currentIndex = 0; currentIndex < current.length; currentIndex += 1) {
    var duplicate = normalizeEntry(current[currentIndex])
    if (duplicate && duplicate.expression === entry.expression
        && (duplicate.result === entry.result || duplicate.dynamic || entry.dynamic)
        && duplicate.pinned)
      entry.pinned = true
  }
  var output = [entry]
  for (var index = 0; index < current.length && output.length < maximum; index += 1) {
    var existing = normalizeEntry(current[index])
    if (!existing) continue
    if (existing.expression === entry.expression
        && (existing.result === entry.result || existing.dynamic || entry.dynamic)) continue
    output.push(existing)
  }
  return output
}

function filterHistory(history, query) {
  var current = Array.isArray(history) ? history : []
  var needle = String(query || "").trim().toLowerCase()
  var pinned = []
  var regular = []
  for (var index = 0; index < current.length; index += 1) {
    var entry = normalizeEntry(current[index])
    if (!entry) continue
    if (needle && (entry.expression + "\n" + entry.result).toLowerCase().indexOf(needle) < 0)
      continue
    entry.historyIndex = index
    if (entry.pinned) pinned.push(entry)
    else regular.push(entry)
  }
  return pinned.concat(regular)
}

function toggleHistoryPin(history, index) {
  var current = Array.isArray(history) ? history.slice() : []
  if (index < 0 || index >= current.length) return current
  var entry = normalizeEntry(current[index])
  if (!entry) return current
  entry.pinned = !entry.pinned
  current[index] = entry
  return current
}

function removeHistoryEntry(history, index) {
  var current = Array.isArray(history) ? history : []
  if (index < 0 || index >= current.length) return current.slice()
  return current.slice(0, index).concat(current.slice(index + 1))
}

function singleLine(value) {
  return String(value || "").replace(/\s*\r?\n+\s*/g, "  ")
}
