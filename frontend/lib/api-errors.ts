export const GENERIC_API_ERROR_MESSAGE = "AURORA could not complete this request.";

export function formatUploadApiError(message: string, status: number): string {
  if (status === 413) {
    return "Source upload failed: the file exceeds the configured upload limit.";
  }
  if (message === GENERIC_API_ERROR_MESSAGE || message === "Internal Server Error") {
    return "Source upload failed: the backend service did not return a usable response. Confirm it is running and try again.";
  }
  return `Source upload failed: ${message}`;
}
