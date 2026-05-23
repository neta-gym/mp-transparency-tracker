const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/** Prefix root-relative public asset URLs when the app is deployed under a subpath. */
export function publicPath(path: string | null | undefined): string {
  if (!path) return "";
  if (/^(https?:)?\/\//.test(path) || path.startsWith("data:")) return path;
  if (!path.startsWith("/")) return path;
  if (BASE_PATH && path === BASE_PATH) return path;
  if (BASE_PATH && path.startsWith(`${BASE_PATH}/`)) return path;
  return `${BASE_PATH}${path}`;
}
