# 2026-09-10 11:40–11:43 JST — Galaxy S26, GPU backend, first attempt: the APK could not load OpenCL

Same device, model and APK build as the gate2 CPU run, `backend=gpu`. Every gate question and every
run failed at the first message with `LiteRtLmJniException: … Can not find OpenCL library on this
device`. The device has OpenCL (the native lane's GPU rows on this S26 use it); the cause is the
app manifest: Android 12+ hides vendor libraries from apps that do not declare them with
`<uses-native-library>`. Fixed in the manifest (`libOpenCL.so`, `libOpenCL-car.so`,
`libOpenCL-pixel.so`, all `required=false`) and re-run as `…-gpu2-android`. The three records are
quarantined (`*.json.gate-fail`): no decode rate, gate FAIL (form 0/8: every answer errored).
