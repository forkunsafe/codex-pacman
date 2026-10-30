#!/usr/bin/env python3
"""Create a self-contained SVG preview; --png also renders it with native AppKit."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'plugin'/'.codex-pacman'))
from ui import icon


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--png', action='store_true', help='Also create a 2x Retina PNG using the macOS Swift developer tools')
    args = parser.parse_args()
    values = (100, 75, 50, 25, 0)
    samples = [{'remaining': value, 'png': icon(value)} for value in values]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="600" height="240" viewBox="0 0 600 240">',
           '<rect width="600" height="240" rx="12" fill="#5A718E"/>',
           '<g font-family="Helvetica,Arial,sans-serif" fill="white">',
           '<text x="24" y="26" font-size="14">5-hour remaining quota · native 16 pt / Retina</text>']
    for index, sample in enumerate(samples):
        center = 72 + index*114
        uri = 'data:image/png;base64,' + sample['png']
        svg += ['<text x="%d" y="52" text-anchor="middle" font-size="12">%d%%</text>' % (center, sample['remaining']),
                '<image x="%d" y="66" width="16" height="16" href="%s"/>' % (center-8, uri),
                '<image x="%d" y="112" width="80" height="80" style="image-rendering:pixelated" href="%s"/>' % (center-40, uri)]
    svg += ['<text x="24" y="220" font-size="11">Top: actual icon size. Bottom: 5× pixel detail. Synthetic values.</text>', '</g></svg>']
    output = ROOT/'docs'/'usage-icon-preview.svg'
    output.write_text('\n'.join(svg)+'\n')
    print(output.name)
    if not args.png:
        return
    scratch = ROOT/'.state'/'usage-preview'
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch/'samples.json').write_text(json.dumps(samples))
    swift = r'''
import AppKit
import Foundation
let samples = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))) as! [[String: Any]]
let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1200, pixelsHigh: 480, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
let context = NSGraphicsContext(bitmapImageRep: bitmap)!
NSGraphicsContext.current = context
context.cgContext.scaleBy(x: 2, y: 2)
NSColor(srgbRed: 90/255, green: 113/255, blue: 142/255, alpha: 1).setFill()
NSRect(x: 0, y: 0, width: 600, height: 240).fill()
func text(_ value: String, _ x: CGFloat, _ y: CGFloat, _ size: CGFloat) {
    (value as NSString).draw(at: NSPoint(x: x, y: y), withAttributes: [.font: NSFont.systemFont(ofSize: size), .foregroundColor: NSColor.white])
}
text("5-hour remaining quota · native 16 pt / Retina", 24, 210, 14)
for (index, sample) in samples.enumerated() {
    let center = CGFloat(72 + index*114)
    let label = "\(sample["remaining"]!)%"
    text(label, center-16, 183, 12)
    let image = NSImage(data: Data(base64Encoded: sample["png"] as! String)!)!
    context.imageInterpolation = .none
    image.draw(in: NSRect(x: center-8, y: 158, width: 16, height: 16))
    image.draw(in: NSRect(x: center-40, y: 48, width: 80, height: 80))
}
text("Top: actual icon size. Bottom: 5× pixel detail. Synthetic values.", 24, 12, 11)
NSGraphicsContext.restoreGraphicsState()
try bitmap.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[2]))
'''
    script = scratch/'render.swift'
    script.write_text(swift)
    env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(scratch/'module-cache'))
    subprocess.run(['swift', str(script), str(scratch/'samples.json'), str(output.with_suffix('.png'))], check=True, env=env)
    print(output.with_suffix('.png').name)


if __name__ == '__main__':
    main()
