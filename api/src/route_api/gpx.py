"""GPX 1.1 export of a stored route: every point exactly as stored, in the same order."""

from xml.sax.saxutils import escape, quoteattr


def route_to_gpx(name: str, coordinates: list[list[float]], attribution: str) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="singapore-route-creator"'
        ' xmlns="http://www.topografix.com/GPX/1/1">',
        "  <metadata>",
        f"    <name>{escape(name)}</name>",
        f"    <desc>{escape(attribution)}</desc>",
        "  </metadata>",
        "  <trk>",
        f"    <name>{escape(name)}</name>",
        "    <trkseg>",
    ]
    for lon, lat in coordinates:
        lines.append(f"      <trkpt lat={quoteattr(repr(lat))} lon={quoteattr(repr(lon))}/>")
    lines += ["    </trkseg>", "  </trk>", "</gpx>", ""]
    return "\n".join(lines)
