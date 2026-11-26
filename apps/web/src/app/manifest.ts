import type { MetadataRoute } from "next";

/** Manifesto do app: permite instalar o site (e, no iPhone, receber push pela tela de início). */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "analisebolsa",
    short_name: "analisebolsa",
    description: "Análise educacional de ações, FIIs, ETFs e BDRs da B3.",
    lang: "pt-BR",
    start_url: "/",
    display: "standalone",
    background_color: "#111317",
    theme_color: "#111317",
    icons: [
      { src: "/icones/icone-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icones/icone-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icones/icone-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
