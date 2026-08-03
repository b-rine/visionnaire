export function isReadOnlyDeployment(): boolean {
  return (
    import.meta.env.VITE_READ_ONLY === "true" ||
    window.location.hostname.endsWith(".vercel.app")
  );
}
