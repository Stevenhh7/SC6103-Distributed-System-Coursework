# Clean-source submission audit - 13 October 2026

All 200 automated tests and 16 real local UDP runs passed from a newly extracted source ZIP without Git metadata or compiled classes. See summary.json, environment.json and source-manifest.json. Runtime: actual Temurin Java 17.0.20.1, Python 3.13.1, macOS ARM64; javac 21.0.5 used --release 17.

Raw commands and CSV evidence fields preserve the original temporary checkout and output paths. Those absolute/relative run-time paths are provenance, not instructions to recreate those directories. For browsing this copied evidence directory, use matrix-index.json: each entry's directory is relative to this README. All original per-case artifacts are under matrix/<case>-<mode>/; boundary integration records are under network/.

Reproduce from any unpacked complete source archive: python3 -m experiments.verify_all --matrix. Use a new output directory; this retained evidence must not be overwritten. These are local-loopback tests, distinct from the 12 October three-computer rehearsal.
