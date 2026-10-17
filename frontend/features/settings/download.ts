/**
 * Hand a JSON document to the browser as a file. The data never goes through React state or the query cache: it
 * exists as a Blob only until the download starts (GDPR[personal-data]: the export holds everything we keep about
 * the person, RM-278).
 */
export function saveJsonFile(fileName: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
