import { ScrollViewStyleReset } from 'expo-router/html';
import type { PropsWithChildren } from 'react';

export default function Root({ children }: PropsWithChildren) {
  const serviceWorkerBoot = `
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', function () {
        navigator.serviceWorker.register('/sw.js').catch(function () {});
      });
    }
  `;

  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        <meta name="theme-color" content="#090A0C" />
        <meta name="description" content="FUSE Mobile — the sovereign Federation workspace for research, creation, building and governed execution." />
        <meta name="application-name" content="FUSE Mobile" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <link rel="manifest" href="/manifest.webmanifest" />
        <link rel="icon" href="/fuse-icon.svg" />
        <ScrollViewStyleReset />
      </head>
      <body>
        {children}
        <script dangerouslySetInnerHTML={{ __html: serviceWorkerBoot }} />
      </body>
    </html>
  );
}
