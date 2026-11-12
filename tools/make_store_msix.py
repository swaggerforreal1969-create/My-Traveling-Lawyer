"""Prepare an UNSIGNED private Store MSIX candidate. Never install or distribute it.

Only Microsoft Store certification can supply Store signing. Uses a previously
built standalone EXE and a reserved Partner Center package identity.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zlib

F = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
UAP = "http://schemas.microsoft.com/appx/manifest/uap/windows10"
UAP10 = "http://schemas.microsoft.com/appx/manifest/uap/windows10/10"
RESCAP = "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
for prefix, uri in (("", F), ("uap", UAP), ("uap10", UAP10), ("rescap", RESCAP)):
    ET.register_namespace(prefix, uri)

def require_identity(name, publisher, version):
    """Refuse speculative Store identities; never create a fake signed release."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,49}", name):
        raise ValueError("Use the exact app package name assigned in Partner Center")
    if not publisher.startswith("CN=") or len(publisher) < 5 or any(c in publisher for c in "\r\n"):
        raise ValueError("Use exact Partner Center Publisher distinguished name")
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version):
        raise ValueError("Version must have four numeric fields")

def manifest(name, publisher, publisher_display_name, version):
    require_identity(name, publisher, version)
    if not publisher_display_name.strip():
        raise ValueError("Publisher display name required")
    package = ET.Element(f"{{{F}}}Package", {"IgnorableNamespaces": "uap uap10 rescap"})
    ET.SubElement(package, f"{{{F}}}Identity", {
        "Name": name, "Publisher": publisher, "Version": version,
        "ProcessorArchitecture": "x64"})
    props = ET.SubElement(package, f"{{{F}}}Properties")
    for tag, value in (("DisplayName", "My Traveling Lawyer Practice"),
                       ("PublisherDisplayName", publisher_display_name),
                       ("Description", "Private fictional attorney practice only"),
                       ("Logo", "Assets\\StoreLogo.png")):
        ET.SubElement(props, f"{{{F}}}{tag}").text = value
    res = ET.SubElement(package, f"{{{F}}}Resources")
    ET.SubElement(res, f"{{{F}}}Resource", {"Language": "en-us"})
    deps = ET.SubElement(package, f"{{{F}}}Dependencies")
    ET.SubElement(deps, f"{{{F}}}TargetDeviceFamily", {
        "Name": "Windows.Desktop",
        "MinVersion": "10.0.19041.0",
        "MaxVersionTested": "10.0.26100.0"})
    apps = ET.SubElement(package, f"{{{F}}}Applications")
    app = ET.SubElement(apps, f"{{{F}}}Application", {
        "Id": "MyTravelingLawyerPractice",
        "Executable": "MyTravelingLawyer-Practice\\MyTravelingLawyer-Practice.exe",
        f"{{{UAP10}}}RuntimeBehavior": "packagedClassicApp",
        f"{{{UAP10}}}TrustLevel": "mediumIL"})
    ET.SubElement(app, f"{{{UAP}}}VisualElements", {
        "DisplayName": "My Traveling Lawyer Practice",
        "Description": "Fictional attorney testing only; no client data",
        "BackgroundColor": "#153047",
        "Square150x150Logo": "Assets\\Square150.png",
        "Square44x44Logo": "Assets\\Square44.png"})
    cap = ET.SubElement(package, f"{{{F}}}Capabilities")
    ET.SubElement(cap, f"{{{RESCAP}}}Capability", {"Name": "runFullTrust"})
    return ET.tostring(package, encoding="utf-8", xml_declaration=True)

def png(size):
    """Deterministic, simple branded placeholder icon; no outside image needed."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(
            ">I", zlib.crc32(kind + data) & 0xffffffff)
    pixels = bytearray()
    for y in range(size):
        pixels.append(0)
        for x in range(size):
            border = min(x, y, size - 1 - x, size - 1 - y) < max(2, size // 15)
            pixels.extend((245, 248, 250, 255) if border else (21, 48, 71, 255))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB",
            size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(pixels), 9))
            + chunk(b"IEND", b""))

def find_makeappx():
    candidates = []
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            candidates += list((Path(base) / "Windows Kits" / "10" / "bin").glob(
                "*/x64/makeappx.exe"))
    if not candidates:
        raise FileNotFoundError("Windows SDK MakeAppx not installed")
    return sorted(candidates, reverse=True)[0]

def build(exe_dir, output, name, publisher, display, version):
    payload = exe_dir / "MyTravelingLawyer-Practice.exe"
    if not payload.is_file():
        raise FileNotFoundError("Build the actual Windows PyInstaller onedir EXE first")
    if output.exists():
        raise FileExistsError("Refusing to overwrite existing package")
    xml = manifest(name, publisher, display, version)
    tool = find_makeappx()
    with tempfile.TemporaryDirectory(prefix="mtl-unsigned-msix-") as temp:
        stage = Path(temp) / "stage"
        stage.mkdir()
        shutil.copytree(exe_dir, stage / "MyTravelingLawyer-Practice",
                        symlinks=False)
        (stage / "AppxManifest.xml").write_bytes(xml)
        (stage / "Assets").mkdir()
        for file_name, size in (("Square150.png", 150), ("Square44.png", 44),
                                ("StoreLogo.png", 50)):
            (stage / "Assets" / file_name).write_bytes(png(size))
        subprocess.run([str(tool), "pack", "/d", str(stage), "/p",
                        str(output.resolve()), "/h", "SHA256"], check=True)
    print("UNSIGNED MSIX candidate only: never install or deliver to an evaluator.")
    print("Store signing requires Partner Center submission and certification.")
    return output

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-name", required=True,
                        help="Exact Store Partner Center package identity name")
    parser.add_argument("--publisher", required=True,
                        help="Exact Partner Center CN=... publisher identity")
    parser.add_argument("--publisher-display-name", required=True)
    parser.add_argument("--version", default="0.1.0.0")
    parser.add_argument("--exe-dir", type=Path, default=Path("dist/MyTravelingLawyer-Practice"))
    parser.add_argument("--output", type=Path, default=Path("dist/MyTravelingLawyer-Practice-UNSIGNED.msix"))
    parser.add_argument("--manifest-only", action="store_true")
    args = parser.parse_args()
    if args.manifest_only:
        print(manifest(args.package_name, args.publisher,
                       args.publisher_display_name, args.version).decode())
    else:
        build(args.exe_dir, args.output, args.package_name,
              args.publisher, args.publisher_display_name, args.version)

if __name__ == "__main__":
    main()
