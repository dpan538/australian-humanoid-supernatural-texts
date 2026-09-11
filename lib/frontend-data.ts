export const FRONTEND_DATA_URL =
  process.env.NEXT_PUBLIC_FRONTEND_DATA_URL || "/data/frontend-interactive.json";
export const MOBILE_ARCHIVE_DATA_URL = "/data/mobile-archive";
export const FRONTEND_DATA_SCHEMA = "frontend-data/v1";
// Decoded byte size of the interactive export at the last review. The boot
// screen only uses it to pace the pixel figure when the response is served
// compressed (Content-Length is then the encoded size and cannot be used);
// the on-screen megabyte counter always reports real bytes received.
export const FRONTEND_DATA_EXPECTED_BYTES = 10_103_947;
