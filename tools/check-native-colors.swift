import AppKit
let text = NSAttributedString(string: "100% remaining", attributes: [
    .foregroundColor: NSColor.controlTextColor,
    .font: NSFont(name: "Menlo-Bold", size: 13)!
])
let stored = text.attribute(.foregroundColor, at: 0, effectiveRange: nil) as! NSColor
var brightness: [CGFloat] = []
for name in [NSAppearance.Name.aqua, .darkAqua, .aqua] {
    let appearance = NSAppearance(named: name)!
    appearance.performAsCurrentDrawingAppearance {
        let resolved = stored.usingColorSpace(.sRGB)!
        brightness.append((resolved.redComponent + resolved.greenComponent + resolved.blueComponent) / 3)
        print("\(name.rawValue): cached native text RGB \(resolved.redComponent), \(resolved.greenComponent), \(resolved.blueComponent)")
    }
}
precondition(brightness[1] - brightness[0] > 0.5)
precondition(abs(brightness[2] - brightness[0]) < 0.01)
print("PASS: the same attributed text adapts Aqua → Dark Aqua → Aqua without rebuilding it or changing system settings.")
