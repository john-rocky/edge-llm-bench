# r2 assets — CLiteRTLM_mac.xcframework.zip, v0.17.0 vs v0.17.1 (2026-10-08 01:38 JST)

Downloaded with `gh release download <tag> -R google-ai-edge/LiteRT-LM -p 'CLiteRTLM_mac.xcframework.zip' -D ~/.cache/litert-lm-retest/assets/<v0170|v0171>` (via quiet_wait, exit 0 both). Unzipped to `<dir>/x/`.

| release asset | zip sha256 | zip size (B) | `libCLiteRTLM_mac.dylib` sha256 | dylib size (B) |
|---|---|---|---|---|
| v0.17.0 `CLiteRTLM_mac.xcframework.zip` | 83efd536485c9d58fcd7fb7d4556ddb16ca46bb775b0449d08d9825c6836c1a4 | 47,006,925 | ece7f316cdcf0552caf7bbc1fc151fd4da068aa801caa5510c30440d66b1a585 | 144,666,096 |
| v0.17.1 `CLiteRTLM_mac.xcframework.zip` | 83efd536485c9d58fcd7fb7d4556ddb16ca46bb775b0449d08d9825c6836c1a4 | 47,006,925 | ece7f316cdcf0552caf7bbc1fc151fd4da068aa801caa5510c30440d66b1a585 | 144,666,096 |

- v0.17.1 `Package.swift` (5e58e9a0) pins `CLiteRTLM_mac` = `releases/download/v0.17.0/CLiteRTLM_mac.xcframework.zip`, checksum `83efd536485c9d58fcd7fb7d4556ddb16ca46bb775b0449d08d9825c6836c1a4` = both zips above (`cmp` identical).
- Therefore: the v0.17.0 zip that the v0.17.1 Swift package pins carries a dylib byte-identical to the dylib in the v0.17.1 release zip. Package.swift is NOT edited (step (3) no-op).
- dylib slices: `lipo -info` = x86_64 arm64 (see ROUND2.md).

## Linked dylib after the step (3) build (2026-10-08 01:42 JST)
- `find $WT/.build/dd-mac-0171 -name libCLiteRTLM_mac.dylib -exec shasum -a 256 {} \;` → both copies `ece7f316cdcf0552caf7bbc1fc151fd4da068aa801caa5510c30440d66b1a585` (144,666,096 B): `Build/Products/Release/libCLiteRTLM_mac.dylib` and `SourcePackages/artifacts/litert-lm/CLiteRTLM_mac/CLiteRTLM_mac.xcframework/macos-arm64_x86_64/libCLiteRTLM_mac.dylib`.
- = the v0.17.1 release dylib in the table above (match). The yardstick loads `@rpath/libCLiteRTLM_mac.dylib` (otool -L) with LC_RPATH `@executable_path` → the `Build/Products/Release` copy.
