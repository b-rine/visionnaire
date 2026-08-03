export default function handler(_request, response) {
  response.status(403).json({
    detail: "Vercel preview deployments are read-only.",
  });
}
